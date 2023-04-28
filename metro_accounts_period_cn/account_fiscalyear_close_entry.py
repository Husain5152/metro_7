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

from openerp.osv import fields, osv
from openerp.tools.translate import _

class account_fiscalyear_close_entry(osv.osv_memory):
    """
    Generate Closing entries for The fiscal year will be close
    """
    _name = "account.fiscalyear.close.entry"
    _description = "Generate Period Closing Entries"
    _columns = {
       'fiscalyear_id': fields.many2one('account.fiscalyear', 'Closing Year', required=True, readonly=True),
       'journal_id': fields.many2one('account.journal', 'Closing Journal', domain="[('company_id','=', company_id),('year_close','=', True), ('type','=','situation')]", required=True),
       'notes': fields.char('Notes',size=64, required=True),       
       'company_id': fields.many2one('res.company', 'Company', required=True, select=1),
       'auto_opt': fields.selection([('none','None'),('post','Post Entry'),('post_close','Post Entry and Close Last Period and Fiscal Year')], 'Auto options', required=True),
    }
    _defaults={'auto_opt':'none'}
    
    def default_get(self, cr, uid, fields, context=None):
        defaults = super(account_fiscalyear_close_entry, self).default_get(cr, uid, fields, context=context)
        if not defaults:
            defaults = {}
            
        defaults['notes'] =  _('Year closing entry')
        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
            
        if 'fiscalyear_id' in fields:
            year_obj = self.pool.get('account.fiscalyear')
            #find the earliest year that not done, 第一个打开状态的会计年度, 时间最早的state='draft'的
            year_ids = year_obj.search(cr, uid, [ ('state','!=','done'), ('company_id','=',company_id)], order='date_start', limit=1, context=context)
            if year_ids:
                defaults['fiscalyear_id'] = year_ids[0]
                year_name = year_obj.read(cr, uid, year_ids[0], ['name'], context=context)['name']
                defaults['notes'] = _('Year closing entry for %s')%(year_name,)
        if not defaults.get('fiscalyear_id'):
            raise osv.except_osv(_('Error!'), _('No available fiscal year was found, please make sure there are years with "Draft" state'))
        
        #年结账簿-默认为本公司的year_close=1, type=('situation', 'Opening/Closing Situation')的account_journal         
        if 'journal_id' in fields:
            domain = [('company_id', '=', company_id), ('year_close', '=', True), ('type', '=', 'situation')]
            journal_ids = self.pool.get('account.journal').search(cr, uid, domain, context=context)
            if journal_ids:
                defaults['journal_id'] = journal_ids[0]
        
        #default to user's company
        if 'company_id' in fields:    
            defaults['company_id'] = company_id 

        return defaults

    def data_save(self, cr, uid, ids, context=None):
        """
        This function create closing entries for one period
        """

        obj_acc_period = self.pool.get('account.period')
        obj_acc_year = self.pool.get('account.fiscalyear')
        obj_acc_move = self.pool.get('account.move')
        obj_acc_move_line = self.pool.get('account.move.line')
        obj_acc_account = self.pool.get('account.account')
        obj_acc_journal_period = self.pool.get('account.journal.period')
        currency_obj = self.pool.get('res.currency')

        data = self.browse(cr, uid, ids, context=context)[0]
        company = data.company_id
        journal = data.journal_id
        year = data.fiscalyear_id

        if context is None:
            context = {}

        #此年度所有期间必须已经生成结帐凭证(period.account_move_done=True)
        if obj_acc_period.search(cr, uid, [('close_entry_done', '!=', True),('fiscalyear_id', '=', year.id)], context=context):
            raise osv.except_osv(_('Error!'), _('There are periods of this year missing closing entry. In order to close a year, you must generate closing entries for all the periods of this year!'))
        #本年度最后一个会计期间必须已经生成结转凭证, 并且凭证已经登帐, 期间未关闭, find the last period of this year
        last_period_ids = obj_acc_period.search(cr, uid, [('fiscalyear_id','=',year.id)], order="date_stop desc", limit=1, context=context)
        last_period = obj_acc_period.browse(cr, uid, last_period_ids[0], context=context)
        if not last_period.close_entry_done \
                or (last_period.close_move_id and last_period.close_move_id.state != 'posted') \
                or last_period.state == 'done':
            raise osv.except_osv(_('Error!'), _('The last period[%s] of this year must be: \n1.generated closing entry \n2.the closing entry is posted \n3.the last period must keep opening to add the year closing entry.')%(last_period.name,))
        
        #已经有转帐凭证(year.close_move_id),则删除, delete the  closing account move if exist
        if  year.close_entry_done:
            obj_acc_year.cancel_close_entry(cr, uid, [year.id], context=context)
        
        #journal's restriction checking
        if not journal.default_credit_account_id or not journal.default_debit_account_id:
            raise osv.except_osv(_('User Error!'),_('The journal must have default credit and debit account.'))
        if  journal.entry_posted or not journal.year_close:
            raise osv.except_osv(_('User Error!'),_('The journal must be without the Skipping draft state option checked and for year close.'))            
            
        #create the opening move
        vals = {
            'name': '/',
            'journal_id': journal.id,
            'period_id': last_period.id,
            'date': last_period.date_stop,
            'narration': data.notes,
            'company_id': company.id
        }
        move_id = obj_acc_move.create(cr, uid, vals, context=context)
        
        ctx_account = {'fiscalyear': year.id}            
        query_line = obj_acc_move_line._query_get(cr, uid,obj='account_move_line', context=ctx_account)
        
        #结转本年利润/未分配利润结转
        #本年利润科目
        account  = obj_acc_account.browse(cr, uid, journal.default_debit_account_id.id, context=ctx_account)
        balance = account.balance
        balance_in_currency = 0.0
        debit = 0.0
        credit = 0.0
        if account.currency_id:
            cr.execute('SELECT sum(COALESCE(amount_currency,0.0)) as balance_in_currency FROM account_move_line ' \
                    'WHERE account_id = %s ' \
                        'AND ' + query_line + ' ' \
                        'AND currency_id = %s', (account.id, account.currency_id.id))
            balance_in_currency = cr.dictfetchone()['balance_in_currency']

        company_currency_id = company.currency_id
        if not currency_obj.is_zero(cr, uid, company_currency_id, abs(account.balance)):
            #for the 本年利润, the balance should be in credit
            balance_in_currency = -balance_in_currency
            balance = -account.balance            
            #本年利润结转到相反方向
            debit = balance>0 and balance or 0
            credit = balance<0 and -balance or 0                
            vals = {'move_id':move_id, 
                    'name':_('Year close profit of year transfer - %s')%(year.name,), 
                    'account_id':account.id,
                    'debit': debit, 
                    'credit': credit, 
                    'amount_currency':balance_in_currency,
                    'date_biz':last_period.date_stop}
            obj_acc_move_line.create(cr, uid, vals, context=context)
            
            #未分配利润科目
            debit = balance<0 and -balance or 0
            credit = balance>0 and balance or 0
            vals = {'move_id':move_id, 
                    'name':_('Year close profit wait allocation transfer %s')%(year.name,), 
                    'account_id':journal.default_credit_account_id.id,
                    'debit': debit, 
                    'credit': credit,
                    'date_biz':last_period.date_stop}
            obj_acc_move_line.create(cr, uid, vals, context=context)
                
        year_vals = {}
        #validate the account move
        move = obj_acc_move.browse(cr, uid, move_id, context=context)
        if not move.line_id:
            #if there are no move lines, then remove the created move
            obj_acc_move.unlink(cr, uid, [move_id], context=context)
        else:
            obj_acc_move.validate(cr, uid, [move_id], context=context)
            #create the journal.period object
            journal_period_ids = obj_acc_journal_period.search(cr, uid, [('journal_id', '=', journal.id), ('period_id', '=', last_period.id)])
            if not journal_period_ids:
                journal_period_ids = [obj_acc_journal_period.create(cr, uid, {
                       'name': (journal.name or '') + ':' + (last_period.code or ''),
                       'journal_id': journal.id,
                       'period_id': last_period.id
                   })]        
            year_vals.update({'close_journal_period_id':journal_period_ids[0], 'close_move_id': move_id})
            
        #update period closing data
        year_vals.update({'close_entry_done':True})
        obj_acc_year.write(cr, uid, year.id, year_vals, context=context)
        
        #auto post the closing entry
        if move.line_id and data.auto_opt in('post', 'post_close'):
            obj_acc_move.post(cr, uid, [move.id], context=context)
            
        '''
        auto close the year
        for  the last month of the period_close_type='year', can not do auto close, since the year close entry need to add this period later
        '''
        if data.auto_opt == 'post_close':
            '''
            1.close the last period
            '''
            period_close_obj = self.pool.get('account.period.close')
            #create close object
            c = context.copy()
            c['active_ids'] = [last_period.id]
            period_close_id = period_close_obj.create(cr, uid, {'sure':True}, context=c)
            #do close
            period_close_obj.data_save(cr, uid, [period_close_id], context=c)
            #delete the wizard data
            period_close_obj.unlink(cr, uid, [period_close_id], context=c)
            
            '''
            2.close the year
            '''
            obj_acc_year.action_close(cr, uid, [year.id])

        return {'type': 'ir.actions.act_window_close'}

account_fiscalyear_close_entry()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
