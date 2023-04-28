# -*- encoding: utf-8 -*-
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re
from openerp.osv import fields, osv
from openerp import netsvc
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools import float_compare
import logging
import openerp.addons.decimal_precision as dp


class cleanup_product_merge(osv.osv):
    _name = 'cleanup.product.merge'
    _description = 'Product Merge'
    _inherit = ['mail.thread']
    _columns = {
        'name': fields.char('Name', required=True),
        'location_id': fields.many2one('stock.location','Location', help='Location to update merged products quantity', required=True),
        'line_ids': fields.one2many('cleanup.product.merge.line', 'merge_id', string='Products To Merge'),
        'create_uid': fields.many2one('res.users', 'Creator', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True),
        'state': fields.selection([('draft','Draft'),
                                   ('done','Done')], string='States'),

    }
    def search_similar(self, cr, uid, ids, context=None):
        product_obj = self.pool.get('product.product')
        for merge_doc in self.browse(cr, uid, ids, context=context):
            similar_product_ids = {}
            product_ids = [line.product_id.id for line in merge_doc.line_ids]
            for line in merge_doc.line_ids:
                name_words = re.split('\s+', line.product_id.name)
                cn_name_words = re.split('\s+', line.product_id.cn_name)
                result_product_ids = product_obj.search(cr, uid, [('id','not in', product_ids),
                                                               '|',('name', 'ilike','%'.join(name_words)),
                                                               ('cn_name','ilike','%'.join(cn_name_words))], context=context)
                for product_id in result_product_ids:
                    similar_product_ids.update({product_id: True})
            merge_product_vals = []
            for similar_product_id in similar_product_ids.keys():
                merge_product_vals.append([(0,0,{'product_id': similar_product_id})])
            if merge_product_vals:
                self.write(cr, uid, ids, {'line_ids': merge_product_vals}, context=context)
        return True

    def run_merge(self,cr, uid, ids, context=None):
        product_obj = self.pool.get('product.product')
        deactive_product_ids = []
        all_deactive_erps = []
        for merge_doc in self.browse(cr, uid, ids, context=context):
            move_qty = 0
            active_products = []
            all_deactive_erps = []
            deactive_erps = []
            active_erps = []
            for line in merge_doc.merge_product_ids:
                if line.active:
                    active_products.append(line.product_id)
                    active_erps.append(line.product_id.default_code)
                else:
                    all_deactive_erps.append(line.product_id.default_code)
                    deactive_erps.append(line.product_id.default_code)
                    move_qty += line.qty_available
            if len(active_products) > 1:
                raise osv.osv_except('Error', 'Can not have 2 active products!')
            if len(deactive_erps) == 0:
                raise osv.osv_except('Error', 'Nothing to merge!')
            if move_qty > 0:
                inventory_vals = {
                    'name': 'Merge %s to %s'%(','.join(deactive_erps), active_erps[0]),
                    'comments': 'Update inventory due to merge products',
                    'inventory_id': [[0,0,{
                        'product_id': active_products[0].id,
                        'product_uom': active_products[0].uom_id.id,
                        'product_qty': move_qty,
                        'location_id': merge_doc.location_id.id
                    }]]
                }
                inventory_obj = self.pool.get('stock.inventory')
                inventory_id = inventory_obj.create(cr, uid, inventory_vals, context=context)
                inventory_obj.action_confirm(cr, uid, [inventory_id], context=context)
                inventory_obj.action_done(cr, uid, [inventory_id], context=context)
        product_obj.write(cr, uid, deactive_product_ids, {'active': False}, context=context)
        self.write(cr, uid, ids, {'state': 'done'}, context=context)
        self.message_post(cr, uid, ids, body='Merge Product %s successfully'%','.join(all_deactive_erps), context=context)
        return True

    _defaults = {
        'state': 'draft',
    }

class cleanup_product_merge_line(osv.osv):
    _name = 'cleanup.product.merge.line'
    _description = 'Cleanup Product Lines'
    _columns = {
        'merge_id': fields.many2one('cleanup.product.merge', 'Product Merge', ondelete='cascade'),
        'product_id': fields.many2one('product.product', 'Product', required=True),
        'quantity': fields.related('product_id','qty_available', type='float', digits_compute=dp.get_precision('Product Unit of Measure'), string='Available Qty', help="Stock on hand quantity", readonly=True),
        'active': fields.boolean('Active?',help='Check to keep this product, others will be deactive'),
    }