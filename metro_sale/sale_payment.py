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
from osv import fields,osv,orm
import openerp.addons.decimal_precision as dp
import math
class sale_order(osv.osv):
    _inherit="sale.order"
        
    def _get_amount(self, cr, uid, ids, field_names, args, context=None):
        """ Finds the payment mount and set the paid flag
        @return: Dictionary of values
        """
        if not field_names:
            field_names = []
        if context is None:
            context = {}
        res = {}
        for id in ids:
            res[id] = {}.fromkeys(field_names)

        for order in self.browse(cr, uid, ids, context=context):
            pre_paid = 0.0
            inv_paid = 0.0
            #check the prepaymenys
            for line in order.payment_ids:    
                if not line.reconcile_id:
                    if not line.reconcile_partial_id:
                        if line.currency_id:
                            pre_paid += abs(line.amount_residual_currency)
                        else:
                            pre_paid += line.amount_residual                        
                    else:
                        #if move is partial reconciled, then only the amount_residual is negative then this line is also need more lines to reconcile it
                        if line.amount_residual > 0:
                            if line.currency_id:
                                pre_paid += abs(line.amount_residual_currency)
                            else:
                                pre_paid += line.amount_residual
                
            #check the invoice paid            
            for invoice in order.invoice_ids:
                if invoice.state not in ('draft','cancel'):
                    if invoice.type == 'in_refund':
                        inv_paid -= (invoice.amount_total - invoice.residual)
                    else:                        
                        inv_paid += (invoice.amount_total - invoice.residual)
               
            res[order.id] = {
                    'amount_paid': inv_paid + pre_paid, 
                    'residual': order.amount_total - inv_paid - pre_paid
                    }
        return res

    def _inv_pay_ids(self, cr, uid, ids, field_names=None, arg=False, context=None):
        """ Finds the payment list by invoice
        @return: Dictionary of values
        """
        if not field_names:
            field_names = []
        if context is None:
            context = {}
        res = {}
        for id in ids:
            res[id] = {}.fromkeys(field_names)

        for order in self.browse(cr, uid, ids, context=context):
            #check the invoice paid  
            inv_pay_ids = []          
            for invoice in order.invoice_ids:
                if invoice.state not in ('draft','cancel'):
                    inv_pay_ids.extend(map(lambda x: x.id, invoice.payment_ids))
            res[order.id] = inv_pay_ids
        return res
            
    _columns={
          'state': fields.selection([
            ('draft', 'Draft Quotation'),
            ('sent', 'Quotation Sent'),
            ('agreed', 'Sales Agreement'),
            ('cancel', 'Cancelled'),
            ('waiting_date', 'Waiting Schedule'),
            ('progress', 'Sales Order'),
            ('manual', 'Sale to Invoice'),
            ('shipping_except', 'Shipping Exception'),
            ('invoice_except', 'Invoice Exception'),
            ('done', 'Done'),
            ], 'Status', readonly=True,help="Gives the status of the quotation or sales order.\
              \nThe exception status is automatically set when a cancel operation occurs \
              in the invoice validation (Invoice Exception) or in the picking list process (Shipping Exception).\nThe 'Waiting Schedule' status is set when the invoice is confirmed\
               but waiting for the scheduler to run on the order date.", select=True),
#change the 'state' arugment, add the "'agreed': [('readonly', False)]"              
        'name': fields.char('Order Reference', size=64, required=True,
            readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'agreed': [('readonly', False)]}, select=True),
        'shop_id': fields.many2one('sale.shop', 'Shop', required=True, readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'agreed': [('readonly', False)]}),
        'date_order': fields.date('Date', required=True, readonly=True, select=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'agreed': [('readonly', False)]}),
        'user_id': fields.many2one('res.users', 'Salesperson', states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'agreed': [('readonly', False)]}, select=True, track_visibility='onchange'),
        'partner_id': fields.many2one('res.partner', 'Customer', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'agreed': [('readonly', False)]}, required=True, change_default=True, select=True, track_visibility='always'),
        'partner_invoice_id': fields.many2one('res.partner', 'Invoice Address', readonly=True, required=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'agreed': [('readonly', False)]}, help="Invoice address for current sales order."),
        'partner_shipping_id': fields.many2one('res.partner', 'Delivery Address', readonly=True, required=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'agreed': [('readonly', False)]}, help="Delivery address for current sales order."),
        'order_policy': fields.selection([
                ('manual', 'On Demand'),
                ('picking', 'On Delivery Order'),
                ('prepaid', 'Before Delivery'),
            ], 'Create Invoice', required=True, readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'agreed': [('readonly', False)]},
            help="""On demand: A draft invoice can be created from the sales order when needed. \nOn delivery order: A draft invoice can be created from the delivery order when the products have been delivered. \nBefore delivery: A draft invoice is created from the sales order and must be paid before the products can be delivered."""),        'pricelist_id': fields.many2one('product.pricelist', 'Pricelist', required=True, readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'agreed': [('readonly', False)]}, help="Pricelist for current sales order."),
        'project_id': fields.many2one('account.analytic.account', 'Contract / Analytic', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'agreed': [('readonly', False)]}, help="The analytic account related to a sales order."),
        'order_line': fields.one2many('sale.order.line', 'order_id', 'Order Lines', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'agreed': [('readonly', False)]}),
