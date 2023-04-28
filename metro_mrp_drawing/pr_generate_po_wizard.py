# -*- coding: utf-8 -*-
import time
from openerp import netsvc
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
from dateutil.relativedelta import relativedelta
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST
import openerp.addons.decimal_precision as dp

# PO_GENERATION_SELECTION = [('BASE_ON_STOCK_IGNORE_RESERVED',_('#1 – Order based on Stock, ignore Reserved')),
#                         ('BASE_ON_STOCK_AND_RESERVED',_('#2 – Order based on Stock and Reserved')),
#                         ('IGNORE_STOCK_IGNORE_RESERVED',_('#3 – Ignore stock, ignore Reserved')),
#                       ]

# class pur_req_po_line(osv.osv_memory):
#     _name = "pur.req.po.line"
#     _inherit = "pur.req.po.line"
#
#     _columns = {
#         'generation_rule': fields.selection(PO_GENERATION_SELECTION, string='Generation Rule'),
#     }

class pur_req_po(osv.osv_memory):
    _name = 'pur.req.po'
    _inherit = 'pur.req.po'

    #HoangTK override _create_po function in metro_purchase to add pr information when generate
    def _create_po(self, cr, uid, ids, context=None):
        record_id = context and context.get('active_id', False) or False
        data = self.browse(cr, uid, ids, context=context)[0]
        req = self.pool.get('pur.req').browse(cr, uid, record_id, context=None);
        po_data = {'origin': req.name, 'req_id': record_id, 'partner_id': data.partner_id.id,
                   'warehouse_id': req.warehouse_id.id, 'notes': req.remark, 'company_id': req.company_id.id,
                   'lines': []}
        if req.mo_id:
            po_data.update({
                'mo_id': req.mo_id.id,
            })
        po_lines = []
        for line in data.line_ids:
            quantity = line.req_line_id.product_qty_remain
            if quantity > 0.0:
                po_line = {'product_id': line.product_id.id,
                           'product_qty': quantity,
                           'product_uom': line.uom_po_id.id,
                           'req_line_id': line.req_line_id.id,
                           'date_planned': line.date_required,
                           'price_unit': line.req_line_id.price,
                           'order_line_id': line.order_line_id and line.order_line_id.id or False,
                           'name': (line.req_reason or ''),
                           'supplier_prod_id': line.supplier_prod_id, 'supplier_prod_name': line.supplier_prod_name,
                           'supplier_prod_code': line.supplier_prod_code, 'supplier_delay': line.supplier_delay}
                # update mfg_ids
                mfg_ids = line.mfg_ids and [mfg_id.id for mfg_id in line.mfg_ids] or []
                procurement_id = line.req_line_id.procurement_ids and line.req_line_id.procurement_ids[0] or False
                if procurement_id:
                    if procurement_id.move_id:
                        # add the move_dest_id for the po_line
                        po_line.update({'move_dest_id': procurement_id.move_id.id})
                    if procurement_id.mfg_ids and len(procurement_id.mfg_ids) > 0:
                        mfg_ids.extend([mfg_id.id for mfg_id in procurement_id.mfg_ids])
                if mfg_ids:
                    po_line.update({'mfg_ids': [[6, False, mfg_ids]]})
                po_lines.append( po_line)
        po_data['lines'] = po_lines
        # call purchase.oder to generate order
        ret_po = self.pool.get('purchase.order').new_po(cr, uid, [po_data], context=context)
        # set req status to in_purchase
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'pur.req', record_id, 'pur_req_purchase', cr)
        # the 'po_id','po_line_id' should be pushed in the purchase.order.make_po() method
        return po_data['new_po_id']

    # _columns = {
    #     'generation_rule': fields.selection(PO_GENERATION_SELECTION, string='Generation Rule'),
    # }
pur_req_po()

