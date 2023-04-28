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

import datetime
from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class work_order_cnc_line_done(osv.osv_memory):
    _name = "work.order.cnc.line.done"
    _description = "Set CNC Work Orders Done"

    _columns = {
        'name': fields.char('Work Order Name', readonly=True),
        'file_name': fields.char('File Name', size=16, readonly=True),
        'size': fields.char('Size', size=32, readonly=True),
        'percent_usage': fields.float('Usage Percent(%)', readonly=True),
        'date_finished': fields.datetime('Finished Date'),
        'product_id': fields.many2one('product.product','Product', required=True),
        'is_whole_plate': fields.boolean('Whole Plate'),
        'product_inv': fields.float('Inventory',digits_compute=dp.get_precision('Product Unit of Measure'),),
        'property_cnc_mr_dept': fields.property(
        'hr.department',
        type='many2one',
        relation='hr.department',
        string="CNC MR Department",
        view_load=True,
        required=True),
                
    }
#    _defaults = {'date_finished': fields.date.context_today,}
    _defaults = {'date_finished': lambda *a: datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),}
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
        res = super(work_order_cnc_line_done, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        record = self.pool.get('work.order.cnc.line').browse(cr, uid, record_id, context=context)
        if record:                    
            res.update({'name': record.order_id.name,
                        'file_name':record.file_name,
                        'size':'%s*%s*%s'%(record.plate_length,record.plate_width,record.plate_height),
                        'percent_usage':record.percent_usage,
                        })
        return res   
    def action_done(self, cr, uid, ids, context=None): 
        record_id = context and context.get('active_id', False) or False
        if not context:
            context = {}
        data = self.browse(cr,uid,ids,context)[0]
        context.update({'product_id':data.product_id.id,'date_finished':data.date_finished,'mr_dept_id':data.property_cnc_mr_dept.id,'is_whole_plate':data.is_whole_plate})
        self.pool.get('work.order.cnc.line').action_done(cr,uid,[record_id],context=context)
        return {'type': 'ir.actions.act_window_close'}  
    
    def on_change_product(self, cr, uid, ids, product_id,context=None):
        qty_available = 0
        if product_id:
            qty_available = self.pool.get("product.product").read(cr, uid, [product_id], ['qty_available'],context=context)[0]['qty_available']
        return {'value':{'product_inv':qty_available}}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
