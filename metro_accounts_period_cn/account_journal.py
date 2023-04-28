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

class account_journal(osv.osv):
    _inherit = "account.journal"
    _columns = {
        #期间结转凭证使用的journal, 每个company只能有一个journal设置此标志
        'period_close': fields.boolean('For Period Closing'),
        #年度结转凭证使用的journal, 每个company只能有一个journal设置此标志
        'year_close': fields.boolean('For Year Closing'),
        }
    
    def _check_period_close(self, cr, uid, ids, context=None):
        for journal in self.browse(cr, uid, ids, context=context):
            if journal.period_close:
                #check if there are other journal is checked in same company
                exist_journal_ids = self.search(cr, uid, [('period_close','=',True), ('id', '!=', journal.id), ('company_id', '=', journal.company_id.id)], context=context)
                if exist_journal_ids:
                    return False
        return True
    
    def _check_year_close(self, cr, uid, ids, context=None):
        for journal in self.browse(cr, uid, ids, context=context):
            if journal.year_close:
                #check if there are other journal is checked in same company
                exist_journal_ids = self.search(cr, uid, [('year_close','=',True), ('id', '!=', journal.id), ('company_id', '=', journal.company_id.id)], context=context)
                if exist_journal_ids:
                    return False
        return True
    
    def _check_year_month_close(self, cr, uid, ids, context=None):
        for journal in self.browse(cr, uid, ids, context=context):
            '''
            Journal can not be year and period close at the same time, 
            since only one entry can be created for the period/year close journal, 
            so if period and year create the closing entry to same journal/period, then error will be occured
            '''
            if journal.period_close and journal.year_close:
                return False
        return True

    _constraints = [
        (_check_period_close, 'Error!\nOnly one journal is allowed for Period Closing for one company.', ['period_close']),
        (_check_year_close, 'Error!\nOnly one journal is allowed for Year Closing for one company.', ['year_close']),
        (_check_year_month_close, 'Error!\nYear and Period Closing flag can not be applied to same journal.', ['period_close', 'year_close']),
    ]
        
account_journal()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
