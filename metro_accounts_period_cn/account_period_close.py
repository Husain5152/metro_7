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

class account_period_close(osv.osv_memory):
    """
        close period
    """
    _inherit = "account.period.close"
    def data_save(self, cr, uid, ids, context=None):
        """
        This function close period
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: account period close’s ID or list of IDs
         """
        period_obj = self.pool.get('account.period')
        account_move_obj = self.pool.get('account.move')
        mode = 'done'
        data = self.browse(cr, uid, ids, context=context)[0]
        if data.sure:
            for period_id in context['active_ids']:
                period = period_obj.browse(cr, uid, period_id, context=context)
                if period.state == 'done':
                    continue                
                #only the period having closing entry generated can be close
                if not period.close_entry_done:
                    raise osv.except_osv(_('Invalid Action!'), _('In order to close a period, you must first generate closing entry for this period %s')%(period.name,))
                
                #the period with draft entry can not be close
                account_move_ids = account_move_obj.search(cr, uid, [('period_id', '=', period_id), ('state', '=', "draft")], context=context)
                if account_move_ids:
                    raise osv.except_osv(_('Invalid Action!'), _('In order to close a period, you must first post related journal entries.'))
                
                '''
                For the 'period_close_type'='period' or the last period of 'period_close_type'='year'
                check if there are new balance for the incoming/expense account again
                since if there are new moves added after the closing entry generated, or user modified the closing entry, this will make data be wrong
                if there is balance, then need user to generate closing entry again
                '''
                company = period.company_id
                last_year_period = False
                if company.period_close_type == 'year':        
                    #find the last period of this year
                    last_periods = period_obj.search(cr, uid, [('fiscalyear_id','=',period.fiscalyear_id.id)], order="date_stop desc", limit=1, context=context)
                    #if the current closing period is the last period then continue, otherwise return
                    last_year_period = last_periods and period.id == last_periods or False
                                                        
                if company.period_close_type == 'period' or last_year_period:
                    obj_acc_account = self.pool.get('account.account')
                    
                    #incoming accounts
                    account_type_ids = [account_type.id for account_type in company.income_account_types]
                    #expense accounts
                    account_type_ids += [account_type.id for account_type in company.expense_account_types]
                    account_ids = obj_acc_account.search(cr, uid, [('user_type', 'in', account_type_ids), ('type', '!=', 'view'), ('company_id', '=', company.id)], context=context)
                    balance_total = 0.0
                    for account in obj_acc_account.browse(cr, uid, account_ids, context={'periods': [period.id]}):
                        balance_total += account.balance
                    if balance_total != 0.0:
                        raise osv.except_osv(_('Invalid Action!'), _('New Incoming/Expense balance found, this may be caused by new entries added or modification to the closing entry after the closing entry was generated.'))    

                cr.execute('update account_journal_period set state=%s where period_id=%s', (mode, period.id))
                cr.execute('update account_period set state=%s where id=%s', (mode, period.id))

        return {'type': 'ir.actions.act_window_close'}

account_period_close()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
