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
import time

class emp_reimburse_line(osv.osv):
    _name = "emp.reimburse.line"
    _description = "Employee Reimburse Line"
    _columns = {
        'order_id': fields.many2one('emp.reimburse', 'Reimburse', ondelete='cascade', select=True),
        'emp_id': fields.related('order_id','emp_id',type='many2one',relation='hr.employee',string='Employee'),
        'name': fields.char('Reimburse Note', size=128, required=True, select=True),
        'date_value': fields.date('Date', required=True),
        'amount': fields.float('Amount', digits_compute=dp.get_precision('Account')),
        }
    _defaults = {
        'date_value': lambda *a: time.strftime('%Y-%m-%d'),
    }
    _order = "date_value desc"

emp_reimburse_line()

class emp_reimburse_reconcile(osv.osv):
    _name = 'emp.reimburse.reconcile'
    _description = 'Reconcile Lines'
    _order = "move_line_id"

    def _compute_amount(self, cr, uid, ids, name, args, context=None):
        rs_data = {}
        for line in self.browse(cr, uid, ids, context=context):
            res = {'amount_original':0.0, 'amount_unreconciled':0.0}
            if line.move_line_id:
                res['amount_original'] = line.move_line_id.credit or line.move_line_id.debit or 0.0
                res['amount_unreconciled'] = abs(line.move_line_id.amount_residual)
            rs_data[line.id] = res
        return rs_data
    
    _columns = {
        'order_id':fields.many2one('emp.reimburse', 'Reimburse', required=1, ondelete='cascade'),
        'name':fields.char('Description', size=256),
        'account_id':fields.many2one('account.account','Account', required=True),
        'emp_id':fields.related('order_id', 'emp_id', type='many2one', relation='hr.employee', string='Employee'),
        'amount':fields.float('Amount', digits_compute=dp.get_precision('Account')),
        'reconcile': fields.boolean('Full Reconcile'),
        'type':fields.selection([('dr','Debit'),('cr','Credit')], 'Dr/Cr'),
        'move_line_id': fields.many2one('account.move.line', 'Journal Item'),
        'date_original': fields.related('move_line_id','date', type='date', relation='account.move.line', string='Date', readonly=1),
        'date_due': fields.related('move_line_id','date_maturity', type='date', relation='account.move.line', string='Due Date', readonly=1),
        'amount_original': fields.function(_compute_amount, multi='dc', type='float', string='Original Amount', store=True, digits_compute=dp.get_precision('Account')),
        'amount_unreconciled': fields.function(_compute_amount, multi='dc', type='float', string='Open Balance', store=True, digits_compute=dp.get_precision('Account')),
        'company_id': fields.related('order_id','company_id', relation='res.company', type='many2one', string='Company', store=True, readonly=True),
        'reconile_move_line_id': fields.many2one('account.move.line', 'Reconcile Journal Item'),
    }
    _defaults = {
        'name': '',
    }

    def onchange_reconcile(self, cr, uid, ids, reconcile, amount, amount_unreconciled, context=None):
        vals = {'amount': 0.0}
        if reconcile:
            vals = { 'amount': amount_unreconciled}
        return {'value': vals}

    def onchange_amount(self, cr, uid, ids, amount, amount_unreconciled, context=None):
        vals = {}
        if amount:
            vals['reconcile'] = (amount == amount_unreconciled)
        resu = {'value': vals}
        if amount > amount_unreconciled:
            mess = _('The reconcile amount can not be greater than the balance %s!')%(amount_unreconciled,)
            resu['warning'] = {'title': _('Error!'), 'message': mess}
            resu['value']['amount'] = amount_unreconciled
            vals['reconcile'] = True
        return resu

emp_reimburse_reconcile()

