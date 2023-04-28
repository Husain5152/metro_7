# -*- encoding: utf-8 -*-
from openerp.osv import fields,osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT,DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime

class pur_req_reserve(osv.osv):
    _name = "pur.req.reserve"
    _description = "Purchase Requisition Reserve"
    _inherit = ['mail.thread']
    _columns = {
        'reserved_date': fields.date(string='Reserved Date'),
        'req_id': fields.many2one('pur.req','Purchase Requisition', ondelete='cascade'),
        'req_line_id': fields.many2one('pur.req.line','PR Line', ondelete='cascade'),
        'product_id': fields.many2one('product.product','Product'),
        'sale_product_ids': fields.related('req_id', 'sale_product_ids', type="many2many", relation="sale.product",
                                           string="Unit IDs"),
        'product_qty': fields.float('Reserved Quantity'),
        'location_id': fields.many2one("stock.location", string="Location"),
    }
    def view_reserved_infor_products(self, cr, uid, product_ids, context=None):
        if product_ids:
            mod_obj = self.pool.get('ir.model.data')
            res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'view_reserved_list_wizard')
            res_id = res and res[1] or False
            context2 = context.copy()
            context2.update({'active_model': 'product.product', 'active_id': product_ids[0], 'active_ids': product_ids})
            return {
                'name': 'Reserved PR Infors',
                'res_model': 'reserved.list.wizard',
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [res_id],
                'context': context2,
                'target': 'new'
            }
        return False

    def get_reserved_qty_except(self, cr, uid, req_id, product_id, context=None):
        qty = 0
        pur_req_line_obj = self.pool.get('pur.req.line')
        req_line_ids = pur_req_line_obj.search(cr, uid, [('req_id', '=', req_id)], context=context)
        reserved_ids = self.search(cr, uid, [('product_id','=',product_id),'|',('req_id','=',req_id),
                                             ('req_line_id','in',req_line_ids)], context=context)
        reserved_line_values = self.read(cr, uid, reserved_ids, ['product_qty'], context=context)
        for reserved_line_value in reserved_line_values:
            qty += reserved_line_value['product_qty']
        return qty

    def view_reserved_infor(self, cr, uid, req_line_ids, context=None):
        if not context:
            context={}
        if isinstance(req_line_ids, (int, long)):
            req_line_ids = [req_line_ids]
        product_ids = []
        pr_line_obj = self.pool.get('pur.req.line')
        for pr_line in pr_line_obj.browse(cr, uid, req_line_ids, context=context):
            product_ids.append(pr_line.product_id.id)
        return self.view_reserved_infor_products(cr, uid, product_ids, context=context)

    def reserved_products(self, cr, uid, req_line_id, quantity, context=None):
        pr_line_obj = self.pool.get('pur.req.line')
        req_line = pr_line_obj.browse(cr, uid, req_line_id, context=context)
        if req_line:
            pr = req_line.req_id
            reserved_ids = self.search(cr, uid, [('req_line_id','=',req_line.id)], context=None)
            vals = {'req_id': pr.id,
                    'req_line_id': req_line.id,
                    'reserved_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                    'product_id': req_line.product_id.id,
                    'location_id': pr.warehouse_id.lot_stock_id.id,
                    'product_qty': quantity,
                    }
            if not reserved_ids:
                reserved_id = self.create(cr, uid, vals, context=context)
            else:
                reserved_id = reserved_ids[0]
                reserve = self.browse(cr, uid, reserved_id, context=context)
                vals.update({'product_qty': quantity + reserve.product_qty})
                self.write(cr, uid, [reserved_id], vals, context=context)
            pr_line_obj.write(cr, uid, [req_line_id], {
                'product_reserved_qty': quantity + req_line.product_reserved_qty,
                'reserved_id': reserved_id,
            })

        return reserved_id

    def unreserved_products(self, cr, uid, pr_ids=None, line_ids=None, product_ids=None, context=None):
        pr_reserve_obj = self.pool.get('pur.req.reserve')
        search_domain = []
        reserved_domain = []
        pur_req_line_obj = self.pool.get('pur.req.line')
        if pr_ids:
            search_domain.append(('req_id', 'in', pr_ids))
            reserved_domain.append(('req_id', 'in', pr_ids))
        if line_ids:
            search_domain.append(('req_line_id', 'in', line_ids))
            reserved_domain.append(('id', 'in', line_ids))
        if product_ids:
            search_domain.append(('product_id','in',product_ids))
            reserved_domain.append(('product_id', 'in', product_ids))

        unreserved_line_ids = pur_req_line_obj.search(cr, uid, reserved_domain, context=context)
        pur_req_line_obj.write(cr, uid, unreserved_line_ids, {'product_reserved_qty': 0}, context=context)
        pr_reserve_ids = pr_reserve_obj.search(cr, uid, search_domain, context=context)
        pr_reserve_obj.unlink(cr, uid, pr_reserve_ids)


pur_req_reserve()

class product_product(osv.osv):
    _inherit = 'product.product'

    def _reserved_qty(self, cr, uid, ids, field_names=None, arg=False, context=None):
        res = super(product_product,self)._reserved_qty(cr, uid, ids, field_names=field_names,arg=arg,context=context)
        for prod in self.browse(cr, uid, ids,context=context):
            cr.execute('SELECT COALESCE(SUM(product_qty),0) as quantity FROM pur_req_reserve WHERE product_id = %s',(prod.id,))
            row = cr.fetchone()
            reserved_qty = row[0]
            res[prod.id] = reserved_qty
        return res

    def _get_mfg_id_products(self, cr, uid, ids, context=None):
        return super(product_product,self)._get_mfg_id_products(cr, uid, ids, context=context)

    def _get_pur_req_products(self, cr, uid, ids, context=None):
        res = set()
        for pr_reserve in self.browse(cr, uid, ids, context=context):
            res.add(pr_reserve.product_id.id)
        return res

    _columns={
                'reserved_qty': fields.function(_reserved_qty, string="Reserved Quantity", type="float",
                     store = {
                         'mfg.id.reserve': (_get_mfg_id_products, ['product_id', 'product_qty'], 10),
                         'pur.req.reserve': (_get_pur_req_products, ['product_id', 'product_qty'], 20),
                     }
                     , digits_compute=dp.get_precision('Product Unit of Measure')),
                'pr_reserved_ids': fields.one2many('pur.req.reserve','product_id',string='PR Reserved',readonly=True),
              }