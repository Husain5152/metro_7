# -*- encoding: utf-8 -*-
from openerp.osv import fields,osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT,DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime
from openerp import netsvc
from openerp.addons.metro_mrp_drawing.drawing_order import PART_TYPE_SELECTION
from openerp.osv.orm import browse_record, browse_null
from openerp import tools
from math import ceil
from openerp import SUPERUSER_ID
import logging

from openerp.tools import float_compare

PR_TYPES = [('normal', 'Normal PR'),
            ('sourcing', 'Sourcing PR'),
            ('procurement', 'Procurement PR'),
            ('mfg', 'MFG PR'),
            ('mfg_pms','PMS PR'),
            ('mfg_pml','PML PR'),
            ('mfg_o', 'MFG-O PR'),
            ('canada','Canada PR')]

# Rule  # 1 (default) = Name: regarding available & incoming (Formula: N-stock-reserved-incoming)
# Rule  # 2 = regarding available (N-stock-reserved)
# Rule  # 3 = regarding stock (N-stock)
# Rule  # 4 = ignore All rules, just order based on  PR Request (N)
# Rule  # 5 = regarding stock and incoming (N-stock-incoming)
# Rule  # 6 = regarding  incoming (N-incoming)

PR_AVAILABLE_QTY_RULE = [
    ('REGARD_AVAILABLE_INCOMING', _('#1 Regarding available & incoming (default)')),
    ('REGARD_AVAILABLE', _('#2 Regarding available')),
    ('REGARD_STOCK', _('#3 Regarding stock')),
    ('IGNORE_ALL',_('#4 – Ignore All rules, just order based on  PR Request')),
    ('REGARD_STOCK_INCOMING',_('#5 – Regarding stock and incoming')),
    ('REGARD_INCOMING',_('#6 – Regarding incoming'))
                      ]
_logger = logging.getLogger(__name__)



class pur_req_history(osv.osv):
    _name = "pur.req.history"
    _description = "Purchase Request History"
    _columns = {
        'date': fields.datetime('Modified Date',readonly=True),
        'pur_req_id': fields.many2one('pur.req','Purchase Request',readonly=True),
        'user_id': fields.many2one('res.users','User',readonly=True),
        'content': fields.char('Content',readonly=True),
        'vals': fields.char('Update Values',readonly=True,size=256),
    }
    _order = 'date desc'
pur_req_history()

class pur_req_move1(osv.osv):
    _name = "pur.req.move1"
    _description = "Purchase Request Move 1"
    _columns = {
        "pur_req_id": fields.many2one("pur.req","Purchase Request",readonly=True),
        "product_id": fields.many2one("product.product","Product",readonly=True),
        "erp_no": fields.char("ERP #",size=128,readonly=True),
        "quantity": fields.integer("Quantity",readonly=True),
    }
pur_req_move1()
class pur_req_move2(osv.osv):
    _name = "pur.req.move2"
    _description = "Purchase Request Move 2"
    _columns = {
        "pur_req_id": fields.many2one("pur.req","Purchase Request",readonly=True),
        "product_id": fields.many2one("product.product","Product",readonly=True),
        "erp_no": fields.char("ERP #",size=128,readonly=True),
        "quantity": fields.integer("Quantity",readonly=True),
    }
pur_req_move2()
class pur_req_move3(osv.osv):
    _name = "pur.req.move3"
    _description = "Purchase Request Move 3"
    _columns = {
        "pur_req_id": fields.many2one("pur.req","Purchase Request",readonly=True),
        "product_id": fields.many2one("product.product","Product",readonly=True),
        "erp_no": fields.char("ERP #",size=128,readonly=True),
        "quantity": fields.integer("Quantity",readonly=True),
    }
pur_req_move3()
class pur_req_line(osv.osv):
    _name = "pur.req.line"
    _inherit = "pur.req.line"

    def calculate_available_qty(self, cr, uid, ids, context=None):
        if context is None:
            context= {}
        return {
            'name': 'Calculate PR Available Qty Wizard',
            'res_model': 'calculate.pr.available.qty.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def action_set_supplier(self, cr, uid, ids, context=None):
        if context is None:
            context= {}
        return {
            'name': 'Set Supplier Wizard',
            'res_model': 'set.pr.line.supplier.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }


    def send_pr_email(self, cr, uid, ids, context=None):
        if not type(ids) is list:
            ids = [ids]
        req_id = False
        for line in self.browse(cr, uid, ids, context=context):
            if not req_id:
                req_id = line.req_id.id
            if req_id != line.req_id.id:
                raise osv.except_osv(_("Error!"), _('You have to select lines of same PR!'))
            #if line.part_type != 'POEM':
            #    raise osv.except_osv(_("Error!"), _('You are allowed to email POEM type only!'))
        if not req_id:
            raise osv.except_osv(_("Error!"), _('No PR lines that are qualified to email!'))
        pur_req_obj = self.pool.get('pur.req')
        return pur_req_obj.pr_email_wizard(cr, uid, [req_id], context=context)

    def onchange_product_id(self, cr, uid, ids, product_id, context=None):
        """ Changes UoM,inv_qty if product_id changes.
        @param product_id: Changed product_id
        @return:  Dictionary of changed values
        """
        result = super(pur_req_line,self).onchange_product_id(cr, uid, ids, product_id, context=context)
        if product_id:
            prod = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            po_line_obj = self.pool.get('purchase.order.line')
            purchase_order_line_ids = po_line_obj.search(cr, uid,
                                                         [('product_id', '=', product_id),
                                                          ('state', 'in',
                                                           ['confirmed', 'approved',
                                                            'done'])],
                                                         order="date_planned desc",limit=1)
            if purchase_order_line_ids:
                purchase_order_line = po_line_obj.browse(cr, uid, purchase_order_line_ids)[0]
                result['value'].update({'supplier_id': purchase_order_line.order_id.partner_id.id,
                                    })
            elif len(prod.seller_ids) > 0:
                result['value'].update({'supplier_id': prod.seller_ids[0].name.id})
            #inv_qty = 0.0
            #if prod.qty_available > prod.reserved_qty:
            #    inv_qty = prod.qty_available - prod.reserved_qty
            price = prod.uom_po_price
            if prod.part_type in ['PMS','PML']:
                price = prod.standard_price
            result['value'].update({
                'price': price,
                #'inv_qty': inv_qty,
                'thickness':prod.thickness,
                'standard':prod.mfg_standard,
                'part_type': prod.part_type,
            })

        return result

    def _get_amount_total(self, cr, uid, ids, name, args, context):
        result = {}
        for line in self.browse(cr, uid, ids):
            result[line.id] = line.price * line.product_qty
        return result

    def _po_info2(self, cr, uid, ids, field_names=None, arg=False, context=None):
        if not field_names:
            field_names = []
        if context is None:
            context = {}
        res = {}
        for id in ids:
            res[id] = {}.fromkeys(field_names, 0.0)
        uom_obj = self.pool.get('product.uom')
        # Improve performance by using read
        po_line_obj = self.pool.get('purchase.order.line')
        req_line_values = self.read(cr, uid, ids, ['id', 'product_uom_id', 'product_qty'])
        for req_line_value in req_line_values:
            product_generated_qty = 0.0
            req_line_id = req_line_value['id']
            product_qty = req_line_value['product_qty']
            po_qty_str = []
            po_line_ids = po_line_obj.search(cr, uid, [('req_line_id', '=', req_line_value['id'])], context=context)
            if po_line_ids:
                to_uom = uom_obj.browse(cr, uid, req_line_value['product_uom_id'][0], context=context)
                po_line_values = po_line_obj.read(cr, uid, po_line_ids, ['order_id', 'state', 'product_uom', 'product_qty'])
                for po_line_value in po_line_values:
                    if po_line_value['state'] != 'cancel':
                        ctx_uom = context.copy()
                        ctx_uom['raise-exception'] = False
                        from_uom = uom_obj.browse(cr, uid, po_line_value['product_uom'][0], context=context)

                        uom_po_qty = uom_obj._compute_qty_obj(cr, uid, from_uom, po_line_value['product_qty'], \
                                                              to_uom, context=ctx_uom)
                        product_generated_qty += uom_po_qty
                        po_qty_str.append('%s(%s)@%s' % (po_line_value['product_qty'], uom_po_qty,
                                                         po_line_value['order_id'][1]))
            res[req_line_id]['product_generated_qty'] = product_generated_qty
            res[req_line_id]['po_info'] = ';'.join(po_qty_str)
            po_finished = float_compare(product_qty, product_generated_qty, precision_rounding=4)
            res[req_line_id]['generated_po'] = (po_finished <= 0)
        return res

    def _pr_qty_info(self, cr, uid, ids, field_names=None, arg=False, context=None):
        """ Finds the requisition related PO info.
        @return: Dictionary of values
        """
        if not field_names:
            field_names = []
        if context is None:
            context = {}
        res = {}
        for id in ids:
            res[id] = {}.fromkeys(field_names, 0.0)
        # uom_obj = self.pool.get('product.uom')
        # product_obj = self.pool.get('product.product')
        # Improve performance by using read
        # for req_line in self.browse(cr, uid, ids, context=context):
        # po_line_obj = self.pool.get('purchase.order.line')
        req_line_values = self.read(cr, uid, ids, ['id', 'product_qty',
                                                   'product_other_reserved_qty', 'product_current_reserved_qty',
                                                   'product_onhand_qty', 'product_incoming_qty','product_generated_qty',
                                                   'available_qty_rule'])
        for req_line_value in req_line_values:
            product_generated_qty = req_line_value['product_generated_qty']
            req_line_id = req_line_value['id']
            product_qty = req_line_value['product_qty']
            product_other_reserved_qty = req_line_value['product_other_reserved_qty']
            available_qty_rule = req_line_value['available_qty_rule']
            product_current_reserved_qty = req_line_value['product_current_reserved_qty']
            product_onhand_qty = req_line_value['product_onhand_qty']
            product_incoming_qty = req_line_value['product_incoming_qty']
            # po_qty_str = []
            # po_line_ids = po_line_obj.search(cr, uid, [('req_line_id', '=', req_line_value['id'])], context=context)
            # if req_line.po_lines_ids:
            # if po_line_ids:
            #     to_uom = uom_obj.browse(cr, uid, req_line_value['product_uom_id'][0], context=context)
            #     po_line_values = po_line_obj.read(cr, uid, po_line_ids, ['order_id', 'state', 'product_uom', 'product_qty'])
            #     for po_line_value in po_line_values:
            #         if po_line_value['state'] != 'cancel':
            #             ctx_uom = context.copy()
            #             ctx_uom['raise-exception'] = False
            #             from_uom = uom_obj.browse(cr, uid, po_line_value['product_uom'][0], context=context)
            #
            #             uom_po_qty = uom_obj._compute_qty_obj(cr, uid, from_uom, po_line_value['product_qty'], \
            #                                                   to_uom, context=ctx_uom)
            #             product_generated_qty += uom_po_qty
            #             po_qty_str.append('%s(%s)@%s' % (po_line_value['product_qty'], uom_po_qty,
            #                                              po_line_value['order_id'][1]))
            # res[req_line_id]['product_generated_qty'] = product_generated_qty
            # res[req_line_id]['po_info'] = ';'.join(po_qty_str)
            # po_finished = float_compare(product_qty, product_generated_qty, precision_rounding=4)
            # res[req_line_id]['generated_po'] = (po_finished <= 0)
            # Rule  # 1 (default) = Name: regarding available & incoming (Formula: N-stock-reserved-incoming)
            # update 10/22/2018: Q=N-S+R-I
            # Rule  # 2 = regarding available (N-stock-reserved)
            # update 10/22/2018: Q=N-S+R
            # R: other PR reserved qty
            # Rule  # 3 = regarding stock (N-stock)
            # Rule  # 4 = ignore All rules, just order based on  PR Request (N)
            # Rule  # 5 = regarding stock and incoming (N-stock-incoming)
            # Rule  # 6 = regarding  incoming (N-incoming)
            # PR_AVAILABLE_QTY_RULE = [
            #     ('REGARD_AVAILABLE_INCOMING', _('#1 Regarding available & incoming (default)')),
            #     ('REGARD_AVAILABLE', _('#2 Regarding available')),
            #     ('REGARD_STOCK', _('#3 Regarding stock')),
            #     ('IGNORE_ALL', _('#4 – Ignore All rules, just order based on  PR Request')),
            #     ('REGARD_STOCK_INCOMING', _('#5 – Regarding stock and incoming')),
            #     ('REGARD_INCOMING', _('#6 – Regarding incoming'))
            product_qty_remain = product_qty - product_generated_qty
            if available_qty_rule == 'REGARD_AVAILABLE_INCOMING':
                product_qty_remain = product_qty - product_generated_qty - \
                                     product_onhand_qty + product_other_reserved_qty - \
                                     product_incoming_qty
            elif available_qty_rule == 'REGARD_AVAILABLE':
                product_qty_remain = product_qty - product_generated_qty - \
                                     product_onhand_qty + product_other_reserved_qty
            elif available_qty_rule == 'REGARD_STOCK':
                product_qty_remain = product_qty - product_generated_qty - \
                                     product_onhand_qty
            elif available_qty_rule == 'IGNORE_ALL':
                product_qty_remain = product_qty - product_generated_qty
            elif available_qty_rule == 'REGARD_STOCK_INCOMING':
                product_qty_remain = product_qty - product_generated_qty - \
                                     product_onhand_qty - product_incoming_qty
            elif available_qty_rule == 'REGARD_INCOMING':
                product_qty_remain = product_qty - product_generated_qty - \
                                     product_incoming_qty
            if product_qty_remain < 0.0:
                product_qty_remain = 0.0
            product_available_qty = product_onhand_qty - product_current_reserved_qty
            if product_available_qty < 0.0:
                product_available_qty = 0.0

            res[req_line_id]['product_qty_remain'] = product_qty_remain
            res[req_line_id]['product_available_qty'] = product_available_qty
        return res

    def _get_pur_req_from_product(self, cr, uid, ids, context=None):
        pur_req_line_obj = self.pool.get('pur.req.line')
        pur_req_line_ids = pur_req_line_obj.search(cr, uid, [('product_id', 'in', ids)], context=context)
        return pur_req_line_ids

    def _get_line_from_pur_req(self, cr, uid, ids, context=None):
        pur_req_line_obj = self.pool.get('pur.req.line')
        pur_req_line_ids = pur_req_line_obj.search(cr, uid, [('req_id', 'in', ids)], context=context)
        return pur_req_line_ids

    def _compute_other_reserved_qty(self, cr, uid, ids, field_names=None, arg=False, context=None):
        res = {}
        pur_req_reserve_obj = self.pool.get('pur.req.reserve')
        # for req_line in self.browse(cr, uid, ids, context=context):
        req_line_values = self.read(cr, uid, ids, ['id', 'product_current_reserved_qty', 'req_id', 'product_id'])
        for req_line_value in req_line_values:
            if req_line_value['product_id']:
                req_line_id = req_line_value['id']
                product_current_reserved_qty = req_line_value['product_current_reserved_qty']
                req_id = req_line_value['req_id'][0]
                product_id = req_line_value['product_id'][0]
                res[req_line_id] = product_current_reserved_qty - \
                                pur_req_reserve_obj.get_reserved_qty_except(cr, uid, req_id, product_id, context=context)
        return res

    def _get_pur_req_from_po_line(self, cr, uid, ids, context=None):
        res = set()
        purchase_order_line_obj = self.pool.get('purchase.order.line')
        for line in purchase_order_line_obj.browse(cr, uid, ids, context=context):
            if line.req_line_id:
                res.add(line.req_line_id.id)
        return res

    def _compute_product_grand_qty_remain(self, cr, uid, ids, field_names=None, arg=False, context=None):
        if context is None:
            context = {}
        res = {}
        for req_line in self.browse(cr, uid, ids, context=context):
            line_ids = self.search(cr, uid, [('product_id','=', req_line.product_id.id),
                                             ('order_state', 'in', ['approved', 'in_purchase'])],
                                   context=context)
            product_grand_qty_remain = 0.0
            for line_id in self.browse(cr, uid, line_ids, context=context):
                product_grand_qty_remain += line_id.product_qty_remain

            res[req_line.id] = product_grand_qty_remain
        return res

    _columns = {
        "sequence": fields.integer('#', readonly=True),
        "pr_type": fields.related('req_id', 'pr_type', type='selection',
                                  selection=PR_TYPES,
                                  string='PR Type', readonly=True, store=True, select=1),
        'sale_product_ids': fields.related('req_id', 'sale_product_ids', type="many2many", relation="sale.product",
                                           string="Unit IDs"),
        'mo_id': fields.related('req_id','mo_id',type='many2one',relation="mrp.production",string="Manufacturer Order",readonly=True),
        'unit': fields.related('req_id','unit',type='many2one',relation="product.product",string="Unit",readonly=True),
        'drawing_order_id': fields.related('req_id','drawing_order_id',type="many2one",relation="drawing.order",string="Drawing Order",readonly=True),
        "order_line_id": fields.many2one('drawing.order.line',string='Drawing Order Line',readonly=True),
        'drawing_file_name': fields.related('order_line_id', 'drawing_file_name', string='Drawing PDF Name',
                                            type='char', size=64, readonly=True),
        'drawing_file': fields.related('order_line_id', 'drawing_file', string="Drawing PDF", type="binary",
                                       readonly=True),
        'drawing_download': fields.char('Drawing PDF', size=128, readonly=True),
        'dxf_file_name': fields.related('order_line_id', 'dxf_file_name', string='Drawing DXF Name',
                                            type='char', size=64, readonly=True),
        'dxf_file': fields.related('order_line_id', 'dxf_file', string="Drawing DXF", type="binary",
                                       readonly=True),
        'dxf_download': fields.char('Drawing DXF', size=128, readonly=True),
        'part_number': fields.char('Part Number', size=128, readonly=True),
        'bom_qty': fields.related('order_line_id','bom_qty', string="Bom Qty", type='integer',readonly=True,),
        'part_type': fields.selection(PART_TYPE_SELECTION, string='Part Type', readonly=True),
        'description': fields.char('Description', size=128, readonly=True),
        "erp_no": fields.char("ERP #", size=128,readonly=True),
        "item_no": fields.char("Item No", size=128, readonly=True),
        "name": fields.char("Name", size=128),
        "material": fields.char("Material", size=128, ),
        "thickness": fields.char("Thickness/Length", size=128),
        "standard": fields.char("Standard", size=128, readonly=True),
        'generated_po': fields.function(_po_info2, multi='_po_info2', string='PO Generated',
                                        type='boolean', readonly=True,
                                        store={
                                            'purchase.order.line': (
                                                _get_pur_req_from_po_line,
                                                ['product_id', 'req_line_id', 'product_qty', 'product_uom'], 10),
                                            'pur.req.line': (lambda self, cr, uid, ids, ctx=None: ids,
                                                             ['product_id', 'product_qty', 'product_uom_id'],
                                                             20),
                                        },
                                        help="It indicates that this products has PO generated"),
        'product_grand_qty_remain': fields.function(_compute_product_grand_qty_remain, string='Grand Qty Remaining', type='float',
                                              digits_compute=dp.get_precision('Product Unit of Measure'),
                                              readonly=True,
                                              store={
                                                   'pur.req.line': (lambda self, cr, uid, ids, ctx=None: ids,
                                                                    ['product_id', 'product_qty_remain'],
                                                                    10),
                                              }
                                                    ),
        'product_qty_remain': fields.function(_pr_qty_info, multi='_pr_qty_info', string='Qty Remaining', type='float',
                                              digits_compute=dp.get_precision('Product Unit of Measure'),
                                              readonly=True,
                                              store={
                                                  'product.product': (_get_pur_req_from_product,
                                                                      ['qty_available',
                                                                       'qty_in'],
                                                                      30),
                                                  'pur.req': (_get_line_from_pur_req, ['available_qty_rule'], 10),
                                                  'pur.req.line': (lambda self, cr, uid, ids, ctx=None: ids,
                                                                   ['product_id',
                                                                    'product_generated_qty',
                                                                    'product_other_reserved_qty',
                                                                    'product_current_reserved_qty'],
                                                                   20),
                                              }
                                              ),
        'product_generated_qty': fields.function(_po_info2, multi='_po_info2', string='PO Generated Qty', type='float',
                                                 digits_compute=dp.get_precision('Product Unit of Measure'),
                                                 readonly=True,
                                                 store={
                                                     'purchase.order.line': (
                                                     _get_pur_req_from_po_line, ['product_id', 'req_line_id', 'product_qty', 'product_uom' ], 10),
                                                     'pur.req.line': (lambda self, cr, uid, ids, ctx=None: ids,
                                                                      ['product_id', 'product_qty', 'product_uom_id'],
                                                                      20),
                                                 }
                                                 ),
        'product_available_qty': fields.function(_pr_qty_info, multi='_pr_qty_info', string='Available Qty', type='float',
                                                 digits_compute=dp.get_precision('Product Unit of Measure'),
                                                 readonly=True,
                                                 store={
                                                     'product.product': (_get_pur_req_from_product,
                                                                        ['qty_available',
                                                                         'qty_in'],
                                                                         30),
                                                     'pur.req': (_get_line_from_pur_req, ['available_qty_rule'], 10),
                                                     'pur.req.line': (lambda self, cr, uid, ids, ctx=None: ids,
                                                                      ['product_id',
                                                                       'product_generated_qty',
                                                                       'product_other_reserved_qty',
                                                                       'product_current_reserved_qty'],
                                                                      20),
                                                 }
                                                 ),
        'po_info': fields.function(_po_info2, multi='_po_info2', type='char',
                                   string='PO Quantity', readonly=True,
                                   store={
                                       'purchase.order.line': (
                                           _get_pur_req_from_po_line,
                                           ['product_id', 'req_line_id', 'product_qty', 'product_uom'], 10),
                                       'pur.req.line': (lambda self, cr, uid, ids, ctx=None: ids,
                                                        ['product_id', 'product_qty', 'product_uom_id'],
                                                        20),
                                   }
                                   ),
        "product_current_reserved_qty": fields.related('product_id','reserved_qty', type='float', string='All Reserved Qty'),
        "product_reserved_qty": fields.float('This Reserved Qty', help='The reserved quantity of this PR line'),
        "product_other_reserved_qty": fields.function(_compute_other_reserved_qty, string='Other Reserved Qty', type='float',
                                                 digits_compute=dp.get_precision('Product Unit of Measure'),
                                                 readonly=True, help='The reserved quantity of other PR lines',
                                                      store=False
                                                      # store={
                                                      #     'product.product': (_get_pur_req_from_product, ['product_id', 'reserved_qty'], 10),
                                                      #     'pur.req.line': (lambda self, cr, uid, ids, ctx=None: ids, ['product_id', 'product_current_reserved_qty'], 10),
                                                      # }
                                                      ),
        "reserved_id": fields.many2one('pur.req.reserve', string='Reserved Id'),
        "available_qty_rule": fields.related('req_id', 'available_qty_rule', type='selection',string='Remain Qty Rule',readonly=True,
                                      selection=PR_AVAILABLE_QTY_RULE),
        "note": fields.char("Note", size=128, ),
        "price": fields.float("Price"),

        'amount_total': fields.function(_get_amount_total, string='Total Amount', type="float", readonly=True,
                                        store={
                                            _name: (lambda self, cr, uid, ids, c={}: ids, ['price','product_qty'], 40),
                                        }
                                        ),
        'expected_date': fields.date('Expected Date',readonly=True),
    }
    _defaults = {
        'drawing_download': 'drawing_file',
        'dxf_download': 'dxf_file',

    }

    def create(self, cr, uid, vals, context=None):
        result = super(pur_req_line,self).create(cr, uid, vals,context=context)
        if result:
            line = self.browse(cr, uid, result,context=context)
            sequence = len(line.req_id.line_ids)
            super(pur_req_line,self).write(cr, uid, [result],{'sequence': sequence})
            # req_history_obj = self.pool.get('pur.req.history')
            # req_history_obj.create(cr, uid, {
            #     'pur_req_id': line.req_id.id,
            #     'user_id': uid,
            #     'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            #     'content': _('Create Purchase Request Line'),
            #     'vals': '%s' % (vals),
            # })
        return result

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        res = super(pur_req_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        return res

    def view_requesting_pr(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context:
            context = {}
        product_ids = []
        for pr_line in self.browse(cr, uid, ids, context=context):
            product_ids.append(pr_line.product_id.id)
        product_obj = self.pool.get('product.product')
        return product_obj.view_requesting_pr(cr, uid, product_ids, context=context)

    def view_incoming_shipment(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context:
            context = {}
        product_ids = []
        for pr_line in self.browse(cr, uid, ids, context=context):
            product_ids.append(pr_line.product_id.id)
        product_obj = self.pool.get('product.product')
        return product_obj.view_incoming_shipment(cr, uid, product_ids, context=context)


    def reserved_infor(self, cr, uid, ids, context=None):
        if not context:
            context={}
        except_pr_ids = [line.req_id.id for line in self.browse(cr, uid, ids, context=context)]
        context.update({'except_pr_ids':except_pr_ids})
        pr_reserved_obj = self.pool.get('pur.req.reserve')
        return pr_reserved_obj.view_reserved_infor(cr, uid, ids, context=context)

    _order = "sequence asc"

class pur_req(osv.osv):
    _name = "pur.req"
    _inherit = "pur.req"

    def open_pr_lines(self, cr, uid, ids, context=None):
        if not isinstance(ids, list):
            ids = [ids]
        return {
            'domain': "[('req_id', 'in', [" + ",".join(str(pr_id) for pr_id in ids) + "])]",
            'name': _('PR by Products'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'pur.req.line',
            'type': 'ir.actions.act_window',
            'context': context,
        }

    def pr_email_wizard(self, cr, uid, ids, context=None):
        #mod_obj = self.pool.get('ir.model.data')
        #res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'view_pr_send_email_wizard')
        #res_id = res and res[1] or False
        return {
            'name': 'PR Email Wizard',
            'res_model': 'pr.send.email.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            #'view_id': [res_id],
            'target': 'new',
            'context': context,
        }

    def send_pr_email(self, cr, uid, ids, context=None):
        if not type(ids) is list:
            ids = [ids]
        ir_model_data = self.pool.get('ir.model.data')
        try:
            template_id = ir_model_data.get_object_reference(cr, uid, 'metro', 'email_template_pr_poem')[1]
            if ids:
                req = self.browse(cr, uid, ids[0], context=context)
                if req.pr_type == 'sourcing':
                    template_id = ir_model_data.get_object_reference(cr, uid, 'metro', 'email_template_pr_outsource')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference(cr, uid, 'mail', 'email_compose_message_wizard_form')[
                1]
        except ValueError:
            compose_form_id = False
        ctx = dict(context)
        #pr_line_ids = context.get('pr_line_ids',[]) or []
        ctx.update({
            'default_model': 'pur.req',
            'default_res_id': ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'show_price': False,
            #'pr_line_ids': pr_line_ids,
        })
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        res = super(pur_req, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        return res

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'state': 'draft',
        })
        return super(pur_req, self).copy(cr, uid, id, default, context)

    def do_merge(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService("workflow")
        def make_key(br, fields):
            list_key = []
            for field in fields:
                field_val = getattr(br, field)
                if field in ('product_id', 'mo_id', 'company_id','unit','bigsubassembly_id','warehouse_id'):
                    if not field_val:
                        field_val = False
                if isinstance(field_val, browse_record):
                    field_val = field_val.id
                elif isinstance(field_val, browse_null):
                    field_val = False
                elif isinstance(field_val, list):
                    field_val = ((6, 0, tuple([v.id for v in field_val])),)
                list_key.append((field, field_val))
            list_key.sort()
            return tuple(list_key)

        new_reqs = {}
        for req in [req for req in self.browse(cr, uid, ids, context=context) if req.state == 'draft']:
            req_key = make_key(req, ('mo_id','pr_type', 'delivery_date', 'company_id','unit','sale_product_ids','warehouse_id'))
            new_req = new_reqs.setdefault(req_key, ({}, [],[],[]))
            new_req[1].append(req.id)
            merged_drawing_orders = []
            if req.drawing_order_id:
                merged_drawing_orders.append(req.drawing_order_id)
            if req.merged_drawing_order_ids:
                merged_drawing_orders.extend(req.merged_drawing_order_ids)
            for merged_drawing_order in merged_drawing_orders:
                if merged_drawing_order.id not in new_req[3]:
                    new_req[3].append(merged_drawing_order.id)
                if merged_drawing_order.product_id.name not in new_req[2]:
                    new_req[2].append('*) %s,DO#%s,%s' % (req.name,
                                                        merged_drawing_order.id,
                                                        merged_drawing_order.product_id.name))
            pr_infos = new_req[0]
            if not pr_infos:
                pr_infos.update({
                    'warehouse_id': req.warehouse_id.id,
                    'delivery_date': req.delivery_date,
                    'company_id': req.company_id.id,
                    'mo_id': req.mo_id.id,
                    'state': 'draft',
                    'line_ids': {},
                    'remark': '%s' % (req.remark or '',),
                    'pr_type': req.pr_type,
                    'unit': req.unit.id,
                    'user_id': req.user_id.id,

                })
            else:
                if req.remark:
                    pr_infos['remark'] = (pr_infos['remark'] or '') + ('\n%s' % (req.remark,))
            for order_line in req.line_ids:
                line_key = make_key(order_line, ('product_id',))
                o_line = pr_infos['line_ids'].setdefault(line_key, {})
                if o_line:
                    # merge the line with an existing line
                    o_line['product_qty'] += order_line.product_qty
                    o_line['note'] = '%s' % (order_line.note or '',)
                    #o_line['inv_qty'] = self.get_inv_qty(order_line.product_id)
                    o_line['price'] = order_line.price
                    if req.drawing_order_id:
                        if req.drawing_order_id.id not in o_line['do_ids']:
                            o_line['do_ids'].append(req.drawing_order_id.id)
                else:
                    # append a new "standalone" line
                    for field in ('product_id','product_qty', 'product_uom_id','supplier_id','erp_no','thickness',
                                  'material','standard','name','description','part_type','name','note','order_line_id'):
                        field_val = getattr(order_line, field)
                        if isinstance(field_val, browse_record):
                            field_val = field_val.id
                        o_line[field] = field_val
                    o_line['do_ids'] = []
                    if req.drawing_order_id:
                        o_line['do_ids'].append(req.drawing_order_id.id)

        allorders = []
        orders_info = {}
        for order_key, (order_data, old_ids, old_big_subassembly_names, drawing_order_ids) in new_reqs.iteritems():
            # skip merges with only one order
            if len(old_ids) < 2:
                allorders += (old_ids or [])
                continue
            for key, value in order_data['line_ids'].iteritems():
                if len(value['do_ids']):
                    if value['note']:
                        value['note'] = 'DO#(%s) %s' % (','.join(str(do_id) for do_id in value['do_ids']),value['note'] or '',)
                    else:
                        value['note'] = 'DO#(%s)' % (','.join(str(do_id) for do_id in value['do_ids']))
                del value['do_ids']
                value.update(dict(key))
            order_data['brief_name'] = 'Full Merged PR'
            order_data['remark'] = _('Merged from:\n%s\n%s') % \
                                   ('\n'.join(old_big_subassembly_names),
                                    (order_data['remark'] or ''),)
            order_data['merged_drawing_order_ids'] = [[6, False, drawing_order_ids]]
            order_data['merged_req_ids'] = [[6, False, old_ids]]
            order_data['line_ids'] = [(0, 0, value) for value in order_data['line_ids'].itervalues()]
            # create the new pr
            newpr_id = self.create(cr, uid, order_data)
            newpr = self.browse(cr, uid, newpr_id)
            self.write(cr, uid, [newpr_id],{'name': '%s-M' %newpr.name})
            orders_info.update({newpr_id: old_ids})
            allorders.append(newpr_id)
            # make triggers pointing to the old orders point to the new order
            for old_id in old_ids:
                wf_service.trg_redirect(uid, 'pur.req', old_id, newpr_id, cr)
                wf_service.trg_validate(uid, 'pur.req', old_id, 'pur_req_cancel', cr)
        return orders_info

    def _get_progress(self, cr, uid, ids, field_names=None, arg=False, context=None):
        if not field_names:
            field_names = []
        if context is None:
            context = {}
        res = {}
        for id in ids:
            res[id] = {}.fromkeys(field_names, 0.0)
        for req in self.browse(cr, uid, ids):
            progress = 0.0
            receive_qty = 0.0
            total_qty = 0.0
            for line in req.line_ids:
                total_qty += line.product_qty
                receive_qty += line.product_reserved_qty
            for po in req.po_ids:
                for po_line in po.order_line:
                    receive_qty += po_line.receive_qty - po_line.return_qty
            if total_qty > 0:
                progress = receive_qty * 100.0 / total_qty
            res[req.id]['progress'] = ceil(progress)
            days_progress = 0
            if req.date_confirm:
                date_now = datetime.now()
                date_confirm = datetime.strptime(req.date_confirm, DEFAULT_SERVER_DATETIME_FORMAT)
                delta = date_now - date_confirm
                days_progress = delta.days
            res[req.id]['days_progress'] = days_progress
        return res

    # def _get_days_progress(self, cr, uid, ids, name, args, context=None):
    #     result = {}
    #     for req in self.browse(cr, uid, ids):
    #         result[req.id] = 0
    #         if req.date_confirm:
    #             date_now = datetime.now()
    #             date_confirm = datetime.strptime(req.date_confirm, DEFAULT_SERVER_DATETIME_FORMAT)
    #             delta = date_now - date_confirm
    #             result[req.id] = delta.days
    #     return result

    # def get_inv_qty(self, product):
    #     qty_available = 0.0
    #     if product.qty_available > product.reserved_qty:
    #         qty_available = product.qty_available - product.reserved_qty
    #     return qty_available

    # def update_inv_qty(self, cr, uid, ids, context=None):
    #     pr_line_obj = self.pool.get('pur.req.line')
    #     for pr in self.browse(cr, uid, ids, context=context):
    #         for line in pr.line_ids:
    #             pr_line_obj.write(cr, uid, [line.id], {
    #                 'inv_qty': self.get_inv_qty(line.product_id),
    #             })
    #     return True

    def update_pdf(self, cr, uid, ids, context=None):
        order_line_obj = self.pool.get('drawing.order.line')
        pr_line_obj = self.pool.get('pur.req.line')
        for pr in self.browse(cr, uid, ids,context=context):
            if pr.drawing_order_id:
                for line in pr.line_ids:
                    if not line.order_line_id:
                        order_line_ids = order_line_obj.search(cr, uid, [
                            ('order_id','=', pr.drawing_order_id.id),
                            ('item_no','=', line.item_no),
                            ('erp_no', '=', line.erp_no),
                            ('part_type','=', line.part_type),
                        ])
                        if order_line_ids:
                            pr_line_obj.write(cr, uid, [line.id], {
                                'order_line_id': order_line_ids[0],
                            })
        return True

    def action_create_grand_pr(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        context2 = context.copy()
        context2.update({'grand_po': True})
        return {
            'name': 'Create Grand PO',
            'res_model': 'pr.generate.po.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context2,
        }

    def action_reserved_products(self, cr, uid, ids, context=None):
        pr_reserve_obj = self.pool.get('pur.req.reserve')
        # Do reserve product
        not_done_ids = self.search(cr, uid, [('id', 'in', ids), ('state', 'in', ['draft','confirmed','approved','in_purchase'])], context=context)
        for req in self.browse(cr, uid, not_done_ids, context=context):
                for line in req.line_ids:
                    # reserved_qty = line.product_qty
                    pr_reserve_obj.reserved_products(cr, uid, line.id, line.product_qty, context=None)
        return True

    def action_unreserved_products(self, cr, uid, ids, context=None):
        pr_reserve_obj = self.pool.get('pur.req.reserve')
        not_done_ids = self.search(cr, uid, [('id','in', ids),('state','=','done')], context=context)
        pr_reserve_obj.unreserved_products(cr, uid, pr_ids=not_done_ids, context=context)
        return self.pool.get('warning').info(cr, uid, title='Information', message=_(
                "%s PRs have been unreserved!")%(len(not_done_ids)))

    def _delete_zero_reserved(self, cr, uid, ids=None, context=None):
        pr_reserve_obj = self.pool.get('pur.req.reserve')
        search_domain = [('product_qty', '=', 0)]
        pr_reserve_ids = pr_reserve_obj.search(cr, uid, search_domain)
        pr_reserve_obj.unlink(cr, uid, pr_reserve_ids)
        return True

    def is_done(self, cr, uid, req_id, context=None):
        for line in req_id.line_ids:
            if line.product_qty_remain != 0.0:
                return False
        return True

    def calculate_available_qty(self, cr, uid, ids, context=None):
        if context is None:
            context= {}
        return {
            'name': 'Calculate PR Available Qty Wizard',
            'res_model': 'calculate.pr.available.qty.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def action_set_supplier(self, cr, uid, ids, context=None):
        return {
            'name': 'Set SupplierWizard',
            'res_model': 'set.pr.line.supplier.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def action_view_purchase(self, cr, uid, ids, context=None):
        return {
            'domain': "[('req_id', 'in', [" + ','.join([str(req_id) for req_id in ids]) + "])]",
            'name': _('Purchase Order'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'purchase.order',
            'type': 'ir.actions.act_window',
            'context': context,
        }

    def action_force_done(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        context.update({'force_done': True})
        return self.action_done(cr, uid, ids, context=context)

    def manual_act_done(self, cr, uid, ids, context=None):
        if context is None:
            context= {}
        return {
            'name': 'Manually Done PR Wizard',
            'res_model': 'manually.done.pr.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def action_archive(self, cr, uid, ids, context=None):
        self.action_force_done(cr, uid, ids, context=context)
        self.action_unreserved_products(cr, uid, ids, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def action_done(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        # pur_req_reserve_obj = self.pool.get('pur.req.reserve')
        # unreserved_ids = []
        done_ids = []
        for req_id in self.browse(cr, uid, ids, context=context):
            if not context.get('force_done', False):
                if self.is_done(cr, uid, req_id,context=context):
                    # unreserved_ids.append(req_id.id)
                    done_ids.append(req_id.id)
            else:
                # unreserved_ids.append(req_id.id)
                done_ids.append(req_id.id)
        # pur_req_reserve_obj.unreserved_products(cr, uid, pr_ids = unreserved_ids)
        self.write(cr, uid, done_ids, {'state': 'done'},context=context)
        self._email_notify(cr, uid, done_ids, 'done', context=context)
        return True

    def wkf_confirm_req(self, cr, uid, ids, context=None):
        res = super(pur_req,self).wkf_confirm_req(cr, uid, ids, context=context)
        self.action_reserved_products(cr, uid, ids, context=context)
        return res

    def wkf_cancel_req(self, cr, uid, ids, context=None):
        res = super(pur_req, self).wkf_cancel_req(cr, uid, ids, context=context)
        pur_req_reserve_obj = self.pool.get('pur.req.reserve')
        pur_req_reserve_obj.unreserved_products(cr, uid, pr_ids=ids)
        return res

    def _get_line_count(self,cr, uid, ids, field_names=None, arg=False, context=None):
        if not field_names:
            field_names = []
        if context is None:
            context = {}
        result = {}
        for id in ids:
            result[id] = {}.fromkeys(field_names, 0)
        for req in self.browse(cr, uid, ids):
            supplier_list = []
            order_supplier_list = []
            in_stock_count = 0
            need_to_order_count = 0
            ordered_count = 0
            po_generated_count = len(req.po_ids)
            for line in req.line_ids:
                if line.supplier_id:
                    if line.supplier_id.id not in supplier_list:
                        supplier_list.append(line.supplier_id.id)
                if line.product_onhand_qty > 0:
                    in_stock_count += 1
                if line.product_qty_remain > 0:
                    need_to_order_count += 1
                    if line.supplier_id:
                        if line.supplier_id.id not in order_supplier_list:
                            order_supplier_list.append(line.supplier_id.id)
            for po in req.po_ids:
                if po.state in ['approved','done']:
                    for line in po.order_line:
                        if line.req_line_id:
                            ordered_count += line.product_qty
            po_need_count = len(order_supplier_list)
            supplier_count = len(supplier_list)
            result[req.id].update({'supplier_count': supplier_count,
                                   'in_stock_count': in_stock_count,
                                   'need_to_order_count': need_to_order_count,
                                   'po_need_count': po_need_count,
                                   'ordered_count': ordered_count,
                                   'po_generated_count': po_generated_count,
                                   'good_need_ordered': '%s/%s'%(need_to_order_count,ordered_count),
                                   'po_need_generated': '%s/%s'%(po_need_count,po_generated_count),
                                   })
        return result

    def _get_req_ids_from_req_line(self, cr, uid, ids, context=None):
        result = {}
        pur_req_line_obj = self.pool.get('pur.req.line')
        for line in pur_req_line_obj.browse(cr, uid, ids, context=context):
            result[line.req_id.id] = True
        return result.keys()

    def _get_amount_total(self, cr, uid, ids, name, args, context):
        result = {}
        for req in self.browse(cr, uid, ids,context=context):
            amount = 0.0
            for line in req.line_ids:
                amount += line.amount_total
            result[req.id] = amount
        return result

    _columns = {
        'urgent': fields.boolean('Urgent'),
        'brief_name': fields.char('Brief Name (简称) ',size=128,readonly=True),
        #'req_reserved_ids': fields.one2many('pur.req.reserve','req_id',string='Reserved Products',readonly=True),
        'product_id': fields.related('line_ids', 'product_id', type='many2one', relation='product.product',
                                     string='Product'),
        'supplier_id': fields.related('line_ids', 'supplier_id', type='many2one', relation='res.partner',
                                     string='Supplier'),
        'pr_type': fields.selection(PR_TYPES,string='PR Type', states={'draft': [('readonly', False)]}, readonly=True),
        'drawing_order_id': fields.many2one('drawing.order','Drawing Order',readonly=True),
        'merged_drawing_order_ids': fields.many2many('drawing.order', 'merged_pr_drawing_order_rel','pr_id','order_id',string='Merged DOs',),
        'merged_req_ids': fields.many2many('pur.req', 'merged_pr_pr_rel', 'pr_id',
                                                     'merged_pr_id', string='Merged PRs', ),
        'date_create': fields.datetime('Created Date', readonly=True, help='Date, when this document has been created'),
        'date_confirm': fields.datetime('Confirm Date', readonly=True),
        'mo_id': fields.many2one('mrp.production', 'Manufacturer Order'),
        'sale_product_ids': fields.related('mo_id', 'mfg_ids', type="many2many", relation="sale.product",
                                           string="Unit IDs"),
        #'bigsubassembly_id': fields.related('drawing_order_id','product_id',type='many2one',relation='product.product',
        #                                    string='Big Sub Assembly',readonly=True,store=True),
        'bigsubassembly_id': fields.many2one('product.product', 'Big Sub Assembly',readonly=True),
        #'unit': fields.many2one('product.product','Unit',readonly=True),
        'unit': fields.related('mo_id','product_id',type='many2one',relation='product.product',string='Unit',readonly=True,store=True),
        'is_full_pr': fields.boolean('Is Full PR or Sub-Assembly?'),
        'engineer': fields.many2one('res.users','Engineer',),
        'assigned_to': fields.many2one('res.users','Assigned To',),
        'delivery_date': fields.date('Delivery date (ETA)', help="Scheduled date filled by Purchaser (when he can deliver the goods)"),
        'progress': fields.function(_get_progress, multi='_get_progress', string='Progress',type="float",readonly=True),
        'days_progress': fields.function(_get_progress, multi='_get_progress', string='Days in progress',type="float",readony=True),
        #'history_ids': fields.one2many('pur.req.history','pur_req_id','History',ondelete='cascade',readonly=True),
        'move1_lines': fields.one2many('pur.req.move1','pur_req_id','Move1 Lines',ondelete='cascade',readonly=True),
        'move2_lines': fields.one2many('pur.req.move2','pur_req_id','Move2 Lines',ondelete='cascade',readonly=True),
        'move3_lines': fields.one2many('pur.req.move3','pur_req_id','Move3 Lines',ondelete='cascade',readonly=True),
        'supplier_count': fields.function(_get_line_count,string='Supplier count',type='integer',readonly=True,multi="line_count"),
        'in_stock_count': fields.function(_get_line_count, string='In Stock count', type='integer', readonly=True,multi="line_count"),
        'need_to_order_count': fields.function(_get_line_count, string='Need to order count', type='integer', readonly=True,
                                          multi="line_count"),
        'ordered_count': fields.function(_get_line_count, string='Ordered Count', type='integer',
                                               readonly=True,
                                               multi="line_count"),
        'po_need_count': fields.function(_get_line_count, string='Need to generate PO count', type='integer', readonly=True,
                                          multi="line_count"),
        'po_generated_count': fields.function(_get_line_count, string='Generated PO count', type='integer',
                                         readonly=True,
                                         multi="line_count"),
        'good_need_ordered': fields.function(_get_line_count, string='Good Need/Ordered', type='char',
                                              readonly=True,
                                              multi="line_count"),
        'po_need_generated': fields.function(_get_line_count, string='PO Need/Generated', type='char',
                                              readonly=True,
                                              multi="line_count"),
        'amount_total': fields.function(_get_amount_total, string='Total Amount', type="float",
                                        digits_compute=dp.get_precision('Product Unit of Measure'),
                                        readonly=True,
                                        store={
                                            _name: (lambda self, cr, uid, ids, context: ids,None,10),
                                            'pur.req.line': (_get_req_ids_from_req_line,None,10),
                                        },track_visibility='always'),
        'rfq_sent': fields.boolean('RFQ Email Sent',readonly=True),
        "available_qty_rule": fields.selection(PR_AVAILABLE_QTY_RULE, string='Available Qty Rule', readonly=True),
        # 'generation_rule': fields.selection(PO_GENERATION_SELECTION, string='Generation Rule',required=True),

    }
    _defaults = {
        'rfq_sent': False,
        'pr_type': 'normal',
        'date_create': lambda *a: datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        # 'generation_rule': 'BASE_ON_STOCK_IGNORE_RESERVED',
        'available_qty_rule': 'REGARD_AVAILABLE_INCOMING'
    }


    def print_pr_mfg(self, cr, uid, ids, context):
        #mod_obj = self.pool.get('ir.model.data')
        #res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'view_print_pr_mfg_wizard')
        #res_id = res and res[1] or False
        #return {
        #    'name': 'Print PR List',
        #    'res_model': 'print.pr.mfg.wizard',
        #    'type': 'ir.actions.act_window',
        #    'view_type': 'form',
        #    'view_mode': 'form',
        #    'view_id': [res_id],
        #    'context': {'pr_ids': ids},
        #    'target': 'new'
        #}
        datas = {
            'model': 'pur_req',
            'ids': ids,
        }
        context.update({'type': 'all'})
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'pr.mfg.form',
            'datas': datas,
            'nodestroy': True,
            'context': context
        }

    def create(self, cr, uid, vals, context=None):
        result = super(pur_req, self).create(cr, uid, vals, context=context)
        if result:
            req = self.browse(cr, uid, result,context=context)
            if req.pr_type == 'mfg':
                self.write(cr, uid, [result],{'name': '%s-MFG'%req.name})
            elif req.pr_type == 'mfg_pms':
                self.write(cr, uid, [result], {'name': '%s-PMS' % req.name})
            elif req.pr_type == 'mfg_pml':
                self.write(cr, uid, [result], {'name': '%s-PML' % req.name})
            elif req.pr_type == 'mfg_o':
                self.write(cr, uid, [result], {'name': '%s-MFG-O' % req.name})
            elif req.pr_type == 'canada':
                self.write(cr, uid, [result], {'name': '%s-CAN' % req.name})
            self._email_notify(cr, uid, [result],mail_type='created', context=context)
        return result

    def update_product_price(self, cr, uid, ids, context=None):
        pr_line_obj = self.pool.get('pur.req.line')
        for pr in self.browse(cr, uid, ids, context=context):
            if pr.state in ['draft','confirmed','approved']:
                for line in pr.line_ids:
                    if line.product_id and line.price == 0.0:
                        price = self.get_product_purchase_price(cr, uid, line.product_id, line.part_type,search_purchase_order=True)
                        if price > 0.0:
                            pr_line_obj.write(cr, uid, [line.id],{'price': price},context=context)

        return True

    def get_product_purchase_price(self, cr, uid, product, part_type, search_purchase_order=False):
        price = 0.0
        if product:
            price = product.uom_po_price
            if part_type in ['PMS', 'PML']:
                price = product.standard_price
            if price == 0.0 and search_purchase_order == True:
                po_line_obj = self.pool.get('purchase.order.line')
                po_line_ids = po_line_obj.search(cr, uid, [('product_id','=',product.id)],order='date_planned desc')
                if po_line_ids:
                    result = po_line_obj.read(cr, uid, po_line_ids, ['price_unit'])
                    if result:
                        price = result[0]['price_unit']
        return price

    def _check_state(self, cr, uid, ids=None, context=None):
        pr_states = ['draft',
                      'confirmed',
                      'approved',
                      'rejected',
                      'in_purchase',
                      'done',
                      'cancel']

        pr_ids = self.search(cr, uid, [('state', 'not in', pr_states)], context=context)
        self.write(cr, uid, pr_ids, {'state': 'in_purchase'}, context=context)
        return True

    def _check_pr_po_link(self, cr, uid, ids=None, context=None):
        po_obj = self.pool.get('purchase.order')
        po_line_obj = self.pool.get('purchase.order.line')
        req_line_obj = self.pool.get('pur.req.line')
        po_ids = po_obj.search(cr, uid, [('state','in',['draft','sent','confirmed','approved']),
                                         ('req_id','!=',False)], context=context)
        for po in po_obj.browse(cr, uid, po_ids,  context=context):
            for line in po.order_line:
                if not line.req_line_id:
                    req_line_ids = req_line_obj.search(cr, uid, [('req_id','=',po.req_id.id),
                                                                 ('product_id','=',line.product_id.id)], context=context)
                    if req_line_ids:
                        po_line_obj.write(cr, uid, [line.id], {'req_line_id': req_line_ids[0]}, context=context)
                else:
                    break



    def write(self, cr, uid, ids, vals, context=None):
        if not type(ids) is list:
            ids = [ids]
        if vals.get('state',False) == 'confirmed':
            vals.update({'date_confirm': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        result = super(pur_req, self).write(cr, uid, ids, vals, context=context)
        return result

    def update_move_lines_req(self, cr, uid, req_ids, context=None):
        req_move1_obj = self.pool.get('pur.req.move1')
        req_move2_obj = self.pool.get('pur.req.move2')
        req_move3_obj = self.pool.get('pur.req.move3')
        purchase_order_line_obj = self.pool.get('purchase.order.line')
        for req in self.browse(cr, uid, req_ids, context=context):
            req_po_ids = [req_po.id for req_po in req.po_ids]
            for req_line in req.line_ids:
                move1_qty = 0
                move2_qty = 0
                move3_qty = 0
                po_line_ids = purchase_order_line_obj.search(cr, uid, [
                    ('order_id', 'in', req_po_ids),
                    ('product_id', '=', req_line.product_id.id)
                ])
                for po_line in purchase_order_line_obj.browse(cr, uid, po_line_ids, context=context):
                    if po_line.state in ['draft', 'sent']:
                        move1_qty += po_line.product_qty
                    if po_line.state in ['confirmed']:
                        move2_qty += po_line.product_qty
                    if po_line.state in ['approved']:
                        move3_qty += po_line.product_qty - po_line.receive_qty
                move1_ids = req_move1_obj.search(cr, uid, [('pur_req_id', '=', req.id),
                                                           ('product_id', '=', req_line.product_id.id)])
                if move1_ids:
                    if move1_qty > 0:
                        req_move1_obj.write(cr, uid, move1_ids, {'quantity': move1_qty})
                    else:
                        req_move1_obj.unlink(cr, uid, move1_ids)
                elif move1_qty > 0:
                    req_move1_obj.create(cr, uid, {
                        'pur_req_id': req.id,
                        'quantity': move1_qty,
                        'erp_no': req_line.product_id.default_code,
                        'product_id': req_line.product_id.id,
                    })
                move2_ids = req_move2_obj.search(cr, uid, [('pur_req_id', '=', req.id),
                                                           ('product_id', '=', req_line.product_id.id)])
                if move2_ids:
                    if move2_qty > 0:
                        req_move2_obj.write(cr, uid, move2_ids, {'quantity': move2_qty})
                    else:
                        req_move2_obj.unlink(cr, uid, move2_ids)
                elif move2_qty > 0:
                    req_move2_obj.create(cr, uid, {
                        'pur_req_id': req.id,
                        'quantity': move2_qty,
                        'erp_no': req_line.product_id.default_code,
                        'product_id': req_line.product_id.id,
                    })
                move3_ids = req_move3_obj.search(cr, uid, [('pur_req_id', '=', req.id),
                                                           ('product_id', '=', req_line.product_id.id)])
                if move3_ids:
                    if move3_qty > 0:
                        req_move3_obj.write(cr, uid, move3_ids, {'quantity': move3_qty})
                    else:
                        req_move3_obj.unlink(cr, uid, move3_ids)
                elif move3_qty > 0:
                    req_move3_obj.create(cr, uid, {
                        'pur_req_id': req.id,
                        'quantity': move3_qty,
                        'erp_no': req_line.product_id.default_code,
                        'product_id': req_line.product_id.id,
                    })

    def update_move_lines(self, cr, uid, po_ids, context=None):
        req_ids = []
        purchase_order_obj = self.pool.get('purchase.order')
        for order in purchase_order_obj.browse(cr, uid, po_ids, context=context):
            if order.req_id:
                if not order.req_id.id in req_ids:
                    req_ids.append(order.req_id.id)
        self.update_move_lines_req(cr, uid, req_ids, context=context)

    def _get_drawing_order_line_ids(self, cr, uid, ids, context=None):
        pur_req_line_obj = self.pool.get('pur.req.line')
        line_ids = pur_req_line_obj.search(cr, uid, [('req_id', 'in', ids), ('order_line_id', '!=', False)],
                                           context=context)
        line_datas = pur_req_line_obj.read(cr, uid, line_ids, ['order_line_id'], context=context)
        order_line_ids = [line['order_line_id'][0] for line in line_datas]
        return order_line_ids

    def print_pdf_zip(self, cr, uid, ids, context=None):
        order_line_ids = self._get_drawing_order_line_ids(cr, uid, ids, context=None)
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        return drawing_order_line_obj.print_pdf_zip(cr, uid, order_line_ids, context=context)

    def print_dxf(self, cr, uid, ids, context):
        order_line_ids = self._get_drawing_order_line_ids(cr, uid, ids, context=None)
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        return drawing_order_line_obj.print_dxf(cr, uid, order_line_ids, context=context)

pur_req()