class emp_reimburse(osv.osv):
    _name = 'emp.reimburse'
    _inherit = ['mail.thread']
    _description = "Employee Reimburse Money"
    _rec_name = 'id'
    _order = 'id desc'
    def _amount(self, cr, uid, ids, field_name, arg, context=None):
        res= {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = {}
            total = 0.0
            amount_debit = 0.0
            amount_credit = 0.0
            for line in order.line_ids:
                total += line.amount
                
            if order.line_dr_ids:
                res[order.id]['has_dr'] = True
                for line in order.line_dr_ids:
                    amount_debit += line.amount
            else:
                res[order.id]['has_dr'] = False
                
            if order.line_cr_ids:
                res[order.id]['has_cr'] = True
                for line in order.line_cr_ids:
                    amount_credit += line.amount
            else:
                res[order.id]['has_cr'] = False
                
            amount_pay = total + amount_debit - amount_credit
            res[order.id]['amount'] = total
            res[order.id]['amount_debit'] = amount_debit
            res[order.id]['amount_credit'] = amount_credit
            res[order.id]['amount_pay'] = amount_pay
        return res
    _columns = {
        'emp_id': fields.many2one('hr.employee',string='Employee', required=True,select=True,readonly=True, states={'draft':[('readonly',False)]}),
        'state':fields.selection(
            [('draft','Draft'),
             ('done','Done'),
             ('cancelled','Cancel')
            ], 'Status', readonly=True, size=32, track_visibility='onchange',),
        'date': fields.date('Date',readonly=True, states={'draft':[('readonly',False)]}),
#        'amount':fields.float('Amount', digits_compute=dp.get_precision('Account'),readonly=True, states={'draft':[('readonly',False)]}),
        'amount': fields.function(_amount, string='Reimburse Amount', type='float',digits_compute=dp.get_precision('Account'), multi='amount'),
        'amount_debit': fields.function(_amount, string='Debit Amount', type='float',digits_compute=dp.get_precision('Account'), multi='amount'),
        'amount_credit': fields.function(_amount, string='Credit Amount', type='float',digits_compute=dp.get_precision('Account'), multi='amount'),
        'amount_pay': fields.function(_amount, string='Pay Amount', type='float',digits_compute=dp.get_precision('Account'), multi='amount'),
        'journal_cash_id': fields.many2one('account.journal', 'Cash Journal', required=True,readonly=True, states={'draft':[('readonly',False)]}),
        'deduct_salary': fields.boolean('Deduct Salary',readonly=True, states={'draft':[('readonly',False)]}),
        'property_account_salary': fields.property(
            'account.account',
            type='many2one',
            relation='account.account',
            string="Employee Salary Account",
            view_load=True,
            domain="[('type','=','payable')]",
            required=False),        
        'property_account_emp_reimburse': fields.property(
            'account.account',
            type='many2one',
            relation='account.account',
            string="Employee Reimburse Account",
            view_load=True,
            domain="[('type','!=','view')]",
            required=True),
        'description': fields.char('Description', size=128, required=False),
        'company_id': fields.many2one('res.company', 'Company', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'move_id': fields.many2one('account.move', 'Accounting Entry', readonly=True),
        'move_state': fields.related('move_id', 'state', type='selection', selection=[('draft','Unposted'), ('posted','Posted')], string='Entry State'),
        'move_lines': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Accounting Items', readonly=True),
        'line_ids': fields.one2many('emp.reimburse.line', 'order_id', 'Reimbursement Detail', readonly=True, states={'draft':[('readonly',False)]} ),
        'has_cr': fields.function(_amount, string='Has dedits', type='boolean',  multi='amount'),
        'has_dr': fields.function(_amount, string='Has credits',  type='boolean',  multi='amount'),
        'line_dr_ids':fields.one2many('emp.reimburse.reconcile','order_id','Debits',
            domain=[('type','=','dr')], context={'default_type':'dr'}, readonly=True, states={'draft':[('readonly',False)]}),
        'line_cr_ids':fields.one2many('emp.reimburse.reconcile','order_id','Credits',
            domain=[('type','=','cr')], context={'default_type':'cr'}, readonly=True, states={'draft':[('readonly',False)]}),        
    }
    def default_get(self, cr, uid, fields_list, context=None):
        resu = super(emp_reimburse,self).default_get(cr, uid, fields_list, context)
        journal_cash_id = self.pool.get('account.journal').search(cr ,uid,[('type','=','cash')],context=context)[0]
        resu.update({'journal_cash_id':journal_cash_id})
        return resu
    
    _defaults = {
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.voucher',context=c),
        'state': 'draft',
        'date': fields.date.context_today
    }
        
    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        if context is None: context = {}
        return [(obj_id, '[%s]%s'%(obj_id,_(self._description))) for obj_id in ids]
        
    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default.update({'move_id':None,'line_dr_ids':None,'line_cr_ids':None})
        return super(emp_reimburse, self).copy(cr, uid, id, default, context)
    
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
        return super(emp_reimburse,self).unlink(cr, uid, ids, context)
    def get_emp_borrow(self, cr, uid, ids, context=None):
        return self.onchange_emp_id(cr, uid, ids, context['emp_id'], context)
    def onchange_emp_id(self, cr, uid, ids, emp_id, context=None):
        if not emp_id:
            return {'value':{}}
        if context is None:
            context = {}
        vals = {'line_dr_ids': [] ,'line_cr_ids': [] ,'has_dr':False, 'has_cr': False,}
        mvln_obj = self.pool.get('account.move.line')
        mvln_ids = []
        #find the employee borrow money orders's unreconciled account move lines
        emp_borrow_obj = self.pool.get('emp.borrow')
        borrow_ids = emp_borrow_obj.search(cr, uid, [('emp_id','=',emp_id),('state','=','done')],context=context)
        for borrow in emp_borrow_obj.browse(cr, uid, borrow_ids, context=context):
            for mvln in borrow.move_lines:
                if mvln.account_id.type == 'receivable' and not mvln.reconcile_id and mvln.state=='valid':
                    mvln_ids.append(mvln.id)
        mvln_ids.reverse()
        #reimburse dr/cr line creation
        account_move_lines = mvln_obj.browse(cr, uid, mvln_ids, context=context)
        for line in account_move_lines:
            if line.reconcile_partial_id and line.amount_residual <= 0:
                continue
            amount_original = line.credit or line.debit or 0.0
            amount_unreconciled = abs(line.amount_residual)
            rs = {
                'name':line.move_id.name,
                'type': line.credit and 'dr' or 'cr',
                'move_line_id':line.id,
                'account_id':line.account_id.id,
                'amount_original': amount_original,
                'amount': 0.0,
                'date_original':line.date,
                'date_due':line.date_maturity,
                'amount_unreconciled': amount_unreconciled,
            }

            if rs['type'] == 'cr':
                vals['line_cr_ids'].append(rs)
            else:
                vals['line_dr_ids'].append(rs)
                
            if len(vals['line_cr_ids']) > 0:
                vals['has_cr'] = True
            if len(vals['line_dr_ids']) > 0:
                vals['has_dr'] = True
        return {'value':vals}
    def move_create(self, cr, uid, ids, context=None):
        for id in ids:
            move_id = self.move_create_single(cr, uid, id, context=None)
            self.write(cr, uid, [id], {'move_id':move_id}, context=context)
        
    def move_create_single(self, cr, uid, id, context=None):
        """ Generate move lines entries to pay the order. """
        move_obj = self.pool.get('account.move')
        mvln_obj = self.pool.get('account.move.line')
        period_obj = self.pool.get('account.period')
        
        trans = self.browse(cr, uid, id, context=context)
        period_id = period_obj.find(cr, uid, dt=trans.date, context=context)[0]
        period = period_obj.browse(cr, uid, period_id, context=context)
        journal = trans.journal_cash_id
        
        move_name =  self._get_move_name(cr, uid, journal, period, context=context)
        move_vals = self._prepare_move(cr, uid, move_name, trans, journal, period,context=context)
        move_id = move_obj.create(cr, uid, move_vals, context=context)
        move_lines = self._prepare_move_line(cr, uid, move_name, trans,journal, period, context=context)
        
        to_reconcile_mvlns = []
        reim_recon_obj = self.pool.get('emp.reimburse.reconcile')
        #to make debit first then credit
        move_lines.reverse()
        for mvln_vals in move_lines:
            #create move line
            mvln_vals['move_id'] = move_id
            new_mvln_id = mvln_obj.create(cr, uid, mvln_vals, context=context)
            if 'to_reconcile_mvln' in mvln_vals:
                #add to the reconcile paris
                to_reconcile_mvlns.append([mvln_vals['to_reconcile_mvln'],new_mvln_id])
                #update the dr/cr line's reconcile move line id
                reim_recon_obj.write(cr, uid, [mvln_vals['reimburse_reconcile_id']],{'reconile_move_line_id':new_mvln_id},context=context)
        #reconcile the move lines
        for reconciles in to_reconcile_mvlns:
            writeoff_acc_id = mvln_obj.read(cr, uid, reconciles[0], ['account_id'],context=context)['account_id']
            mvln_obj.reconcile_partial(cr, uid, reconciles, writeoff_acc_id=writeoff_acc_id, writeoff_period_id=period_id, writeoff_journal_id=journal.id)
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
                'ref': _('ERM[%s]')%(order.id,),
                'period_id': period.id,
                'narration':_('Employee Reimburse Money, %s\n%s')%(order.emp_id.name,order.description or ''),
                }

    def _prepare_move_line(self, cr, uid, move_name, order, journal, period,  context=None):
        """ """
        mv_lines = []
        #reimburse lines, record on debit
        for line in order.line_ids:        
            debit_line = {
                'name': '%s,%s'%(order.emp_id.name,line.name),
                'debit': line.amount,
                'credit': 0,
                'account_id': order.property_account_emp_reimburse.id,
                'journal_id': journal.id,
                'period_id': period.id,
                'date': order.date,
                'date_biz': order.date,
                'amount_currency': 0.0,
                'currency_id': False,
            }
            mv_lines.append(debit_line)
        #reconcile lines on debit
        for line in order.line_dr_ids:
            if line.amount > 0:
                debit_line = {
                    'name': _('Reimburse reconcile[%s]')%(order.emp_id.name,),
                    'debit': line.amount,
                    'credit': 0,
                    'account_id': line.account_id.id,
                    'journal_id': journal.id,
                    'period_id': period.id,
                    'date': order.date,
                    'date_biz': order.date,
                    'amount_currency': 0.0,
                    'currency_id': False,
                    'reimburse_reconcile_mvln': line.move_line_id.id,
                    'reimburse_reconcile_id': line.id
                }
                mv_lines.append(debit_line)
        #the cash line
        if order.amount_pay != 0:
            amount_pay_dr_prefix = 0
            amount_pay_cr_prefix = 0
            if order.amount_pay > 0:
                amount_pay_cr_prefix = 1
            if order.amount_pay < 0:
                amount_pay_dr_prefix = -1
            cash_line = {
                'name': _('Reimburse[%s]')%(order.emp_id.name,),        
                'debit': amount_pay_dr_prefix*order.amount_pay,
                'credit': amount_pay_cr_prefix*order.amount_pay,
                'account_id': order.journal_cash_id.default_credit_account_id.id,
                'journal_id': journal.id,
                'period_id': period.id,
                'date': order.date,
                'date_biz': order.date,
                'amount_currency': 0.0,
                'currency_id': False,
            }
            if order.deduct_salary:
                cash_line['account_id'] = order.property_account_salary.id
            mv_lines.append(cash_line)
        #reconcile lines on credit
        for line in order.line_cr_ids:
            if line.amount > 0:
                debit_line = {
                    'name': _('Reimburse reconcile[%s]')%(order.emp_id.name,),
                    'debit': 0,
                    'credit': line.amount,
                    'account_id': line.account_id.id,
                    'journal_id': journal.id,
                    'period_id': period.id,
                    'date': order.date,
                    'date_biz': order.date,
                    'amount_currency': 0.0,
                    'currency_id': False,
                    'to_reconcile_mvln': line.move_line_id.id,
                    'reimburse_reconcile_id': line.id
                }
                mv_lines.append(debit_line)
        return mv_lines          
                
