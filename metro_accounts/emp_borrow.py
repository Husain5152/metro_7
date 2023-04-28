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

class emp_borrow(osv.osv):
    _name = 'emp.borrow'
    _inherit = ['mail.thread']
    _description = "Employee Borrow Money"
    _rec_name = 'id'
    _order = 'id desc'
    def _check_reimbursed(self, cr, uid, ids, name, args, context=None):
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = any([((line.account_id.type, 'in', ('receivable')) and line.reconcile_id) for line in order.move_lines])
        return res   
    _columns = {
        'emp_id': fields.many2one('hr.employee',string='Employee', required=True,select=True,readonly=True, states={'draft':[('readonly',False)]}),
        'state':fields.selection(
            [('draft','Draft'),
             ('done','Done'),
             ('cancelled','Cancel')
            ], 'Status', readonly=True, size=32, track_visibility='onchange',),
        'date': fields.date('Date',readonly=True, states={'draft':[('readonly',False)]}),
        'amount':fields.float('Amount', digits_compute=dp.get_precision('Account'),readonly=True, states={'draft':[('readonly',False)]}),
        'journal_cash_id': fields.many2one('account.journal', 'Cash Journal', required=True,readonly=True, states={'draft':[('readonly',False)]}),
        'property_account_emp_borrow': fields.property(
            'account.account',
            type='many2one',
            relation='account.account',
            string="Employee Borrow Account",
            view_load=True,
            domain="[('type', '=', 'receivable')]",
            required=True),
        'description': fields.char('Description', size=128, required=False),
        'company_id': fields.many2one('res.company', 'Company', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'move_id': fields.many2one('account.move', 'Accounting Entry', readonly=True),
        'move_state': fields.related('move_id', 'state', type='selection', selection=[('draft','Unposted'), ('posted','Posted')], string='Entry State'),
        'move_lines': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Accounting Items', readonly=True),
        'reimbursed': fields.function(_check_reimbursed, string='Reimbursed', type='boolean', help="The Voucher has been totally paid."),
    } 
    def default_get(self, cr, uid, fields_list, context=None):
        resu = super(emp_borrow,self).default_get(cr, uid, fields_list, context)
        journal_cash_id = self.pool.get('account.journal').search(cr ,uid,[('type','=','cash')],context=context)[0]
        resu.update({'journal_cash_id':journal_cash_id})
        return resu    
    
    _defaults = {
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.voucher',context=c),
        'state': 'draft',
        'date': fields.date.context_today
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
        return [(obj_id, '[%s]%s'%(obj_id,_(self._description))) for obj_id in ids]
        
    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default.update({'move_id':None})
        return super(emp_borrow, self).copy(cr, uid, id, default, context)
    
    def action_done(self, cr, uid, ids, context=None):
        self.move_create(cr, uid, ids)
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
        return super(emp_borrow,self).unlink(cr, uid, ids, context)

    def move_create(self, cr, uid, ids, context=None):
        for id in ids:
            move_id = self.move_create_single(cr, uid, id, context=None)
            self.write(cr, uid, [id], {'move_id':move_id}, context=context)
        
    def move_create_single(self, cr, uid, id, context=None):
        """ Generate move lines entries to pay the order. """
        move_obj = self.pool.get('account.move')
        period_obj = self.pool.get('account.period')
        
        trans = self.browse(cr, uid, id, context=context)
        period_id = period_obj.find(cr, uid, dt=trans.date, context=context)[0]
        period = period_obj.browse(cr, uid, period_id, context=context)
        journal = trans.journal_cash_id
        
        move_name =  self._get_move_name(cr, uid, journal, period, context=context)
        move_vals = self._prepare_move(cr, uid, move_name, trans, journal, period,context=context)
        move_lines = self._prepare_move_line(cr, uid, move_name, trans,journal, period, context=context)

        move_vals['line_id'] = [(0, 0, line) for line in move_lines]
        move_id = move_obj.create(cr, uid, move_vals, context=context)
        return move_id

    def _get_move_name(self, cr, uid, journal, period, context=None):
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

    def _prepare_move(self, cr, uid, move_name, order, journal,period, context=None):
        return {'name': move_name,
                'journal_id': journal.id,
                'date': order.date,
                'ref': _('EBM[%s]')%(order.id,),
                'period_id': period.id,
                'narration':_('Employee Borrow Money, %s\n%s')%(order.emp_id.name,order.description),
                }

    def _prepare_move_line(self, cr, uid, move_name, order, journal, period,  context=None):
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
        ln_desc = _('Borrow[%s]')%(order.emp_id.name,)
        
        # cash line
        credit_line = {
            'name': ln_desc,
            'debit': 0,
            'credit': amount,
            'account_id': order.journal_cash_id.default_credit_account_id.id,
            'journal_id': journal.id,
            'period_id': period.id,
            'date': order.date,
            'date_biz': order.date,
            'amount_currency': amount_currency,
            'currency_id': currency_id,
        }
        #bank line
        debit_line = {
            'name': ln_desc,
            'debit': amount,
            'credit': 0,
            'account_id': order.property_account_emp_borrow.id,
            'journal_id': journal.id,
            'period_id': period.id,
            'date': order.date,
            'date_biz': order.date,
            'amount_currency': amount_currency,
            'currency_id': currency_id,
        }
        return debit_line, credit_line                
                
