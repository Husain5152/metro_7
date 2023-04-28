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
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from openerp import netsvc

from openerp.osv import fields,osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools import float_compare
from openerp.addons.metro import utils
PR_STATES_SELECTION = [('draft','New'),
                       ('confirmed','Confirmed'),
                       ('approved','Approved'),
                       ('rejected','Rejected'),
                       ('in_purchase','PO Issuing'),
                       ('enough','Enough In Stock'),
                       ('not_ordered','Not Ordered'),
                       ('not_paid','Not Paid'),
                       ('not_delivered','Not Delivered'),
                       ('delivered','Delivered'),
                       ('done','PR Closed'),
                       ('cancel','Cancelled')]
class pur_req(osv.osv):
    _name = "pur.req"
    _description="Purchase Requisitions"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _order = "name desc"
    def _full_gen_po(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for req in self.browse(cursor, user, ids, context=context):
            full_gen_po = True
            if req.line_ids:
                for req_line in req.line_ids:
                    if not req_line.generated_po:
                        full_gen_po = False
                        break
            res[req.id] = full_gen_po
        return res
    def _req_pos(self,cr,uid,ids,field_names=None, arg=False, context=None):
        """ Finds the requisition related PO ids.
        @return: Dictionary of values
        """
        if not field_names:
            field_names = []
        if context is None:
            context = {}
        res = dict.fromkeys(ids,[])
        for req in self.browse(cr, uid, ids, context=context):
            po_ids = []
            for req_line in req.line_ids:
                for po_line in req_line.po_lines_ids:
                    if po_line.order_id.id not in po_ids:
                        po_ids.append(po_line.order_id.id)
            res[req.id] = po_ids
        return res
        
    _columns = {
        'name': fields.char('Requisition#', size=32,required=True),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse',required=True,readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),    
        'user_id': fields.many2one('res.users', 'Requester',required=True,readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),        
        'date_request': fields.datetime('Requested Date',required=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}, help="Filled by Requester (when we need the goods)"),
        'remark': fields.text('Remark'),
        'company_id': fields.many2one('res.company', 'Company', required=True,readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'line_ids' : fields.one2many('pur.req.line','req_id','Products to Purchase',readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'state': fields.selection(PR_STATES_SELECTION,
            'Status', track_visibility='onchange', required=True,),
#        'po_ids' : fields.one2many('purchase.order','req_id','Related PO'),
        #once user did merging PO, then one PO may have multi requestions, so change this field to a function field
        'po_ids' : fields.function(_req_pos, type='one2many',relation='purchase.order',string='Related PO'),              
        'full_gen_po': fields.function(_full_gen_po, string='All products generated PO', type='boolean', help="It indicates that this requsition's all lines generated PO"),
    }
    _defaults = {
#        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'pur.req'),
        'name': lambda obj, cr, uid, context: '/',
#        'warehouse_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).id ,
        'user_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).id ,
        'date_request': lambda *args: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'pur.req', context=c),
        'state': 'draft',
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Order Reference must be unique!'),
    ]

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'state':'draft',
            'po_ids':[],
            'name': self.pool.get('ir.sequence').get(cr, uid, 'pur.req'),
        })
        return super(pur_req, self).copy(cr, uid, id, default, context)
    
    def create(self, cr, uid, vals, context=None):
        if vals.get('name','/')=='/':
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'pur.req') or '/'
        order =  super(pur_req, self).create(cr, uid, vals, context=context)
        return order
        
    def wkf_confirm_req(self, cr, uid, ids, context=None):
        for req in self.browse(cr, uid, ids, context=context):
            if not req.line_ids:
                raise osv.except_osv(_('Error!'),_('You cannot confirm a purchase requisition order without any product line.'))
            for line in req.line_ids:
                if not line.supplier_id or not line.product_id:
                    raise osv.except_osv(_('Error!'),
                             _('Please fill all product and suppliers before confirm purchase requisition.'))
        self.write(cr,uid,ids,{'state':'confirmed'})
        return True

    def wkf_cancel_req(self, cr, uid, ids, context=None):
        #wf_service = netsvc.LocalService("workflow")
        for req in self.browse(cr, uid, ids, context=context):
            for po in req.po_ids:
                if po.state not in('cancel'):
                    raise osv.except_osv(
                        _('Unable to cancel this purchase requisition.'),
                        _('First cancel all purchase orders related to this purchase order.'))