class pr_generate_po_wizard(osv.osv_memory):
    _name = "pr.generate.po.wizard"
    _description = "PR Generate All PO Wizard"

    def _get_amount_total(self, cr, uid, ids, name, args, context):
        result = {}
        for wizard in self.browse(cr, uid, ids):
            amount = 0.0
            for po in wizard.po_ids:
                amount += po.amount_total
            result[wizard.id] = amount
        return result

    _columns = {
        "pr_id": fields.many2one('pur.req', 'Purchase Request', readonly=True),
        "po_ids": fields.one2many('pr.generate.po.wizard.po', 'wizard_id', string="Purchase Order"),
        'amount_total': fields.function(_get_amount_total,string='Total Amount',type="float",readonly=True)
    }


    def default_get(self, cr, uid, fields, context=None):
        """
         To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary with default values for all field in ``fields``
        """
        if context is None:
            context = {}
        grand_po = context.get('grand_po', False)
        res = super(pr_generate_po_wizard, self).default_get(cr, uid, fields, context=context)
        req_obj = self.pool.get('pur.req')
        req_line_obj = self.pool.get('pur.req.line')
        record_id = context and context.get('active_id', False) or False
        req = req_obj.browse(cr, uid, record_id, context=context)
        line_ids = []
        if grand_po:
            line_ids = []
            for req_line  in req.line_ids:
                # HoangTK Fix grand po empty
                if req_line.product_grand_qty_remain > 0.0:
                    line_ids.append(req_line.id)
        else:
            for req_line  in req.line_ids:
                if req_line.product_qty_remain > 0.0:
                    line_ids.append(req_line.id)
        if line_ids:
            supplier_quantity = {}
            for req_line in req_line_obj.browse(cr, uid, line_ids, context=context):
                supplier_id_key = 0
                if req_line.supplier_id:
                    supplier_id_key = req_line.supplier_id.id
                if grand_po:
                    quantity = req_line.product_grand_qty_remain
                else:
                    quantity = req_line.product_qty_remain
                if not supplier_quantity.get(supplier_id_key, False):
                    supplier_quantity.update({supplier_id_key : {
                                              'quantity':  quantity,
                                              'req_line_ids': [req_line.id]}})
                else:
                    supplier_quantity[supplier_id_key]['quantity'] += quantity
                    supplier_quantity[supplier_id_key]['req_line_ids'].append(req_line.id)
            po_vals = []
            all_po_amount = 0.0
            for supplier_id in supplier_quantity.keys():
                po_amount = 0.0
                po_val = {
                    'supplier_id':supplier_id,
                    'total_quantity': supplier_quantity[supplier_id]['quantity'],
                    'date_required': req.delivery_date,
                    'req_id': req.id
                }
                req_line_ids = supplier_quantity[supplier_id]['req_line_ids']
                po_line_vals = []
                for req_line in req_line_obj.browse(cr, uid, req_line_ids, context=context):
                    po_line_qty = req_line.product_qty_remain
                    if grand_po:
                        po_line_qty = req_line.product_grand_qty_remain
                    po_line_vals.append((0,0,{
                        'product_id': req_line.product_id.id,
                        'quantity':  po_line_qty,
                        'price': req_line.price,
                        'uom_id': req_line.product_uom_id.id,
                        'order_line_id': req_line.order_line_id and req_line.order_line_id.id or False,
                        'date_required': req_line.date_required,
                        'supplier_prod_name': req_line.product_id.cn_name,
                        'req_line_id': req_line.id,
                    }))
                    po_amount += req_line.price * req_line.product_qty_remain
                po_val.update({'line_ids': po_line_vals,'amount_total':po_amount})
                all_po_amount += po_amount
                po_vals.append(po_val)
            res.update({'po_ids': po_vals,'amount_total': all_po_amount})
        return res

    def view_init(self, cr, uid, fields_list, context=None):
        """
         Creates view dynamically and adding fields at runtime.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param context: A standard dictionary
         @return: New arch of view with new columns.
        """
        if context is None:
            context = {}
        res = super(pr_generate_po_wizard, self).view_init(cr, uid, fields_list, context=context)
        record_id = context and context.get('active_id', False)
        if record_id:
            req_obj = self.pool.get('pur.req')
            req = req_obj.browse(cr, uid, record_id, context=context)
            if req.state == 'draft':
                raise osv.except_osv(_('Warning!'),
                                     _("You may only generate purchase orders based on confirmed requisitions!"))
            valid_lines = 0
            for line in req.line_ids:
                if line.product_qty_remain > 0.0:
                    valid_lines += 1
            if not valid_lines:
                raise osv.except_osv(_('Warning!'), _("No available products need to generate purchase order!"))
        return res

    def do_generate(self, cr, uid, ids, context=None):
        record_id = context and context.get('active_id', False) or False
        wizard = self.browse(cr, uid, ids, context=context)[0]
        req = self.pool.get('pur.req').browse(cr, uid, record_id, context=None);
        result_po_ids = []
        mfg_ids = req.sale_product_ids and [mfg_id.id for mfg_id in req.sale_product_ids] or []
        for po_id in wizard.po_ids:
            if not po_id.date_required:
                raise osv.except_osv(_('Error!'), _("Delivery Date(ETA) can not be left empty!"))
            po_data = {'origin': req.name,
                       'req_id': record_id,
                       'partner_id': po_id.supplier_id.id,
                       'warehouse_id': req.warehouse_id.id,
                       'notes': req.remark,
                       'company_id': req.company_id.id,
                       'lines': []}
            if req.mo_id:
                po_data.update({
                    'mo_id': req.mo_id.id,
                })
            po_lines = []
            for line in po_id.line_ids:
                quantity = line.quantity
                po_line = {'product_id': line.product_id.id,
                           'product_qty': quantity,
                           'product_uom': line.uom_id.id,
                           'req_line_id': line.req_line_id.id,
                           'order_line_id': line.order_line_id and line.order_line_id.id or False,
                           'date_planned': po_id.date_required,
                           'price_unit': line.price,
                           'name': (line.req_reason or ''),
                           'supplier_prod_id': line.supplier_prod_id,
                           'supplier_prod_name': line.supplier_prod_name,
                           'supplier_prod_code': line.supplier_prod_code,
                           'supplier_delay': line.supplier_delay
                           }
                #mfg_ids = line.mfg_ids and [mfg_id.id for mfg_id in line.mfg_ids] or []
                #procurement_id = line.req_line_id.procurement_ids and line.req_line_id.procurement_ids[0] or False
                #if procurement_id:
                #    if procurement_id.move_id:
                        # add the move_dest_id for the po_line
                #        po_line.update({'move_dest_id': procurement_id.move_id.id})
                #    if procurement_id.mfg_ids and len(procurement_id.mfg_ids) > 0:
                #        mfg_ids.extend([mfg_id.id for mfg_id in procurement_id.mfg_ids])
                if mfg_ids:
                    po_line.update({'mfg_ids': [[6, False, mfg_ids]]})

                po_lines.append(po_line)
            po_data['lines'] = po_lines
            # call purchase.oder to generate order
            ret_po = self.pool.get('purchase.order').new_po(cr, uid, [po_data], context=context)
            # set req status to in_purchase
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'pur.req', record_id, 'pur_req_purchase', cr)
            # the 'po_id','po_line_id' should be pushed in the purchase.order.make_po() method
            result_po_ids.append(po_data['new_po_id'])
        return result_po_ids

    def do_generate_view(self, cr, uid, ids, context=None):
        record_id = context and context.get('active_id', False) or False
        po_ids = self.do_generate(cr, uid, ids, context=context)
        return {
            'domain': "[('req_id', 'in', [" + str(record_id) + "])]",
            'name': _('Purchase Order'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'purchase.order',
            'type': 'ir.actions.act_window',
            'context': context,
        }
pr_generate_po_wizard()


class pr_generate_po_wizard_po(osv.osv_memory):
    _name = "pr.generate.po.wizard.po"
    _description = "PR Wizard Purchase Order"

    def _get_amount_total(self, cr, uid, ids, name, args, context):
        result = {}
        for po in self.browse(cr, uid, ids):
            amount = 0.0
            for line in po.line_ids:
                amount += line.amount_total
            result[po.id] = amount
        return result

    # def onchange_generation_rule(self, cr, uid, ids, req_id, supplier_id, generation_rule, context=None):
    #     vals = {}
    #     if req_id:
    #         pr_obj = self.pool.get('pur.req')
    #         pr_line_obj = self.pool.get('pur.req.line')
    #         pr = pr_obj.browse(cr, uid, req_id, context=context)
    #         if pr:
    #             line_ids = []
    #             req_line_ids = pr_line_obj.search(cr, uid, [('req_id','=',req_id),
    #                                                     ('supplier_id','=',supplier_id)], context=context)
    #             for req_line in pr_line_obj.browse(cr, uid, req_line_ids, context=context):
    #                 quantity = pr_obj.get_product_qty_base_on_generation_rule(cr, uid, req_line,generation_rule)
    #                 if quantity > 0:
    #                     line_ids.append({
    #                             'product_id': req_line.product_id.id,
    #                             'quantity': quantity,
    #                             'price': req_line.price,
    #                             'uom_id': req_line.product_uom_id.id,
    #                             'order_line_id': req_line.order_line_id and req_line.order_line_id.id or False,
    #                             'date_required': req_line.date_required,
    #                             'supplier_prod_name': req_line.product_id.cn_name,
    #                             'req_line_id': req_line.id,
    #                         })
    #             if line_ids:
    #                 vals.update({'line_ids': line_ids})
    #     return {'value': vals}

    _columns = {
        'wizard_id': fields.many2one('pr.generate.po.wizard', 'PR Wizard'),
        'req_id': fields.many2one('pur.req',string ='PR',readonly=True),
        'date_required': fields.date('Delivery Date (ETA)'),
        'supplier_id': fields.many2one('res.partner', 'Supplier', required=True),
        'total_quantity': fields.float('Total Quantity', readonly=True),
        'line_ids': fields.one2many('pr.generate.po.wizard.po.line', 'order_id', string='Purchase Order Lines',
                                    ),
        # 'generation_rule': fields.selection(PO_GENERATION_SELECTION, string='Generation Rule'),
        'amount_total': fields.function(_get_amount_total,string='Total Amount',type="float",readonly=True)
    }
    # _defaults = {
    #     'generation_rule': 'BASE_ON_STOCK_IGNORE_RESERVED',
    # }

pr_generate_po_wizard_po()


class pr_generate_po_wizard_po_line(osv.osv_memory):
    _name = "pr.generate.po.wizard.po.line"
    _description = "PR Wizard Purchase Order Line"

    def _get_amount_total(self, cr, uid, ids, name, args, context):
        result = {}
        for line in self.browse(cr, uid, ids):
            result[line.id] = line.price * line.quantity
        return result

    def reserved_infor(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        product_ids = []
        for pr_line in self.browse(cr, uid, ids, context=context):
            product_ids.append(pr_line.product_id.id)
        if product_ids:
            pr_reserved_obj = self.pool.get('pur.req.reserve')
            return pr_reserved_obj.view_reserved_infor_products(cr, uid, ids, context=context)
        return False

    # def onchange_generation_rule(self, cr, uid, ids, req_line_id, generation_rule, context=None):
    #     vals = {}
    #     if req_line_id:
    #         pr_line_obj = self.pool.get('pur.req.line')
    #         pr_obj = self.pool.get('pur.req')
    #         req_line = pr_line_obj.browse(cr, uid, req_line_id, context=context)
    #         if req_line:
    #             quantity = pr_obj.get_product_qty_base_on_generation_rule(cr, uid, req_line, generation_rule)
    #             vals.update({'quantity': quantity})
    #     return {'value': vals}

    _columns = {
        'order_id': fields.many2one('pr.generate.po.wizard.po', 'Purchase Order', readonly=True),
        'product_id': fields.many2one('product.product', 'Product', required=True),
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
        'req_line_id': fields.many2one('pur.req.line', string='PR Line', readonly=True),
        #'date_required': fields.date('Delivery Date (ETA)', required=True),
        'date_required': fields.related('order_id','date_required',type='date',readonly=True),
        #'req_line_id': fields.many2one('pur.req.line', 'Purchase Requisition'),
        'supplier_prod_id': fields.integer(string='Supplier Product ID'),
        'supplier_prod_name': fields.char(string='Supplier Product Name'),
        'supplier_prod_code': fields.char(string='Supplier Product Code'),
        'supplier_delay': fields.integer(string='Supplier Lead Time'),
        'amount_total': fields.function(_get_amount_total,string='Amount',type="float",readonly=True),
    }
    _defaults = {
        'supplier_delay': 1,
    }
pr_generate_po_wizard_po_line()
