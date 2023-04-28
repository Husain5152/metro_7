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
from dateutil.relativedelta import relativedelta
import time
import datetime
from openerp import netsvc
from openerp.osv import fields,osv,orm
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.addons.purchase import purchase
from collections import Iterable
from openerp.tools.translate import _
import logging

_logger = logging.getLogger(__name__)


class purchase_order(osv.osv):  
    _inherit = "purchase.order"
    def _get_order_from_move(self, cr, uid, ids, context=None):
        result = set()
        move_obj = self.pool.get('account.move')
        for move in move_obj.browse(cr, uid, ids, context=context):
            for order in move.order_ids:
                result.add(order.id)
        return list(result)

    def _get_order_from_line(self, cr, uid, ids, context=None):
        so_obj = self.pool.get('sale.order')
        return so_obj._get_order(cr, uid, ids, context=context)

    def _pay_info(self, cr, uid, ids, field_names=None, arg=False, context=None):
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

        for purchase in self.browse(cr, uid, ids, context=context):
            pre_paid = 0.0
            inv_paid = 0.0
            #check the prepaymenys
            for line in purchase.payment_ids:    
#                pre_paid += line.debit - line.credit
                if not line.reconcile_id:
                    if not line.reconcile_partial_id:
                        pre_paid += line.amount_residual
                    else:
                        #if move is partial reconciled, then only the amount_residual is negative then this line is also need more lines to reconcile it
                        if line.amount_residual > 0:
                             pre_paid += line.amount_residual
                
            #check the invoice paid            
            for invoice in purchase.invoice_ids:
                if invoice.state not in ('draft','cancel'):
                    if invoice.type == 'in_refund':
                        inv_paid -= (invoice.amount_total - invoice.residual)
                    else:                        
                        inv_paid += (invoice.amount_total - invoice.residual)
               
            res[purchase.id] = {
                    'amount_paid': inv_paid + pre_paid, 
                    'residual': purchase.amount_total - inv_paid - pre_paid,
                    'paid_done': purchase.amount_total == (inv_paid + pre_paid),
                    'payment_exists': (inv_paid + pre_paid) > 0,
                    }
        return res
    
    def _payment_exists(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for order in self.browse(cursor, user, ids, context=context):
            res[order.id] = bool(order.payment_ids)
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

        for purchase in self.browse(cr, uid, ids, context=context):
            #check the invoice paid  
            inv_pay_ids = []          
            for invoice in purchase.invoice_ids:
                if invoice.state not in ('draft','cancel'):
                    inv_pay_ids.extend(map(lambda x: x.id, invoice.payment_ids))
            res[purchase.id] = inv_pay_ids
        return res
    
    _columns = {
        'payment_ids': fields.many2many('account.move.line', string='Advance Payments'),
        'payment_moves': fields.many2many('account.move', string='Payment Moves', readonly=True, states={'approved': [('readonly', False)]}, ),
        'amount_paid': fields.function(_pay_info, multi='pay_info', string='Amount Paid', type='float', readonly=True,digits_compute=dp.get_precision('Account')),        
        'residual': fields.function(_pay_info, multi='pay_info', string='Balance', type='float', readonly=True,digits_compute=dp.get_precision('Account')),
        'paid_done': fields.function(_pay_info, multi='pay_info', string='Paid Done', type='boolean', readonly=True),        
        'payment_exists': fields.function(_pay_info, multi='pay_info', string='Has payments', type='boolean', readonly=True,help="It indicates that purchase order has at least one payment."),
        'inv_pay_ids': fields.function(_inv_pay_ids,relation='account.move.line', type='many2many', string='Invoice Payments'),
    }

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default['payment_ids'] = False
        default['payment_moves'] = False
        return super(purchase_order, self).copy(cr, uid, id,
                                            default, context=context)

    def add_payment(self, cr, uid, ids, journal_id, amount,
                    date=None, description=None, context=None):
        """ Generate payment move lines of a certain amount linked
        with the order. """
        if isinstance(ids, Iterable):
            assert len(ids) == 1, "one purchase order at a time can be paid"
            ids = ids[0]
        journal_obj = self.pool.get('account.journal')

        order = self.browse(cr, uid, ids, context=context)
        if date is None:
            date = order.date_order
        context = context.update({'company_id': order.company_id and order.company_id.id or False})
        journal = journal_obj.browse(cr, uid, journal_id, context=context)
        self._add_payment(cr, uid, order, journal, amount, date, description, context=context)
        return True

    def _add_payment(self, cr, uid, order, journal, amount, date, description=None, context=None):
        """ Generate move lines entries to pay the order. """
        move_obj = self.pool.get('account.move')
        period_obj = self.pool.get('account.period')
        period_id = period_obj.find(cr, uid, dt=date, context=context)[0]
        period = period_obj.browse(cr, uid, period_id, context=context)
        move_name =  self._get_payment_move_name(cr, uid, journal,
                                                period, context=context)
        description = '%s : %s'%(_('Supplier Advance Payment'),description)
        move_vals = self._prepare_payment_move(cr, uid, move_name, order,
                                               journal, period, date, description,
                                               context=context)
        move_lines = self._prepare_payment_move_line(cr, uid, move_name, order,
                                                     journal, period, amount,
                                                     date, description, context=context)

        move_vals['line_id'] = [(0, 0, line) for line in move_lines]
        _logger.error('--- Advance payment move : %s ', move_vals)
        move_obj.create(cr, uid, move_vals, context=context)

    def _get_payment_move_name(self, cr, uid, journal, period, context=None):
        if context is None:
            context = {}
        seq_obj = self.pool.get('ir.sequence')
        sequence = journal.sequence_id

        if not sequence:
            raise osv.except_osv(
                _('Configuration Error'),
                _('Please define a sequence on the journal %s.') %
                journal.name)
        if not sequence.active:
            raise osv.except_osv(
                _('Configuration Error'),
                _('Please activate the sequence of the journal %s.') %
                journal.name)

        ctx = context.copy()
        ctx['fiscalyear_id'] = period.fiscalyear_id.id
        name = seq_obj.next_by_id(cr, uid, sequence.id, context=ctx)
        return name

    def _prepare_payment_move(self, cr, uid, move_name, order, journal,
                              period, date, description, context=None):
        return {'name': move_name,
                'journal_id': journal.id,
                'date': date,
                'ref': order.name,
                'period_id': period.id,
                'purchase_ids': [(4, order.id)],
                'narration':description,
                }

    def _prepare_payment_move_line(self, cr, uid, move_name, order, journal,
                                   period, amount, date, description, context=None):
        """ """
        partner_obj = self.pool.get('res.partner')
        currency_obj = self.pool.get('res.currency')
        partner = partner_obj._find_accounting_partner(order.partner_id)

        company = journal.company_id

        currency_id = False
        amount_currency = 0.0
        if journal.currency and journal.currency.id != company.currency_id.id:
            currency_id = journal.currency.id
            amount_currency, amount = (amount,
                                       currency_obj.compute(cr, uid,
                                                            currency_id,
                                                            company.currency_id.id,
                                                            amount,
                                                            context=context))

        # payment line (bank / cash)
        credit_line = {
            'name': description,
            'debit': 0.0,
            'credit': amount,
            'account_id': journal.default_credit_account_id.id,
            'journal_id': journal.id,
            'period_id': period.id,
            'partner_id': partner.id,
            'date': date,
            'amount_currency': -amount_currency,
            'currency_id': currency_id,
        }

        # payment line (payable)
        debit_line = {
            'name': description,
            'debit': amount,
            'credit': 0.0,
            'account_id': partner.property_account_prepayable.id,
            'journal_id': journal.id,
            'period_id': period.id,
            'partner_id': partner.id,
            'date': date,
            'amount_currency': amount_currency,
            'currency_id': currency_id,
            'purchase_ids': [(4, order.id)],
        }
        return debit_line, credit_line

    def action_cancel(self, cr, uid, ids, context=None):
        for po in self.browse(cr, uid, ids, context=context):
            if po.payment_ids:
                raise osv.except_osv(
                    _('Cannot cancel this purchase order!'),
                    _('Payment entries are linked with the purchase order.'))
        return super(purchase_order, self).action_cancel(cr, uid, ids, context=context)
    
class account_move_line(orm.Model):
    _inherit = 'account.move.line'

    _columns = {
        'purchase_ids': fields.many2many('purchase.order', string='Purchase Orders'),
    }    
class account_move(osv.osv):
    _inherit="account.move"
    _columns = {
        'purchase_ids': fields.many2many('purchase.order', string='Purchase Orders'),
    }
       
    def unlink(self, cr, uid, ids, context=None, check=True):
        #if the move's line generated by the sales payment, then cancel this entry firstly
        moves = self.browse(cr,uid,ids,context)
        for move in moves:
            if move.state == 'posted' and move.purchase_ids:
                self.button_cancel(cr,uid,[move.id],context=context)
        #execute the delete action
        result = super(account_move, self).unlink(cr, uid, ids, context=context)
        return result    