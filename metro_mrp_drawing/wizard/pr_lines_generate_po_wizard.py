# -*- coding: utf-8 -*-
import time
from openerp import netsvc
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
from dateutil.relativedelta import relativedelta
import openerp.tools as tools
import openerp.addons.decimal_precision as dp

class pr_line_generate_po_wizard(osv.osv_memory):
    _name = "pr.line.generate.po.wizard"
    _description = "PR Lines Generate PO Wizard"

    def _get_amount_total(self, cr, uid, ids, name, args, context):
        result = {}
        for wizard in self.browse(cr, uid, ids):
            amount = 0.0
            for pr_line in wizard.line_ids:
                amount += pr_line.quantity * pr_line.quantity
            result[wizard.id] = amount
        return result

    _columns = {
        "req_id": fields.many2one('pur.req', string='Purchase Requisition', readonly=True),
        "supplier_id": fields.many2one('res.partner', string='Supplier', required=True),
        "req_line_ids": fields.many2many('pur.req.line', string='Purchase Requisition Line', readonly=True),
        "line_ids": fields.one2many('pr.line.generate.po.line', 'wizard_id', string = 'Purchase Lines'),
        'amount_total': fields.function(_get_amount_total, string='Total Amount',type="float",readonly=True),
        'date_required': fields.date('Delivery Date (ETA)'),
    }


    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(pr_line_generate_po_wizard, self).default_get(cr, uid, fields, context=context)
        record_ids = context and context.get('active_ids', False) or False
        record_model = context and context.get('active_model', False) or False
        if record_ids and record_model == 'pur.req.line':
            req_line_obj = self.pool.get('pur.req.line')
            po_quantity = {}
            supplier_id = False
            date_required = False
            req_id = False
            for req_line in req_line_obj.browse(cr, uid, record_ids, context=context):
                if not req_line.generated_po:
                    if not date_required:
                        if req_line.date_required:
                            date_required = req_line.date_required
                    else:
                        if req_line.date_required:
                            if req_line.date_required > date_required:
                                date_required = req_line.date_required
                    if not req_id:
                        req_id = req_line.req_id.id
                    if not supplier_id and req_line.supplier_id:
                        supplier_id = req_line.supplier_id.id
                    if not po_quantity.get(req_line.product_id.id, False):
                        mfg_ids = req_line.req_id.sale_product_ids and [mfg_id.id for mfg_id in
                                                                        req_line.req_id.sale_product_ids] or []
                        po_quantity.update({req_line.product_id.id : {
                            'product_id': req_line.product_id.id,
                            'quantity': req_line.product_qty_remain,
                            'price': req_line.price,
                            'uom_id': req_line.product_uom_id.id,
                            'req_line_id': req_line.id,
                            'order_line_id': req_line.order_line_id and req_line.order_line_id.id or False,
                            'date_required': req_line.date_required,
                            'supplier_prod_name': req_line.product_id.cn_name,
                            'pr_line_id': req_line.id,
                            'mfg_ids': [],
                            }})
                        if mfg_ids:
                            po_quantity[req_line.product_id.id].update({
                                'mfg_ids': [[6, False, mfg_ids]]
                            })
                    else:
                        po_quantity[req_line.product_id.id]['quantity'] += req_line.product_qty_remain
            po_line_vals = []
            po_amount = 0.0
            for po_line in po_quantity.values():
                po_line_vals.append((0,0,{
                    'product_id': po_line['product_id'],
                    'quantity': po_line['quantity'],
                    'price': po_line['price'],
                    'uom_id': po_line['uom_id'],
                    'req_line_id': po_line['req_line_id'],
                    'order_line_id': po_line['order_line_id'],
                    'date_required': po_line['date_required'],
                    'supplier_prod_name': po_line['supplier_prod_name'],
                    'mfg_ids': po_line['mfg_ids'],
                }))
                po_amount += req_line.price * req_line.product_qty_remain
            if supplier_id:
                res.update({'supplier_id': supplier_id})
            if date_required:
                res.update({'date_required': date_required})
            if req_id:
                res.update({'req_id': req_id})
            res.update({'line_ids': po_line_vals,
                        'req_line_ids': [[6, 0, record_ids]]})
        return res

    def view_init(self, cr, uid, fields_list, context=None):
        if context is None:
            context = {}
        res = super(pr_line_generate_po_wizard, self).view_init(cr, uid, fields_list, context=context)
        record_ids = context and context.get('active_ids', False)
        record_model = context and context.get('active_model', False)
        if record_ids and record_model == 'pur.req.line':
            req_line_obj = self.pool.get('pur.req.line')
            valid_lines = 0
            req_ids = {}
            for line in req_line_obj.browse(cr, uid, record_ids, context=context):
                req_ids.update({line.req_id.id : True})
                if line.product_qty_remain > 0.0:
                    valid_lines += 1
            if len(req_ids) > 1:
                raise osv.except_osv(_('Error!'), _("Can not generate purchase order from 2 purchase requisitions!"))
            if not valid_lines:
                raise osv.except_osv(_('Warning!'), _("No available products need to generate purchase order!"))
        return res

    def do_generate(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids, context=context)[0]
        result_po_ids = []
        if not wizard.req_id:
            raise osv.except_osv(_('Error!'), _("Purchase Requisition can not be left empty!"))
        if not wizard.date_required:
            raise osv.except_osv(_('Error!'), _("Delivery Date(ETA) can not be left empty!"))
        if not wizard.supplier_id:
            raise osv.except_osv(_('Error!'), _("Supplier can not be left empty!"))
        po_lines = []
        for line in wizard.line_ids:
            po_line = {'product_id': line.product_id.id,
                       'product_qty': line.quantity,
                       'product_uom': line.uom_id.id,
                       'req_line_id': line.req_line_id.id,
                       'order_line_id': line.order_line_id and line.order_line_id.id or False,
                       'date_planned': line.date_required,
                       'price_unit': line.price,
                       'name': (line.req_reason or ''),
                       'supplier_prod_id': line.supplier_prod_id,
                       'supplier_prod_name': line.supplier_prod_name,
                       'supplier_prod_code': line.supplier_prod_code,
                       'supplier_delay': line.supplier_delay,
                       'mfg_ids': [[6, False, [mfg_id.id for mfg_id in line.mfg_ids]]],
                       }
            po_lines.append(po_line)
        po_data = {'origin': wizard.req_id.name,
                   'req_id': wizard.req_id.id,
                   'partner_id': wizard.supplier_id.id,
                   'warehouse_id': wizard.req_id.warehouse_id.id,
                   'notes': wizard.req_id.remark,
                   'company_id': wizard.req_id.company_id.id,
                   'lines': po_lines
                   }
        if wizard.req_id.mo_id:
            po_data.update({
                'mo_id': wizard.req_id.mo_id.id,
            })
        # call purchase.oder to generate order
        ret_po = self.pool.get('purchase.order').new_po(cr, uid, [po_data], context=context)
        # set req status to in_purchase
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'pur.req', wizard.req_id.id, 'pur_req_purchase', cr)
        # the 'po_id','po_line_id' should be pushed in the purchase.order.make_po() method
        result_po_ids.append(po_data['new_po_id'])
        return result_po_ids

    def do_generate_view(self, cr, uid, ids, context=None):
        po_ids = self.do_generate(cr, uid, ids, context=context)
        return {
            'domain': "[('id', 'in', [" + ','.join([str(po_id) for po_id in po_ids]) + "])]",
            'name': _('Purchase Order'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'purchase.order',
            'type': 'ir.actions.act_window',
            'context': context,
        }

pr_line_generate_po_wizard()


class pr_line_generate_po_line(osv.osv_memory):
    _name = "pr.line.generate.po.line"
    _description = "PR Lines Generate PO lines"

    def reserved_infor(self, cr, uid, ids, context=None):
        pr_reserved_obj = self.pool.get('pur.req.reserve')
        return pr_reserved_obj.view_reserved_infor(cr, uid, ids, context=context)

    _columns = {
        'wizard_id': fields.many2one('pr.line.generate.po.wizard', 'Purchase Order', readonly=True),
        'product_id': fields.many2one('product.product', 'Product', required=True, readonly=True),
        # 'generation_rule': fields.selection(PO_GENERATION_SELECTION, string='Generation Rule'),
        'reserved_qty': fields.related('product_id', 'reserved_qty', type='float', string='Reserved Qty',
                                       readonly=True),
        'quantity': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),
                                 required=True),
        'mfg_ids': fields.many2many('sale.product', string="MFG IDs"),
        'req_reason': fields.char('Reason and use', size=64),
        'price': fields.float('Unit Price', digits_compute=dp.get_precision('Product Price')),
        'uom_id': fields.many2one('product.uom', 'Unit of Measure', required=True, ),
        "order_line_id": fields.many2one('drawing.order.line', string='Drawing Order Line', readonly=True),
        'pr_line_id': fields.many2one('pur.req.line', string='PR Line', readonly=True),
        'date_required': fields.related('wizard_id', 'date_required', type='date', readonly=True),
        'req_line_id': fields.many2one('pur.req.line', 'Purchase Requisition'),
        'supplier_prod_id': fields.integer(string='Supplier Product ID'),
        'supplier_prod_name': fields.char(string='Supplier Product Name'),
        'supplier_prod_code': fields.char(string='Supplier Product Code'),
        'supplier_delay': fields.integer(string='Supplier Lead Time'),
    }
    _defaults = {
        'supplier_delay': 1,
    }


