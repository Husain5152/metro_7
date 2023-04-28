# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2010 OpenERP s.a. (<http://openerp.com>).
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
{
    'name': 'Metro Accounting Period Processing CN',
    'version': '1.0',
    'category': 'Metro',
    'description' : """    
Metro Accounting Period Processing CN.
====================================

Accounting Period Processing for China that covers:
--------------------------------------------
    * Period closing entry generation and closing
    * Year closing entry generation and closing
    * Not allow to cancel account entries for the closed period
    * Only can select opening period on Accouting Entry
    
Depends:
--------------------------------------------
    * metro_accounts for the account_move_line.date_biz
        
    """,
    'author': 'Metro Tower Trucks',
    'website': 'http://www.metrotowtrucks.com',
    'depends': ["account","metro_accounts"],
    'data': ['menu.xml',
             'res_company_view.xml',
             'account_journal_view.xml',
             'account_period_view.xml',
             'account_period_close_entry_view.xml',
#             'account_period_close_view.xml',
             'account_fiscalyear_close_entry_view.xml',
             'account_fiscalyear_view.xml',
             'account_move_view.xml'
             ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
