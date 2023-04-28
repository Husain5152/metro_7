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

import time
from lxml import etree

from openerp.osv import fields, osv
from openerp import tools
from openerp.tools.translate import _
from openerp.addons.account_analytic_plans import account_analytic_plans
import openerp.addons.decimal_precision as dp

'''
1.Allow to update analytic plan instance
2.Add 'Instances' tag page to analytic plan screen
3.Replace 'Analytic Account' with 'Analytic Distribution' on customer invoice line tree
4.Add the analytics plan logic when create invoices from stock move
5.Use the plan instance's journal as the analytic journal line's journal 
'''

#1.Allow to update analytic plan instance
def account_analytic_plan_instance_write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
    if context is None:
        context = {}
    #johnw, 08/05/2014, feel it is useless following code: do not write plan instance, copy one
    #TODO think if we need to check the opening data related to this instance: SO Lines, PO Lines, Invoice lines, Account Move Lines
    ''' 
    this = self.browse(cr, uid, ids[0], context=context)
    invoice_line_obj = self.pool.get('account.invoice.line')
    if this.plan_id and not vals.has_key('plan_id'):
        #this instance is a model, so we have to create a new plan instance instead of modifying it
        #copy the existing model
        temp_id = self.copy(cr, uid, this.id, None, context=context)
        #get the list of the invoice line that were linked to the model
        lists = invoice_line_obj.search(cr, uid, [('analytics_id','=',this.id)], context=context)
        #make them link to the copy
        invoice_line_obj.write(cr, uid, lists, {'analytics_id':temp_id}, context=context)

        #and finally modify the old model to be not a model anymore
        vals['plan_id'] = False
        if not vals.has_key('name'):
            vals['name'] = this.name and (str(this.name)+'*') or "*"
        if not vals.has_key('code'):
            vals['code'] = this.code and (str(this.code)+'*') or "*"
    '''
    return super(account_analytic_plans.account_analytic_plan_instance, self).write(cr, uid, ids, vals, context=context)

account_analytic_plans.account_analytic_plan_instance.write = account_analytic_plan_instance_write

#5.Use the plan instance's journal as the analytic journal line's journal 
def _get_analytic_lines(self, cr, uid, id, context=None):
    inv = self.browse(cr, uid, [id])[0]
    cur_obj = self.pool.get('res.currency')
    invoice_line_obj = self.pool.get('account.invoice.line')
    acct_ins_obj = self.pool.get('account.analytic.plan.instance')
    company_currency = inv.company_id.currency_id.id
    if inv.type in ('out_invoice', 'in_refund'):
        sign = 1
    else:
        sign = -1

    iml = invoice_line_obj.move_line_get(cr, uid, inv.id, context=context)

    for il in iml:
        if il.get('analytics_id', False):

            if inv.type in ('in_invoice', 'in_refund'):
                ref = inv.reference
            else:
                ref = self._convert_ref(cr, uid, inv.number)
            obj_move_line = acct_ins_obj.browse(cr, uid, il['analytics_id'], context=context)
            ctx = context.copy()
            ctx.update({'date': inv.date_invoice})
            amount_calc = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, il['price'], context=ctx) * sign
            qty = il['quantity']
            il['analytic_lines'] = []
            #johnw, check the analytic distribution's journal
            if not obj_move_line.journal_id:
                raise osv.except_osv(_('No Analytic Journal !'),_("You have to define an analytic journal on the '%s' distribution.") % (obj_move_line.name,))
            for line2 in obj_move_line.account_ids:
                amt = amount_calc * (line2.rate/100)
                qtty = qty* (line2.rate/100)
                al_vals = {
                    'name': il['name'],
                    'date': inv['date_invoice'],
                    'unit_amount': qtty,
                    'product_id': il['product_id'],
                    'account_id': line2.analytic_account_id.id,
                    'amount': amt,
                    'product_uom_id': il['uos_id'],
                    'general_account_id': il['account_id'],
#                    'journal_id': self._get_journal_analytic(cr, uid, inv.type),
                    'journal_id': obj_move_line.journal_id.id,
                    'ref': ref,
                }
                il['analytic_lines'].append((0, 0, al_vals))
    return iml
