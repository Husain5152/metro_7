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

from datetime import datetime
from dateutil.relativedelta import relativedelta

class account_fiscalyear(osv.osv):
    _inherit = "account.fiscalyear"
    _columns = {
        #生成年度结账凭证的时候设置,相关凭证信息
        'close_journal_period_id':fields.many2one('account.journal.period','Close Journal Period', readonly=True),
        'close_move_id':fields.many2one('account.move','Close Account Entries', readonly=True),
        #结转凭证已生成标志, True则证明已经进行了生成月度结账凭证的操作, 但是如果损益类科目没有余额, 没必要生成转账凭证, 则close_journal_period_id/close_move_id没有数据
        'close_entry_done':fields.boolean('Close entry done', readonly=True),
        #do we need generate the opening period for this  year when do periods generating
        'need_open_period':fields.boolean('Generate Opening Period'),
    }

    def create_period(self, cr, uid, ids, context=None, interval=1):
        period_obj = self.pool.get('account.period')
        for fy in self.browse(cr, uid, ids, context=context):
            ds = datetime.strptime(fy.date_start, '%Y-%m-%d')
#            period_obj.create(cr, uid, {
#                    'name':  "%s %s" % (_('Opening Period'), ds.strftime('%Y')),
#                    'code': ds.strftime('00/%Y'),
#                    'date_start': ds,
#                    'date_stop': ds,
#                    'special': True,
#                    'fiscalyear_id': fy.id,
#                })
            #johnw, add the checking of need_open_period
            if fy.need_open_period:
                period_obj.create(cr, uid, {
                        'name':  "%s %s" % (_('Opening Period'), ds.strftime('%Y')),
                        'code': ds.strftime('00/%Y'),
                        'date_start': ds,
                        'date_stop': ds,
                        'special': True,
                        'fiscalyear_id': fy.id,
                    })
            while ds.strftime('%Y-%m-%d') < fy.date_stop:
                de = ds + relativedelta(months=interval, days=-1)

                if de.strftime('%Y-%m-%d') > fy.date_stop:
                    de = datetime.strptime(fy.date_stop, '%Y-%m-%d')

                period_obj.create(cr, uid, {
                    'name': ds.strftime('%m/%Y'),
                    'code': ds.strftime('%m/%Y'),
                    'date_start': ds.strftime('%Y-%m-%d'),
                    'date_stop': de.strftime('%Y-%m-%d'),
                    'fiscalyear_id': fy.id,
                })
                ds = ds + relativedelta(months=interval)
        return True
    
    def cancel_close_entry(self, cr, uid, ids, context=None):
        obj_acc_move = self.pool.get("account.move")
        obj_acc_journal_period = self.pool.get('account.journal.period')
        for year in self.browse(cr, uid, ids, context=context):
            if not year.close_entry_done:
                continue
            if year.state == 'done':
                raise osv.except_osv(_('Invalid Action!'), _('%s is closed, please re-open it first then can do the close entry cancel.')%(year.name,))
            #cancel and delete the close journal entry
            if year.close_move_id:
                if year.close_move_id.state == 'posted':
                    #open the last month first
                    context['force_open'] = True
                    self.pool.get('account.period').action_draft(cr, uid, [year.close_move_id.period_id.id], context=context)
                    obj_acc_move.button_cancel(cr, uid, [year.close_move_id.id],context=context)
                obj_acc_move.unlink(cr, uid, [year.close_move_id.id],context=context)                
            if year.close_journal_period_id:
                obj_acc_journal_period.unlink(cr, uid, [year.close_journal_period_id.id],context=context)            
            
        #clear the fields recording the closed entry
        self.write(cr, uid, ids, {'close_journal_period_id':None, 'close_move_id': None, 'close_entry_done':False})
                    
        return True
    
    def action_close(self, cr, uid, ids, context=None):
        acc_period_obj = self.pool.get('account.period')
        journal_obj = self.pool.get('account.journal')
        for year in self.browse(cr, uid, ids, context=context):
            if year.state == 'done':
                continue
            #only the year having closing entry generated can be close
            if not year.close_entry_done:
                raise osv.except_osv(_('Invalid Action!'), _('In order to close a year, you must first generate closing entry for this year %s')%(year.name,))
            
            #with opening periods of  this year, can not close year
            if acc_period_obj.search(cr, uid, [('fiscalyear_id', '=', year.id), ('state', '!=', 'done')], context=context):
                raise osv.except_osv(_('Invalid Action!'), _('In order to close a year, you must first close all periods of this year.'))
            
            #check the profit account balance, if there are balance of  this year, can not be close   
            domain = [('company_id', '=', year.company_id.id), ('year_close', '=', True), ('type', '=', 'situation')]
            journal_ids = journal_obj.search(cr, uid, domain, context=context)            
            if not journal_ids:
                raise osv.except_osv(_('Error!'), _('No available year close journal found, system need use it to get the profit account.'))
            journal = journal_obj.browse(cr, uid, journal_ids[0], context=context)
            #本年利润科目
            account_profit_year  = self.pool.get('account.account').browse(cr, uid, journal.default_debit_account_id.id, context={'fiscalyear': year.id})
            if account_profit_year.balance != 0.0:
                raise osv.except_osv(_('Invalid Action!'), _('The account of Profit of this year already have balance , this may be caused by new entries added or modification to the closing entry after the closing entry was generated.'))

            cr.execute('update account_fiscalyear set state=%s where id=%s', ('done', year.id))
        
        return True
        
    def action_draft(self, cr, uid, ids, context=None):
        open_ids = []
        for year in self.browse(cr, uid, ids, context=context):
            if year.state != 'done':
                continue
            period_obj = self.pool.get('account.period')
            #make sure there are no periods of next year are closed are generated closing entry
            domain = [('date_start', '>', year.date_stop), ('company_id','=',year.company_id.id), '|', ('close_entry_done', '=', True), ('state','=','done')]
            new_periods = period_obj.search(cr, uid, domain, context=context)
            if new_periods:
                raise osv.except_osv(_('Invalid Action!'), _('%s: there are periods closed or in closing of next year, please cancel them first.')%(year.name,))
                     
            open_ids.append(year.id)
            
        if open_ids:
            cr.execute('update account_fiscalyear set state=%s where id in %s', ('draft', tuple(open_ids),))
            
        return True            
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
