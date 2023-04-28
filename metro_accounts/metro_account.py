# -*- coding: utf-8 -*-
import time
from openerp.report import report_sxw
from openerp.osv import fields, osv
    
class account_account(osv.osv):
    _inherit = "account.account"
    _columns={
        'name': fields.char('Name', size=256, required=True, select=True, translate=True),
        'bal_direct': fields.selection([
            ('d', 'Debit'),
            ('c', 'Credit'),
        ], 'Balance Direction',) 
    }
'''
Update SQL:
update account_account set bal_direct = 'd' where user_type in (select id from account_account_type where name in('Check','Asset','Bank','Cash','Receivable'))
update account_account set bal_direct = 'c' where user_type in (select id from account_account_type where name in('Equity','Liability','Payable','Tax'))
'''    
account_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: