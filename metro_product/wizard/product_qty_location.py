# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
import openerp.addons.decimal_precision as dp

class product_qty_location(osv.osv_memory):
    _name = 'product.qty.location'
    _description = 'Product Qty Location'
    _columns = {
        'product_id': fields.many2one('product.product','Product',readonly=True),
        'qty_location_ids': fields.one2many('product.qty.location.line','wizard_id',
                                          string='Quantity Details', readonly=True),
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(product_qty_location, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        record_model = context and context.get('active_model', False) or False
        if record_id and record_model == 'product.product':
            res.update({'product_id': record_id})
            product_obj = self.pool.get('product.product')
            warehouse_obj = self.pool.get('stock.warehouse')
            wids = warehouse_obj.search(cr, uid, [], context=context)
            if wids:
                line_vals = []
                location_ids = product_obj._get_locations_from_context(cr, uid, [record_id], context=context)
                # for w in warehouse_obj.browse(cr, uid, wids, context=context):
                #    location_id = w.lot_stock_id.id
                for location_id in location_ids:
                    c = context.copy()
                    c.update({'location': [location_id],
                                        'states': ('done',),
                                        'what': ('in', 'out')
                                        })
                    stock = product_obj.get_product_available(cr, uid, [record_id], context=c)
                    product_qty = stock.get(record_id, 0.0)
                    line_vals.append((0,0,{
                        'location_id': location_id,
                        'product_qty': product_qty
                    }))
                res.update({'qty_location_ids': line_vals})
        return res

class product_qty_location_line(osv.osv_memory):
    _name = 'product.qty.location.line'
    _description = 'Product Qty Location Line'
    _columns = {
        'wizard_id': fields.many2one('product.qty.location', string='Wizard', ondelete='cascade'),
        'location_id': fields.many2one('stock.location', string='Location', readonly=True),
        'product_qty': fields.float('Onhand Qty', digits_compute= dp.get_precision('Product Unit of Measure'), readonly=True)
    }




