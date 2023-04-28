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

import time

from openerp.report import report_sxw
from openerp.addons.metro.rml import rml_parser_ext  
from metro.utils import cnumber

class account_move_print(rml_parser_ext):
    def __init__(self, cr, uid, name, context=None):
        super(account_move_print, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time, 
            'to_cn': self.to_cn, 
            
        })
        
    def to_cn(self, amount):
        pt = cnumber()
        if not isinstance(amount, str):
            str_amount = str(amount).replace(',', '') #delete the ','
            cn_amt = pt.cwchange(str_amount)
        else:
            cn_amt = pt.cwchange(amount)
        return cn_amt
            
report_sxw.report_sxw('report.account.move.print', 'account.move', 'addons/metro_accounts/account_move.rml', parser=account_move_print, header=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