def create_analytic_lines(self, cr, uid, ids, context=None):
    if context is None:
        context = {}
    super(account_analytic_plans.account_move_line, self).create_analytic_lines(cr, uid, ids, context=context)
    analytic_line_obj = self.pool.get('account.analytic.line')
    for line in self.browse(cr, uid, ids, context=context):
       if line.analytics_id:
#           if not line.journal_id.analytic_journal_id:
#               raise osv.except_osv(_('No Analytic Journal !'),_("You have to define an analytic journal on the '%s' journal.") % (line.journal_id.name,))           
           if not line.analytics_id.journal_id:
               raise osv.except_osv(_('No Analytic Journal !'),_("You have to define an analytic journal on the '%s' distribution.") % (line.analytics_id.name,))
           #avoid to delete the lines generated by account_move_line.analytic_account_id, both analytic_account_id and analytics_id will generate analytical lines 
#           toremove = analytic_line_obj.search(cr, uid, [('move_id','=',line.id)], context=context)
#           if toremove:
#                analytic_line_obj.unlink(cr, uid, toremove, context=context)
           for line2 in line.analytics_id.account_ids:
               val = (line.credit or  0.0) - (line.debit or 0.0)
               amt=val * (line2.rate/100)
               al_vals={
                   'name': line.name,
                   'date': line.date,
                   'account_id': line2.analytic_account_id.id,
                   'unit_amount': line.quantity,
                   'product_id': line.product_id and line.product_id.id or False,
                   'product_uom_id': line.product_uom_id and line.product_uom_id.id or False,
                   'amount': amt,
                   'general_account_id': line.account_id.id,
                   'move_id': line.id,
#                   'journal_id': line.journal_id.analytic_journal_id.id,
                   'journal_id': line.analytics_id.journal_id.id,
                   'ref': line.ref,
                   'percentage': line2.rate
               }
               analytic_line_obj.create(cr, uid, al_vals, context=context)
    return True
account_analytic_plans.account_invoice._get_analytic_lines = _get_analytic_lines
account_analytic_plans.account_move_line.create_analytic_lines = create_analytic_lines

class account_move_line(osv.osv):
    _inherit = "account.move.line"
    _columns = {
                'quantity': fields.float('Quantity', digits_compute= dp.get_precision('Product Unit of Measure'),
                            help="The optional quantity expressed by this line, eg: number of product sold. The quantity is not a legal requirement but is very useful for some reports."),
            }
        

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default.update({'analytic_lines': []})
        return super(account_move_line, self).copy(cr, uid, id, default, context)
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default.update({'analytic_lines': []})
        return super(account_move_line, self).copy_data(cr, uid, id, default, context)
            
account_move_line()
    
#2.Add 'Instances' tag page to analytic plan screen
class account_analytic_plan(osv.osv):
    _inherit = "account.analytic.plan"
    _columns = {
        'instance_ids': fields.one2many('account.analytic.plan.instance', 'plan_id', 'Instances'),
    }
    
account_analytic_plan()

#4.Add the analytics plan logic when create invoices from stock move
class stock_picking(osv.osv):
    _inherit = "stock.picking"

    def _prepare_invoice_line(self, cr, uid, group, picking, move_line, invoice_id, invoice_vals, context=None):
        vals = super(stock_picking, self)._prepare_invoice_line(cr, uid, group, picking, move_line, invoice_id, invoice_vals, context=context)
        if picking.sale_id and move_line.sale_line_id and hasattr(move_line.sale_line_id, 'analytics_id'):
            vals.update({'analytics_id':move_line.sale_line_id.analytics_id.id})
        if picking.purchase_id and move_line.purchase_line_id and hasattr(move_line.purchase_line_id, 'analytics_id'):      
            vals.update({'analytics_id':move_line.purchase_line_id.analytics_id.id})
        return vals

stock_picking()

class account_analytic_line(osv.osv):
    _inherit = 'account.analytic.line'
    _order = 'id desc'
    _columns = {
                'unit_amount': fields.float('Quantity', digits_compute= dp.get_precision('Product Unit of Measure'), help='Specifies the amount of quantity to count.'),    
                }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
