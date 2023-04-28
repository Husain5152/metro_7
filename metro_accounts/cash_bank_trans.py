# -*- coding: utf-8 -*-
##############################################################################
#
#    sale_quick_payment for OpenERP
#    Copyright (C) 2011 Akretion Sébastien BEAU <sebastien.beau@akretion.com>
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

class cash_bank_trans(osv.osv):
    _name = 'cash.bank.trans'
    _inherit = ['mail.thread']
    _description = "Withdraw/Deposit Order"
    _rec_name = 'id'
    _order = 'id desc'
    _columns = {
        'state':fields.selection(
            [('draft','Draft'),
             ('done','Done'),
             ('cancelled','Cancel')
            ], 'Status', readonly=True, size=32, track_visibility='onchange',),                
        'date': fields.date('Date',readonly=True, states={'draft':[('readonly',False)]}),
        'type': fields.selection([('c2b','Withdraw/Deposit Order'),('b2b','Bank Trans'),('o_pay_rec','Other Payments/Receipts')],'Order Type',select=True,required=True,readonly=True),
        'trans_type': fields.selection([('withdraw','Withdraw'),('deposit','Deposit')],'Type',select=True,required=True,readonly=True, states={'draft':[('readonly',False)]}),
        'amount':fields.float('Amount', digits_compute=dp.get_precision('Account'),readonly=True, states={'draft':[('readonly',False)]}),
        'journal_cash_id': fields.many2one('account.journal', 'Cash Journal', required=False,readonly=True, states={'draft':[('readonly',False)]}),
        'journal_bank_id': fields.many2one('account.journal', 'Bank Journal', required=True,readonly=True, states={'draft':[('readonly',False)]}),
        'description': fields.char('Description', size=128, required=False),
        'company_id': fields.many2one('res.company', 'Company', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'move_id': fields.many2one('account.move', 'Accounting Entry', readonly=True),
        'move_state': fields.related('move_id', 'state', type='selection', selection=[('draft','Unposted'), ('posted','Posted')], string='Entry State', readonly=True),
        'move_lines': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Entry Items', readonly=True),
        #account for other payments/receipts
        'account_to_id': fields.many2one('account.account', 'To account', domain=[('type','!=','view')],required=True,readonly=True, states={'draft':[('readonly',False)]}),
        'employee_id': fields.many2one('hr.employee', "Employee"), #add a new string for "jing shou ren" to record who have the payment
    }
    def default_get(self, cr, uid, fields_list, context=None):
        resu = super(cash_bank_trans,self).default_get(cr, uid, fields_list, context)
        if context.get('default_type',False) == 'c2b':
            #for the cash bank tranfer, auto set the journal
            journal_cash_id = self.pool.get('account.journal').search(cr ,uid,[('type','=','cash')],context=context)[0]
            journal_bank_id = self.pool.get('account.journal').search(cr ,uid,[('type','=','bank')],context=context)[0]
            resu.update({'journal_cash_id':journal_cash_id,'journal_bank_id':journal_bank_id})
        return resu    
    
    _defaults = {
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.voucher',context=c),
        'state': 'draft',
        'date': fields.date.context_today,
        'type':'c2b'
    }
    def _check_amount(self, cr, uid, ids, context=None):
        for pay in self.browse(cr, uid, ids, context=context):
            if pay.amount <= 0:
                return False
        return True
    
    _constraints = [(_check_amount, 'Amount only must be greater than zero.', ['amount'])]    
    
    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        if context is None: context = {}
        sel_types = {}
        for sel in self._columns['type'].selection:
            sel_types[sel[0]] = sel[1]
            
        obj_types = self.read(cr, uid, ids, ['type','trans_type'], context=context)
        ret_names = []
        for obj_type in obj_types:
            name_prefix = sel_types[obj_type['type']]
            if obj_type['type'] == 'o_pay_rec':
                name_prefix = 'Other Payments' if obj_type['trans_type'] == 'withdraw' else 'Other Receipts'
            #get the different title by various type
            data_name = '%s[%s]'%(_(name_prefix), obj_type['id'])
            ret_names.append((obj_type['id'], data_name))
    
        return ret_names
        
    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default.update({'move_id':None})
        return super(cash_bank_trans, self).copy(cr, uid, id, default, context)
    
    def action_done(self, cr, uid, ids, context=None):
        self.trans_move_create(cr, uid, ids)
        self.write(cr, uid, ids, {'state':'done'})
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        for trans in self.browse(cr, uid, ids, context=context):
            move_ids = []
            if trans.move_id:
                if trans.move_id.state == 'posted':
                    raise osv.except_osv(_('Error!'), _('The accounting entry to the order was posted, can not be deleted!'))
                else:
                    move_ids.append(trans.move_id.id)
        if move_ids:     
            self.pool.get('account.move').unlink(cr, uid, move_ids, context)
        self.write(cr, uid, ids, {'state':'cancelled'})
        return True
    
    def action_to_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'draft'})
        return True
    
    def unlink(self, cr, uid, ids, context=None):
        for data in self.read(cr, uid, ids, ['state'], context=context):
            if data['state'] not in ('cancelled','draft'):
                raise osv.except_osv(_('Error!'), _('Only order under Draft or Cancel can be delete!'))
        return super(cash_bank_trans,self).unlink(cr, uid, ids, context)

    def trans_move_create(self, cr, uid, ids, context=None):
        for id in ids:
            move_id = self.trans_move_create_single(cr, uid, id, context=None)
            self.write(cr, uid, [id], {'move_id':move_id}, context=context)
        
    def trans_move_create_single(self, cr, uid, id, context=None):
        """ Generate move lines entries to pay the order. """
        move_obj = self.pool.get('account.move')
        period_obj = self.pool.get('account.period')
        
        trans = self.browse(cr, uid, id, context=context)
        period_id = period_obj.find(cr, uid, dt=trans.date, context=context)[0]
        period = period_obj.browse(cr, uid, period_id, context=context)
        journal = None
        if trans.type != 'o_pay_rec':
            journal = trans.trans_type=='withdraw' and trans.journal_cash_id or trans.journal_bank_id
        else:
            journal = trans.journal_bank_id
        
        move_name =  self._get_payment_move_name(cr, uid, journal, period, context=context)
        move_vals = self._prepare_payment_move(cr, uid, move_name, trans, journal, period,context=context)
        move_lines = self._prepare_payment_move_line(cr, uid, move_name, trans,journal, period, context=context)

        move_vals['line_id'] = [(0, 0, line) for line in move_lines]
        move_id = move_obj.create(cr, uid, move_vals, context=context)
        return move_id

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

    def _prepare_payment_move(self, cr, uid, move_name, order, journal,period, context=None):
        ref_prefix = 'CashBankTrans[%s]'
        if order.type == 'c2b':
            ref_prefix = 'CashBankTrans[%s]'
        elif  order.type == 'b2b':
            ref_prefix = 'BankTrans[%s]'
        elif  order.type == 'o_pay_rec':
            ref_prefix = order.trans_type == 'withdraw' and 'OtherPayments[%s]' or 'OtherReceipts[%s]' 
        return {'name': move_name,
                'journal_id': journal.id,
                'date': order.date,
                'ref': _(ref_prefix)%(order.id,),
                'period_id': period.id,
                'narration':order.description,
                }

    def _prepare_payment_move_line(self, cr, uid, move_name, order, journal, period,  context=None):
        """ """
        currency_obj = self.pool.get('res.currency')

        company = journal.company_id

        currency_id = False
        amount = order.amount
        amount_currency = 0.0
        if journal.currency and journal.currency.id != company.currency_id.id:
            currency_id = journal.currency.id
            amount_currency, amount = (order.amount,
                                       currency_obj.compute(cr, uid,
                                                            currency_id,
                                                            company.currency_id.id,
                                                            order.amount,
                                                            context=context))
        cash_debit_prefix = 0
        bank_debit_prefix = 0        
        cash_credit_prefix = 0
        bank_credit_prefix = 0
        ln_desc = ''
        
        if order.type == 'c2b':
            ln_cash_desc = order.trans_type == 'withdraw' and _('Withdraw') or _('Deposit')
            ln_bank_desc = ln_cash_desc
        elif  order.type == 'b2b':
            #for the 'b2', the trans_type is 'withdraw'
            ln_cash_desc = _('In')
            ln_bank_desc = _('Out')
        elif  order.type == 'o_pay_rec':
            ln_bank_desc = order.trans_type == 'withdraw' and _('Other Payments') or _('Other Receipts')
            ln_cash_desc = ln_bank_desc
            
        if order.trans_type == 'withdraw':
            cash_debit_prefix = 1
            bank_credit_prefix = 1
        if order.trans_type == 'deposit':
            cash_credit_prefix = 1
            bank_debit_prefix = 1
        
        # cash line
        cash_line = {
            'name': ln_cash_desc,
            'debit': cash_debit_prefix*amount,
            'credit': cash_credit_prefix*amount,
            'account_id': order.type != 'o_pay_rec' and order.journal_cash_id.default_debit_account_id.id or order.account_to_id.id,
            'journal_id': journal.id,
            'period_id': period.id,
            'date': order.date,
            'date_biz': order.date,
            'amount_currency': amount_currency,
            'currency_id': currency_id,
        }
        #bank line
        bank_line = {
            'name': ln_bank_desc,
            'debit': bank_debit_prefix*amount,
            'credit': bank_credit_prefix*amount,
            'account_id': order.journal_bank_id.default_debit_account_id.id,
            'journal_id': journal.id,
            'period_id': period.id,
            'date': order.date,
            'date_biz': order.date,
            'amount_currency': amount_currency,
            'currency_id': currency_id,
        }
        return cash_line, bank_line                
                