#            for po in req.po_ids:
#                wf_service.trg_validate(uid, 'purchase.order', po.id, 'purchase_cancel', cr)
    
        self.write(cr,uid,ids,{'state':'cancel'})
        return True  
      
    def unlink(self, cr, uid, ids, context=None):
        pur_reqs = self.read(cr, uid, ids, ['state'], context=context)
        unlink_ids = []
        for s in pur_reqs:
            if s['state'] in ['draft','cancel']:
                unlink_ids.append(s['id'])
            else:
                raise osv.except_osv(_('Invalid Action!'), _('In order to delete a purchase requisition, you must cancel it first.'))

        # automatically sending subflow.delete upon deletion
        wf_service = netsvc.LocalService("workflow")
        for id in unlink_ids:
            wf_service.trg_validate(uid, 'pur.req', id, 'pur_req_cancel', cr)
        if unlink_ids:
            self._email_notify(cr, uid, unlink_ids, 'deleted', context=context)
        return super(pur_req, self).unlink(cr, uid, unlink_ids, context=context)    
    
    def action_cancel_draft(self, cr, uid, ids, context=None):
        if not len(ids):
            return False
        self.write(cr, uid, ids, {'state':'draft'})
        wf_service = netsvc.LocalService("workflow")
        for p_id in ids:
            # Deleting the existing instance of workflow for requisition
            wf_service.trg_delete(uid, 'pur.req', p_id, cr)
            wf_service.trg_create(uid, 'pur.req', p_id, cr)
        return True
    
    def _email_notify(self, cr, uid, ids, mail_type, context=None):
        mail_types = {
                    'created': {'action':'has been created','groups':['metro_purchase.group_pur_req_manager']},
                    'confirmed':{'action':'need your approval','groups':['metro_purchase.group_pur_req_checker']},
                    'approved':{'action':'approved, please issue PO','groups':['metro_purchase.group_pur_req_buyer']},
                    'rejected':{'action':'was rejected, please check','groups':[]},
                    'in_purchase':{'action':'is in purchasing','groups':[],},
                    'done':{'action':'was done','groups':['metro_purchase.group_pur_req_buyer']},
                    'cancel':{'action':'was cancelled', 'groups': []},
                    'deleted': {'action': 'was deleted', 'groups': ['metro_purchase.group_pur_req_manager']},
                  }
        model_obj = self.pool.get('ir.model.data')
        if mail_types.get(mail_type,False):
            action_name = mail_types[mail_type]['action']
            group_params = mail_types[mail_type]['groups']
            for order in self.browse(cr, uid, ids, context=context):
                #email to groups
                email_group_ids = []
                for group_param in group_params:
                    grp_data = group_param.split('.')
                    email_group_ids.append(model_obj.get_object_reference(cr, uid, grp_data[0], grp_data[1])[1])
                #email to users
                email_to = None
                if mail_type in (' rejected', 'done', 'cancel'):
                    email_to = order.user_id.email
                email_cc = None
                if mail_type in ('approved', 'in_purchase'):
                    email_cc = order.user_id.email
                # HoangTK - Add username to email subject
                user = self.pool.get("res.users").browse(cr, uid, uid, context=context)
                #email messages
                if action_name in ['created', 'approved', 'cancel', 'rejected', 'deleted']:
                    email_subject = 'Purchase Requisition: %s %s by %s' % (order.name, action_name, user.name)
                else:
                    email_subject = 'Purchase Requisition: %s %s'%(order.name,action_name)
                email_body = email_subject
                #the current user is the from user
                # email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'],context=context)['email']
                email_from = user.email
                #send emails
                utils.email_send_group(cr, uid, email_from, email_to, email_subject,email_body, email_group_ids, email_cc=email_cc,context=context)
                
