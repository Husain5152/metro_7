# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp.osv import fields,osv
import openerp.addons.decimal_precision as dp
from math import floor


class plate_material(osv.osv):
    _name = "plate.material"
    _description = "Plate Material"
    _order = "product_id"
    _inherit = ['mail.thread']
#    def _prod_qty(self, cr, uid, ids, fields, args, context=None):
#        result = {}
#        prod_obj = seld.pool.get("product.product")
#        for line in self.browse(cr, uid, ids, context=ids):
#            result[id] = {'on_order_qty':0}
#            line.product_id.incoming_qty
        
    _columns = {
        'product_id': fields.many2one('product.product','Product', required=True),
        'plate_whole_qty': fields.integer('Whole Quantity of Plate', required=True, track_visibility='onchange'),
#        'on_order_qty': fields.function(_prod_qty,type='float',string='On Order Quantity',digits_compute=dp.get_precision('Product Unit of Measure'),multi=prod_qty),
        'on_order_qty': fields.related('product_id','incoming_qty',type='integer',string='On Order Quantity',readonly=True),
        'notes': fields.text('Notes'),        
        'product_name': fields.related('product_id','name',type='char',string='Product Name'),
    }
    _sql_constraints = [
        ('product_uniq', 'unique(product_id)', 'Product must be unique!'),
    ]

    def update_plate_whole_qty(self, cr, uid, prod_id, change_qty, context=None):
        if not prod_id or int(change_qty) == 0:
            return
        change_qty = int(change_qty)
        #check if this product need to generate whole quantity records
        prod_data = self.pool.get('product.product').browse(cr, uid, prod_id, context=context)
        cate_ids = self.pool.get('ir.config_parameter').get_param(cr, uid, 'stock.plate.wholeqty.category_id', context=context)
        if not cate_ids:
            return
        cate_ids_list = cate_ids.split(',')
        categ_id = '%s'%prod_data.categ_id.id
        if categ_id not in cate_ids_list:
            return        
        
        plate_obj = self.pool.get("plate.material")
        plate_ids = plate_obj.search(cr, uid, [('product_id','=',prod_id)])
        if plate_ids and len(plate_ids) > 0:
            #if found then decrease the whole quantity of plate
            plate = plate_obj.browse(cr, uid, plate_ids[0], context=context)
            plate_obj.write(cr, uid, plate_ids[0], {'plate_whole_qty':plate.plate_whole_qty + change_qty})
        else:
            #If no this product, then do creation
            qty_available = self.pool.get('product.product').read(cr, uid, [prod_id], ['qty_available'],context=context)[0]['qty_available']
            vals = {'product_id':prod_id, 'plate_whole_qty':floor(qty_available) + change_qty, 'notes':'Generated when finish CNC work order line or stock-in order automatically'}
            plate_obj.create(cr, uid, vals, context=context) 
                
class stock_move(osv.osv):
    _inherit="stock.move"
    def action_done(self, cr, uid, ids, context=None):
        resu = super(stock_move,self).action_done(cr, uid, ids, context=context)
        for move in self.browse(cr, uid, ids, context=context):
            if move.type != 'in':
                continue
            #increase the plate material whole quantity
            move['product_qty']
            self.pool.get('plate.material').update_plate_whole_qty(cr, uid, move.product_id.id, move['product_uom_base_qty'], context=context)
        return resu
        