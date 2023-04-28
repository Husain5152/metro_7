# -*- coding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 OpenERP SA (<http://www.openerp.com>)
#    Copyright (C) 2011-2013 Serpent Consulting Services Pvt. Ltd. (<http://www.serpentcs.com>).

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
from openerp.addons.metro import utils

class future_shipment(osv.osv):
    '''
    Define one future shipment order, one shipment have multiple product lines
    '''
    _name="future.shipment"
    
    _rec_name="code"
    _order = "id desc"
    _columns = {
        'code': fields.char('Reference', size=16, required=True, readonly=True),        
        'origin_id':fields.many2one('res.partner', 'Origination', required=True,readonly=True, states={'wait':[('readonly',False)]}),
        'dest_id': fields.many2one('res.partner','Destination', required=True,readonly=True, states={'wait':[('readonly',False)]}),
        'state':fields.selection(
                                 [('wait','Waiting'),('shipped','Shipped'),('cancel','Cancelled')],
                                 'State',required=True
                                 ),
        'line_ids' : fields.one2many('future.shipment.line','shipment_id','Products to future shipping',readonly=True, states={'wait':[('readonly',False)]}),
        'real_ship_id':fields.many2one('shipment.shipment','Final Shipment', readonly=True),
        'new_future_ship_id':fields.many2one('future.shipment','New Future Shipment', readonly=True),
#        'multi_images': fields.text("Multi Images"),
        'create_uid':  fields.many2one('res.users', 'Creator', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'delivery_type':fields.selection(
                                [('container','Container'),('express','Express')],
                                'Delivery Type',
                                ),
                }
    
    _defaults={
               'state':'wait', 
               'code':lambda self, cr, uid, obj, ctx=None: self.pool.get('ir.sequence').get(cr, uid, 'future.shipment') or '/',
                }
    
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        code = self.pool.get('ir.sequence').get(cr, uid, 'future.shipment') or '/'
        default.update({
               'state':'wait', 
               'code':code,
               'real_ship_id':None,
               'new_future_ship_id':None,
        })
        return super(future_shipment, self).copy(cr, uid, id, default, context)    
        
    def unlink(self, cr, uid, ids, context=None):
        for order in self.read(cr, uid, ids, ['state'], context=context):
            if order['state'] == 'shipped':
                raise osv.except_osv(_('Error'), 'Future shipment was shipped, can not be delete!')
        return super(future_shipment,self).unlink(cr, uid, ids, context=context)
    
    def action_cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'cancel', 'real_ship_id':None, 'new_future_ship_id':None}, context=context)
    
    def _email_notify(self, cr, uid, ids, action_name, group_params, context=None):
        #ids 是int 需要转成list
        if isinstance(ids, (int, long)):
            ids = [ids]
        for order in self.browse(cr, uid, ids, context=context):
            for group_param in group_params:
                email_group_id = self.pool.get('ir.config_parameter').get_param(cr, uid, group_param, context=context)
                if email_group_id:                    
                    email_subject = 'Future Shipment reminder: %s %s'%(order.code,action_name)
                    email_body_string = 'The Future Shipment({0}) has been changed.'
                    email_body = email_body_string.format(order.code,)
                    email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'],context=context)['email']
                    utils.email_send_group(cr, uid, email_from, None, email_subject,email_body, email_group_id, context=context)      
                    
    def write(self, cr, uid, ids, vals, context=None):
        resu = super(future_shipment,self).write(cr, uid, ids, vals, context=context)
        self._email_notify(cr, uid, ids,'Future shipment was changed',['future_shipment_group_notice'],context)
        return resu
    
    def create(self, cr, uid, vals, context=None):
        new_id = super(future_shipment, self).create(cr, uid, vals, context=context)
        self._email_notify(cr, uid, new_id,'New future shipment was created',['future_shipment_group_notice'],context)
        return new_id

    def print_report(self, cr, uid, ids, context=None):
        datas = {
                 'model': 'future.shipment',
                 'ids': ids,
                 'form': self.read(cr, uid, ids[0], context=context),
                }
        return {'type': 'ir.actions.report.xml', 'report_name': 'future.shipment.briefreport', 'datas': datas, 'nodestroy': True}

    
future_shipment()

class future_shipment_line(osv.osv):
    '''
    doc
    Model: future.shipment.line
    '''
    _name="future.shipment.line"
    _columns = {
        'shipment_id':fields.many2one('future.shipment','Future Shipment'),
        'notes':fields.text('Description'),
        'product_id':fields.many2one('product.product', 'Product', required=False),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),required=True),
        
        'create_uid':  fields.many2one('res.users', 'Creator', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'write_uid':  fields.many2one('res.users', 'Modified By', readonly=True),
        'write_date': fields.datetime('Modification Date', readonly=True, select=True),
        
        'multi_images': fields.text("Multi Images"),
        }
future_shipment_line()