pur_req()    

class pur_req_line(osv.osv):

    _name = "pur.req.line"
    _description="Purchase Requisition Line"
    _rec_name = 'product_id'
    
    def _generated_po(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for req_line in self.browse(cursor, user, ids, context=context):
            generated_po = False
            if req_line.po_lines_ids:
                for po_line in req_line.po_lines_ids:
                    if po_line.state != 'cancel':
                        generated_po = True
                        break
            res[req_line.id] = generated_po
        return res

    def _po_info(self, cr, uid, ids, field_names=None, arg=False, context=None):
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
        for req_line in self.browse(cr, uid, ids, context=context):
            generated_po = False
            req_qty = req_line.product_qty
            #product_qty_remain = req_line.product_qty
            product_qty_remain = 0
            product_generated_qty = 0
            if req_line.product_qty > req_line.product_onhand_qty:
                product_qty_remain = req_line.product_qty - req_line.product_onhand_qty
            po_qty_str = ''
            if req_line.po_lines_ids:
                uom_obj = self.pool.get('product.uom')
                for po_line in req_line.po_lines_ids:
                    if po_line.state != 'cancel':
                        ctx_uom = context.copy()
                        ctx_uom['raise-exception'] = False
                        uom_po_qty = uom_obj._compute_qty_obj(cr, uid, po_line.product_uom, po_line.product_qty, \
                                                              req_line.product_uom_id, context=ctx_uom)
                        product_generated_qty += uom_po_qty
                        po_qty_str += ((po_qty_str or '') and '; ') + '%s(%s)@%s'%(po_line.product_qty, uom_po_qty, po_line.order_id.name)
#                po_finished = float_compare(po_qty, req_qty, precision_rounding=req_line.product_uom_id.rounding)
                po_finished = float_compare(req_qty, product_generated_qty, precision_rounding=4)
                generated_po = (po_finished <= 0)
                if generated_po:
                    product_qty_remain =  0
                else:
                    product_qty_remain = req_qty - product_generated_qty
            res[req_line.id]['product_generated_qty'] = product_generated_qty
            res[req_line.id]['generated_po'] = generated_po 
            res[req_line.id]['product_qty_remain'] = product_qty_remain
            res[req_line.id]['po_info'] = po_qty_str
        return res  

      
    _columns = {
        'req_id' : fields.many2one('pur.req','Purchase Requisition', ondelete='cascade'),
        #HoangTK - 07/01/2016 - removed required in order to create PR from xls
        #'product_id': fields.many2one('product.product', 'Product', required=True),
        'product_id': fields.many2one('product.product', 'Product'),
        'uom_categ_id': fields.related('product_uom_id','category_id',type='many2one',relation='product.uom.categ',String="UOM Category"),
        'product_qty': fields.float('Need Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),required=True),
        #'product_uom_id': fields.many2one('product.uom', 'Product UOM',required=True),
        'product_uom_id': fields.many2one('product.uom', 'Product UOM'),
        'inv_uom_id': fields.related('product_id','uom_id',type='many2one',relation='product.uom', string='Inventory UOM',readonly=True),
        #'date_required': fields.date('Date Required',required=True),
        'date_required': fields.date('Date Required'),
        'inv_qty': fields.float('Inventory'),
        'req_emp_id': fields.many2one('hr.employee','Employee'),
        'req_dept_id': fields.related('req_emp_id','department_id',type='many2one',relation='hr.department',string='Department',readonly=True),
        'req_reason': fields.char('Reason and use',size=64),
        'company_id': fields.related('req_id','company_id',type='many2one',relation='res.company',String='Company',store=True,readonly=True),
        'po_lines_ids' : fields.one2many('purchase.order.line','req_line_id','Purchase Order Lines',readonly=True),
        'generated_po': fields.function(_po_info, multi='po_info', string='PO Generated', type='boolean', help="It indicates that this products has PO generated"),
        'product_qty_remain': fields.function(_po_info, multi='po_info', string='Qty Remaining', type='float', digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True),
        'product_generated_qty': fields.function(_po_info, multi='po_info', string='PO Generated Qty', type='float', digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True),
        'product_incoming_qty': fields.related('product_id','qty_in', type='float', string='Qty Incoming', digits_compute=dp.get_precision('Product Unit of Measure'), help="Quantity of product waiting to be received", readonly=True),
        'product_onhand_qty': fields.related('product_id','qty_available', type='float', digits_compute=dp.get_precision('Product Unit of Measure'), string='On hand Qty', help="Stock on hand quantity", readonly=True),
        'product_qty_req': fields.related('product_id','product_qty_req', type='float', digits_compute=dp.get_precision('Product Unit of Measure'), string='Requesting Qty', help="All PR need quantity that not generated PO yet", readonly=True),
        'procurement_ids': fields.one2many("procurement.order",'pur_req_line_id','Procurements'),
        'po_info': fields.function(_po_info, multi='po_info',type='char',string='PO Quantity',readonly=True),   
        'req_ticket_no': fields.char('Requisition Ticket#', size=10),
        'order_warehouse_id': fields.related('req_id','warehouse_id',type='many2one',relation='stock.warehouse',string='Warehouse',readonly=True),
        'order_user_id': fields.related('req_id','user_id',type='many2one',relation='res.users',string='Requester',readonly=True),
        'order_date_request': fields.related('req_id','date_request',type='datetime',string='Requisition Date',readonly=True),
        'order_state': fields.related('req_id', 'state', type='selection',string='Status',readonly=True,
                                      selection=PR_STATES_SELECTION),
        'mfg_ids': fields.many2many('sale.product',string="MFG IDs"),
        "supplier_id": fields.many2one('res.partner', "Supplier"),
                        
    }
    _rec_name = 'product_id'
    
    def onchange_product_id(self, cr, uid, ids, product_id, context=None):
        """ Changes UoM,inv_qty if product_id changes.
        @param product_id: Changed product_id
        @return:  Dictionary of changed values
        """
        #value = {'product_uom_id': '', 'inv_qty': ''}
        value = {'product_uom_id': ''}
        if product_id:
            prod = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            #HoangTK - 08/10/2016 - Remove default product_qty
            #value = {'product_qty':1.0,'inv_qty':prod.qty_available}
            #value = {'inv_qty': prod.qty_available}
            uom = prod.uom_id or prod.uom_po_id
            value.update({'product_uom_id': uom.id,'inv_uom_id':prod.uom_id.id})
            '''
            Add the uom_categ_id, johnw, 05/08/2015
            '''
            value['uom_categ_id'] = prod.uom_id.category_id.id
            
        return {'value':value}

    _defaults = {
        'product_qty': lambda *a: 1.0,
    }
    
    def onchange_product_uom(self, cr, uid, ids, product_id, uom_id, context=None):
        """
        onchange handler of product_uom.
        """
        res = {}
        if not uom_id:
            return {'value': {'product_uom_id' : False}}
        # - check that uom and product uom belong to the same category
        product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
        prod_uom = product.uom_id or product.uom_po_id
        uom = self.pool.get('product.uom').browse(cr, uid, uom_id, context = context)
        if prod_uom.category_id.id != uom.category_id.id:
            if self._check_product_uom_group(cr, uid, context=context):
                res['warning'] = {'title': _('Warning!'), 'message': _('Selected Unit of Measure does not belong to the same category as the product Unit of Measure.')}
            uom_id = prod_uom.id
        res['value'] = {'product_uom_id': uom_id, 'uom_categ_id':uom.category_id.id}
        return res
    
    def _check_product_uom_group(self, cr, uid, context=None):
        group_uom = self.pool.get('ir.model.data').get_object(cr, uid, 'product', 'group_uom')
        res = [user for user in group_uom.users if user.id == uid]
        return len(res) and True or False
    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'po_lines_ids':[],
        })
        res = super(pur_req_line, self).copy_data(cr, uid, id, default, context)
        return res    
       
