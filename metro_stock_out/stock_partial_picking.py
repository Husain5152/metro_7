# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP SA (<http://openerp.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
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

from openerp.osv import fields, osv
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _

class stock_partial_picking_line(osv.TransientModel):
    _inherit = "stock.partial.picking.line"
    _columns = {
        'quantity_max' : fields.float("Max Quantity", digits_compute=dp.get_precision('Product Unit of Measure'), required=True),
        'quantity_out_available' : fields.float("Avail Quantity", digits_compute=dp.get_precision('Product Unit of Measure'), required=True),
        'pick_type': fields.selection([('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal')], 'Shipping Type', required=True, select=True, help="Shipping type specify, goods coming in or going out."),
        'state': fields.char('Move State', size=8)
    }

class stock_partial_picking(osv.osv_memory):
    _inherit = "stock.partial.picking"
    
    def _partial_move_for(self, cr, uid, move):
        partial_move = super(stock_partial_picking, self)._partial_move_for(cr, uid, move)
        #for the internal/out picking, need control the available out quantity        
        if move.picking_id.type in('internal', 'out'):            
            prod_id = move.product_id.id
            prod_obj = self.pool.get('product.product')
            #get on hand quantity
            c = {'location':move.location_id.id, 'states': ('done',), 'what': ('in', 'out')}
            stock = prod_obj.get_product_available(cr, uid, [prod_id], context=c)
            qty_onhand = stock.get(prod_id, 0.0)
            #get assigned outgoing quantity  
            c = {'location':move.location_id.id, 'states': ('assigned',), 'what': ('out')}
            stock = prod_obj.get_product_available(cr, uid, [prod_id], context=c)
            qty_out_assigned = abs(stock.get(prod_id, 0.0))
            #if curreny move is assigned then need to subtract it
            if move.state == 'assigned':
                qty_out_assigned -= move.product_qty
            #get quantity
            quantity = min(partial_move['quantity'], qty_onhand - qty_out_assigned)
            
            partial_move.update({'quantity': quantity,'quantity_out_available':qty_onhand - qty_out_assigned})
            
        #the max quantity that user can deliver and the picking type
        partial_move.update({'quantity_max':move.product_qty, 'pick_type':move.picking_id.type, 'state':move.state})
        return partial_move

    def do_partial(self, cr, uid, ids, context=None):
        partial = self.browse(cr, uid, ids[0], context=context)
        picking_type = partial.picking_id.type
        for wizard_line in partial.move_ids:
            #user deliver quantity can not be larger than the stock move's original quantity
            if wizard_line.quantity > wizard_line.quantity_max:
                raise osv.except_osv(_('Error!'), _('[%s]%s, quantity %s is larger than the original quantity %s') % (wizard_line.product_id.default_code, wizard_line.product_id.name, wizard_line.quantity,  wizard_line.quantity_max))
            #for the internal/out picking, the  deliver quantity can not be larger than the available quantity
            if picking_type in('internal', 'out') and wizard_line.quantity > wizard_line.quantity_out_available:
                raise osv.except_osv(_('Error!'), _('[%s]%s, quantity %s is larger than the available quantity %s') % (wizard_line.product_id.default_code, wizard_line.product_id.name, wizard_line.quantity,  wizard_line.quantity_out_available))
            
        return super(stock_partial_picking,self).do_partial(cr, uid, ids, context=context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
