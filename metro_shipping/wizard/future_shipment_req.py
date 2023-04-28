# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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


from openerp.osv import osv,fields

import openerp.addons.decimal_precision as dp

from openerp import netsvc
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

from openerp.tools.translate import _

from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP

class future_ship_req_line(osv.osv_memory):
    _name = "future.ship.req.line"
    _columns = {
        'wizard_id' : fields.many2one('future.ship.requi', string="Wizard"),
        'product_id': fields.many2one('product.product', 'Product' ,required=False),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),required=True),
        'product_qty_remain': fields.float('Quantity Remain', digits_compute=dp.get_precision('Product Unit of Measure'),required=True),
        'future_ship_line_id':fields.many2one('future.shipment.line', 'Future shipment line'),
        'notes':fields.text('Description'),
    }
    def default_get(self, cr, uid, fields, context=None):pass
       
    
    def _check_product_qty(self, cursor, user, ids, context=None):
        for line in self.browse(cursor, user, ids, context=context):
            if line.product_qty > line.product_qty_remain:
                prod_name = line.product_id and (line.product_id.default_code + '-' + line.product_id.name) or line.notes
                raise osv.except_osv(_('Warning!'), _("Product '%s' max ship quantity is %s, you can not ship %s"%(prod_name, line.product_qty_remain, line.product_qty)))
            if line.product_qty <= 0:
                raise osv.except_osv(_('Warning!'), _("Product '%s' ship quantity must be greater than zero!"%(line.product_id.default_code + '-' + line.product_id.name)))
        return True    
            
    _constraints = [(_check_product_qty,'Product quantity exceeds the remaining quantity',['product_qty'])]
        
future_ship_req_line()

class future_ship_req(osv.osv_memory):
    _name = 'future.ship.requi'
    _columns = {
            
            'real_ship_id': fields.many2one('shipment.shipment', 'Shipment', required=False),    
            'line_ids' : fields.one2many('future.ship.req.line', 'wizard_id', 'Products'),
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
        line_data = []
        if context is None:
            context = {}
        res = super(future_ship_req, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        future_ship_obj = self.pool.get('future.shipment')
        future_ship = future_ship_obj.browse(cr, uid, record_id, context=context)
        for line in future_ship.line_ids:
            line_data.append({'product_id': line.product_id.id, 
                                  'product_qty': line.product_qty, 
                                  'product_qty_remain': line.product_qty,
                                  'future_ship_line_id':line.id,#if it is an object rather than string, ".id" is required
                                  'notes':line.notes,
                                })
        res['line_ids'] = line_data
        return res
        
    def do_ship(self, cr, uid, ids, context=None):
        '''
        This method also include the split button function
        '''
        record_id = context and context.get('active_id', False) or False#
        future_ship = self.pool.get('future.shipment').browse(cr, uid, record_id, context=None);
        future_ship_line_obj = self.pool.get("future.shipment.line")
        future_ship_obj = self.pool.get("future.shipment")
        #the  lines that partial shipped or not shipped, need to create a new future shipment based on them
        #{id:remain_qty}
        remain_future_ship_line_ids = dict((line.id,line.product_qty) for line in future_ship.line_ids)
        data =  self.browse(cr, uid, ids, context=context)[0]
        #loop user selected product lines, to update the products need to remain
        for line in data.line_ids:
            future_line_id = line.future_ship_line_id.id
            if not remain_future_ship_line_ids.has_key(future_line_id):
                #user delete at the wizard, need to keep this on remaining list
                continue
            elif line.product_qty_remain > line.product_qty:
                #user changed quantity, need update the remaining quantity
                remain_future_ship_line_ids[future_line_id] = line.product_qty_remain - line.product_qty
            else:
                #user selected this product fully, then need remove it from the remaining list
                remain_future_ship_line_ids.pop(future_line_id)
                
        #create new future shipment based on the remaining products
        new_future_ship_id = None
        if remain_future_ship_line_ids:
            context['__copy_data_seen'] = {}
            new_future_ship_data = future_ship_obj.copy_data(cr, uid, record_id, context=context)
            new_future_ship_data['line_ids'] = None
            new_future_ship_data['code'] = self.pool.get('ir.sequence').get(cr, uid, 'future.shipment') or '/'               
            new_future_ship_id = future_ship_obj.create(cr, uid, new_future_ship_data, context=context)
            for line_id, qty in remain_future_ship_line_ids.items():
                qty_old = future_ship_line_obj.read(cr, uid, line_id, ['product_qty'], context=context)['product_qty']
                if qty == qty_old:
                    #remain fully, then update shipment_id direct, switch the line to new future shipment
                    future_ship_line_obj.write(cr, uid, line_id, {'shipment_id':new_future_ship_id},context=context)
                else:
                    #remain partial
                    context['__copy_data_seen'] = {}
                    new_line_id = future_ship_line_obj.copy(cr, uid, line_id, context=context)
                    #attach new line to new future shipment and update quantity 
                    future_ship_line_obj.write(cr, uid, new_line_id, {'product_qty':qty, 'shipment_id':new_future_ship_id})
                    #update the old future shipment quantity to the real shipped quantity
                    future_ship_line_obj.write(cr, uid, line_id, {'product_qty':(qty_old-qty)})

        #update current future shipment to 'shipped'
        #TODO check split parameter from context
        if not context.get('split'):
            vals = {'state':'shipped', 'real_ship_id':data.real_ship_id.id}
            future_ship_obj.write(cr, uid, record_id, vals, context)
        #update the generated new future shipment order id
        if new_future_ship_id:
            vals = {}
            vals['new_future_ship_id'] = new_future_ship_id
            future_ship_obj.write(cr, uid, record_id, vals, context)
        
        return {'type': 'ir.actions.act_window_close'} 
    
future_ship_req() 


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
