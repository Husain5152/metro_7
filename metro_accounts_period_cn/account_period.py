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

class account_period(osv.osv):
    _inherit = "account.period"
    _columns = {
        #生成月度结账凭证的时候设置,相关凭证信息
        'close_journal_period_id':fields.many2one('account.journal.period','Close Journal Period', readonly=True),
        'close_move_id':fields.many2one('account.move','Close Account Entries', readonly=True),
        #结转凭证已生成标志, True则证明已经进行了生成月度结账凭证的操作, 但是如果损益类科目没有余额, 没必要生成转账凭证, 则close_journal_period_id/close_move_id没有数据
        'close_entry_done':fields.boolean('Close entry done', readonly=True),
    }
    def action_draft(self, cr, uid, ids, context=None):
        open_ids = []
        for period in self.browse(cr, uid, ids, context=context):
            if period.state != 'done':
                continue
            period_obj = self.pool.get('account.period')
            #要打开的月之后没有已经生成结转凭证或者关闭的期间: close_entry_done=False and state !='done'
            domain = [('date_start', '>', period.date_stop), ('special','!=',True),  ('company_id','=',period.company_id.id), '|', ('close_entry_done', '=', True), ('state','=','done')]
            new_periods = period_obj.search(cr, uid, domain, context=context)            
            if new_periods:
                raise osv.except_osv(_('Invalid Action!'), _('%s: there are periods closed or in closing after this period, please open them first.')%(period.name,))
            #区间所属年度不能关闭或者或者生成年结凭证, force_open is used for the cancel one year's closing entry
            if not context.get('force_open',False) and (period.fiscalyear_id.state == 'done' or period.fiscalyear_id.close_entry_done):
                raise osv.except_osv(_('Invalid Action!'), _('%s: the year of this period is closed or in closing, please re-open the year first.')%(period.name,))
                     
            open_ids.append(period.id)
            
        return super(account_period, self).action_draft(cr, uid, open_ids)
    
    def cancel_close_entry(self, cr, uid, ids, context=None):
        obj_acc_move = self.pool.get("account.move")
        obj_acc_journal_period = self.pool.get('account.journal.period')
        for period in self.browse(cr, uid, ids, context=context):
            if not period.close_entry_done:
                continue
            if period.state == 'done':
                raise osv.except_osv(_('Invalid Action!'), _('%s is closed, please re-open it first then can do the close entry cancel.')%(period.name,))
            #cancel and delete the close journal entry
            if period.close_move_id:
                if period.close_move_id.state == 'posted':
                    obj_acc_move.button_cancel(cr, uid, [period.close_move_id.id],context=context)
                obj_acc_move.unlink(cr, uid, [period.close_move_id.id],context=context)                
            if period.close_journal_period_id:
                obj_acc_journal_period.unlink(cr, uid, [period.close_journal_period_id.id],context=context)            
            
        #clear the fields recording the closed entry
        self.write(cr, uid, ids, {'close_journal_period_id':None, 'close_move_id': None, 'close_entry_done':False})
                    
        return True
            
account_period()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