pur_req_line()

class purchase_order(osv.osv):
    _inherit = "purchase.order"
    _columns = {
        'req_id' : fields.many2one('pur.req','Purchase Requisition',readonly=True)
    }
    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'req_id':False,
        })
        res = super(purchase_order, self).copy_data(cr, uid, id, default, context)
        return res  
   
purchase_order()

class purchase_order_line(osv.osv):    
    _inherit = "purchase.order.line"
    _columns = {
                'req_line_id':fields.many2one('pur.req.line', 'Purchase Requisition',readonly=True)}   
    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'req_line_id':False,
        })
        res = super(purchase_order_line, self).copy_data(cr, uid, id, default, context)
        return res    
    
purchase_order_line()

class product_product(osv.osv):
    """
    Requested Quantity without approval: we need the result of (PR - PO),
    """
    
    _inherit = "product.product"

    def view_requesting_pr(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context:
            context = {}
        pr_line_obj = self.pool.get('pur.req.line')
        requesting_line_ids = pr_line_obj.search(cr, uid, [('product_id','in',ids),
                                                    ('order_state','in',['approved', 'in_purchase'])], context=context)
        if requesting_line_ids:
            return {
                'domain': "[('id', 'in', [" + ','.join([str(request_line_id) for request_line_id in requesting_line_ids]) + "])]",
                'name': _('Requesting Products'),
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'pur.req.line',
                'type': 'ir.actions.act_window',
                'context': context,
            }
        return True

    def view_incoming_shipment(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context:
            context = {}
        product_obj = self.pool.get('product.product')
        location_ids  = product_obj._get_locations_from_context(cr, uid, [], context=context)
        if ids:
            return {
                'domain': "[('state','in',['confirmed', 'waiting', 'assigned']),('product_id', 'in', [" + ','.join([str(product_id) for product_id in ids]) + "]), \
                ('location_id','not in', [" + ','.join([str(location_id) for location_id in location_ids]) + "]), \
                ('location_dest_id','in', [" + ','.join([str(location_id) for location_id in location_ids]) + "])]",
                'name': _('Incoming Products'),
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'stock.move',
                'type': 'ir.actions.act_window',
                'context': context.update({
                    'product_receive': True,
                    'search_default_future': True,
                    'picking_type': 'in'
                }),
            }
        return True

    def _product_qty_req(self, cr, uid, ids, field_names=None, arg=False, context=None):
        if context is None:
            context = {}
        res = {}
        req_obj = self.pool.get('pur.req.line')# get the object of model,pur_req_line
        for prod in self.browse(cr, uid, ids, context=context):
            # req_line_ids = req_obj.search(cr, uid, [('product_id','=',prod.id),('order_state','not in',['cancel']),], context=context)
            req_line_ids = req_obj.search(cr, uid,
                                          [('product_id', '=', prod.id),
                                           ('order_state', 'not in', ['draft', 'confirmed', 'done','rejected', 'cancel', 'cancel_except']), ],
                                          context=context)
            prod_req_qty = 0.0
            for req_line in req_obj.browse(cr, uid, req_line_ids, context=context):#get the above req_line_ids 's product
                prod_req_qty += req_line.product_qty #get the  'product_qty' in  fields.float('Quantity',
                if req_line.po_lines_ids:#if the purchase order has already been generated
                    #calculate the quantity of this request line
                    for po_line in req_line.po_lines_ids:#get the PO lines- products
                        required_state = ('draft', 'confirmed', 'rejected', 'cancel', 'cancel_except')
                        if po_line.order_id.state not in required_state:
                            prod_req_qty -= po_line.product_qty    #deduct the number in PO
                    prod_req_qty = max(0, prod_req_qty)
            res[prod.id] = prod_req_qty           
        return res
    
    _columns = {
                'product_qty_req': fields.function(_product_qty_req, string='Requesting Quantities', type='float',
                                                   digits_compute=dp.get_precision('Product Unit of Measure'),
                                                   help='All PR need quantity that not generated PO yet'),
                }

product_product()   
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