#links to account_move        
        'payment_moves': fields.many2many('account.move', string='Payment Moves', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'agreed': [('readonly', False)]}),
#redefine the columns in sale_payment_method/sale.py
        'residual': fields.function(
            _get_amount,
            type='float',
            digits_compute=dp.get_precision('Account'),
            string='Balance',
            store=False,
            multi='payment'),
        'amount_paid': fields.function(
            _get_amount,
            type='float',
            digits_compute=dp.get_precision('Account'),
            string='Amount Paid',
            store=False,
            multi='payment'),
        #new field include the invoice payment move lines         
        'inv_pay_ids': fields.function(_inv_pay_ids,relation='account.move.line', type='many2many', string='Invoice Payments'),              
    }
        
    #from the sale_payment_method.sale.py, add the sale_id
    def _prepare_payment_move(self, cr, uid, move_name, sale, journal,
                              period, date, description, context=None):
        resu = super(sale_order,self)._prepare_payment_move(cr,uid,move_name,sale,journal,period,date,description,context)
        resu.update({'sale_ids':[(4, sale.id)]})
        return resu
    
    #johnw, 03/02/2015, add the prepayment attachment dealing
    def _add_payment(self, cr, uid, sale, journal, amount, date, description=None, context=None):
        new_mvid = super(sale_order,self)._add_payment(cr,uid, sale, journal, amount, date, description,context=context)        
        if context.get('pay_attachment_name'):
            self.pool.get('ir.attachment').create(
                cr, uid, {'name':  context.get('pay_attachment_name'),
                          'datas_fname':  context.get('pay_attachment_name'),
                          'res_id': new_mvid,
                          'res_model': 'account.move',
                          'type': 'binary',
                          'datas': context.get('pay_attachment'),
                          'description': 'From Customer Advance Payment',
                          'account_move_id':new_mvid})
                                
        return new_mvid        
        
    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default['payment_moves'] = False
        return super(sale_order, self).copy(cr, uid, id,
                                            default, context=context)
    def print_agreement(self, cr, uid, ids, context=None):
        datas = {
                 'model': 'sale.order',
                 'ids': ids,
                 'form': self.read(cr, uid, ids[0], context=context),
        }
        return {'type': 'ir.actions.report.xml', 'report_name': 'sale.agreement', 'datas': datas, 'nodestroy': True}
class account_move(osv.osv):
    _inherit="account.move"
    _columns = {
        'sale_ids': fields.many2many('sale.order', string='Sales Orders'),
    }       
    def unlink(self, cr, uid, ids, context=None, check=True):
        #if the move's line generated by the sales payment, then cancel this entry firstly
        moves = self.browse(cr,uid,ids,context)
        for move in moves:
            if move.state == 'posted' and move.sale_ids:
                self.button_cancel(cr,uid,[move.id],context=context)
        #execute the delete action
        result = super(account_move, self).unlink(cr, uid, ids, context=context)
        return result
    
class pay_sale_order(orm.TransientModel):
    _inherit = 'pay.sale.order'       
    _columns = {
        'amount_max': fields.float('Max Amount',digits_compute=dp.get_precision('Account')),
        'attachment': fields.binary('Attachment'),
        'attachment_name': fields.char('Attachment File Name'),
    }
    def _get_amount(self, cr, uid, context=None):
        if context is None:
            context = {}
        if context.get('active_id'):
            sale_obj = self.pool.get('sale.order')
            order = sale_obj.browse(cr, uid, context['active_id'],
                                    context=context)
            return order.residual
        return False    
    _defaults = {
        'amount': _get_amount,
        'amount_max':_get_amount,
        'description':u'Customer Advance Payment'
    }    
    def _check_amount(self, cr, uid, ids, context=None):
        for pay in self.browse(cr, uid, ids, context=context):
            #+++ HoangtK - 02/15/2016 : Fix floating point rounding issue
            precision = 6
            if pay.amount <= 0 or math.ceil(pay.amount * (10** precision)) > math.ceil(pay.amount_max * (10**precision)):
                return False
        return True
    _constraints = [(_check_amount, 'Pay amount only can be between zero and the balance.', ['amount'])]
    
    def pay_sale_order(self, cr, uid, ids, context=None):
        """ Pay the sale order """
        wizard = self.browse(cr, uid, ids[0], context=context)
        if wizard.attachment_name:
            context['pay_attachment'] = wizard.attachment
            context['pay_attachment_name'] = wizard.attachment_name
        return super(pay_sale_order, self).pay_sale_order(cr, uid, ids, context=context)
            