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

class res_company(osv.osv):
    _inherit = "res.company"
    _columns = {
        #损益类科目结转方式:账结法/表结法, 默认为账结法
        'period_close_type': fields.selection([('period','Period'),('year','Year')],string='Accounting Transfer Method'),
        #收入类科目相关科目类型
        'income_account_types': fields.many2many('account.account.type', 'company_income_account_type_rel', 'company_id', 'account_type_id', 'Incoming Account Types'),            
        #成本费用类科目相关科目类型: res_company.expense_account_types
        'expense_account_types': fields.many2many('account.account.type', 'company_expense_account_type_rel', 'company_id', 'account_type_id', 'Expense Account Types')
        }
    
    def write(self, cr, uid, ids, vals, context=None):
        if vals.has_key('period_close_type'):
            #一旦有已经结账的期间(period.close_entry_done or state='done'),此标志不能修改
            period_ids = self.pool.get('account.period').search(cr, uid, ['|', ('close_entry_done', '=', True), ('state', '=', 'done')])
            if period_ids:
                raise osv.except_osv(_('Error!'), _("You cannot change the Accounting Transfer Method once there are closed or closing periods!"))
        return super(res_company,self).write(cr, uid, ids, vals, context=context)
res_company()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
