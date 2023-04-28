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
import openerp.addons.metro_mrp.work_order_cnc as cnc 

from datetime import datetime
from dateutil.relativedelta import relativedelta
from operator import itemgetter

from openerp import netsvc
from openerp import pooler
from openerp.osv import fields, osv
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from openerp.addons.metro import utils
import os
# ---------------------------------------------------------
# Account Financial Report
# ---------------------------------------------------------
'''
1.Add 'Complete Name', 'Code'
2.Add type 'account_item' and column 'account_item_ids'
3.Add class account_financial_report_item link to account_item_ids
4.Improve _get_balance for the 'account_item' type
5.Add excel template fields, and add the excel output feature
'''
class account_financial_report(osv.osv):
    _inherit = "account.financial.report"
    def name_get(self, cr, uid, ids, context=None):
        if isinstance(ids, (list, tuple)) and not len(ids):
            return []
        if isinstance(ids, (long, int)):
            ids = [ids]
        reads = self.read(cr, uid, ids, ['name','parent_id'], context=context)
        res = []
        for record in reads:
            name = record['name']
            if record['parent_id']:
                name = record['parent_id'][1]+' / '+name
            res.append((record['id'], name))
        return res

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)    

    def _get_balance(self, cr, uid, ids, field_names, args, context=None):
        '''returns a dictionary with key=the ID of a record and value=the balance amount 
           computed for this record. If the record is of type?:
               'accounts'?: it's the sum of the linked accounts
               'account_type'?: it's the sum of leaf accoutns with such an account_type
               'account_report'?: it's the amount of the related report
               'sum'?: it's the sum of the children of this record (aka a 'view' record)'''
        account_obj = self.pool.get('account.account')
        res = {}
        for report in self.browse(cr, uid, ids, context=context):
            if report.id in res:
                continue
            res[report.id] = dict((fn, 0.0) for fn in field_names)
            #add the operator, used in the 'sum' code segment, by johnw, 10/30/2014
            res[report.id]['operator'] = report.operator
            if report.type == 'accounts':
                # it's the sum of the linked accounts
                for a in report.account_ids:
                    for field in field_names:
                        res[report.id][field] += getattr(a, field)
            elif report.type == 'account_type':
                # it's the sum the leaf accounts with such an account type
                report_types = [x.id for x in report.account_type_ids]
                account_ids = account_obj.search(cr, uid, [('user_type','in', report_types), ('type','!=','view')], context=context)
                for a in account_obj.browse(cr, uid, account_ids, context=context):
                    for field in field_names:
                        res[report.id][field] += getattr(a, field)
            elif report.type == 'account_report' and report.account_report_id:
                # it's the amount of the linked report
                res2 = self._get_balance(cr, uid, [report.account_report_id.id], field_names, False, context=context)
                for key, value in res2.items():
                    for field in field_names:
                        res[report.id][field] += value[field]
            elif report.type == 'sum':
                # it's the sum of the children of this account.report
                res2 = self._get_balance(cr, uid, [rec.id for rec in report.children_ids], field_names, False, context=context)
#                for key, value in res2.items():
#                    for field in field_names:
#                        res[report.id][field] += value[field]
                for key, value in res2.items():
                    #refer the "add the operator, used in the 'sum' code segment" part
                    operator = '+'
                    if value.get('operator',False):
                        operator = value['operator']
                    for field in field_names:
                        if operator == '+':
                            res[report.id][field] += value[field]
                        elif operator == '-':
                            res[report.id][field] -= value[field]
                                                    
            elif report.type == 'account_item':
                # it's the sum the account items
                for item in report.account_item_ids:
                    if 'debit' in field_names:
                        res[report.id]['debit'] += item.account_id.debit
                    if 'credit' in field_names:
                        res[report.id]['credit'] += item.account_id.credit
                    if 'balance' in field_names:
                        #get the balance
                        balance = item.account_id.balance
                        #get the item amount value as the balance
                        if item.fetch_logic == 'db':
                            balance = item.account_id.balance
                        elif item.fetch_logic == 'cb':
                            balance = -item.account_id.balance
                        elif item.fetch_logic == 'dt':
                            balance = item.account_id.debit
                        elif item.fetch_logic == 'ct':
                            balance = item.account_id.credit
                        #add or subtract by the operator
                        if item.operator == '+':
                            res[report.id]['balance'] += balance
                        else:
                            res[report.id]['balance'] -= balance                        
        return res        

    def _get_default_excel_template(self, cr, uid, ids, field_names, args, context):
        cur_path = os.path.split(os.path.realpath(__file__))[0] + "/wizard"
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = None
            if not order.default_excel_template_file_name:
                continue
            path = os.path.join(cur_path,order.default_excel_template_file_name)
            data = open(path,'rb').read().encode('base64')
            res[order.id] = data
        return res
        
    _columns = {
        'code': fields.char('Code', size=32, required=True, select=True),
        'complete_name': fields.function(_name_get_fnc, type="char", string='Name'),
        'type': fields.selection([
            ('sum','View'),
            ('accounts','Accounts'),
            ('account_item','Account Items'),
            ('account_type','Account Type'),
            ('account_report','Report Value'),
            ],'Type'),
        'account_item_ids': fields.one2many('account.financial.report.account.item', 'report_id', string='Account Items'),
        'excel_template_file': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file,  type='binary',  string = 'User Excel Template', multi="_get_file"),
        'excel_template_file_name': fields.char('User Excel Template File Name'), 
        'default_excel_template_file': fields.function(_get_default_excel_template, type='binary', string = 'Default Excel Template'),
        'default_excel_template_file_name': fields.char('Default Excel Template File Name'),
        'operator': fields.selection([('+','Plus'),('-','Subtract'),('n','None')],'Operator', required=True),
        #redefine the 3 columns here, then the code will call the method _get_balance in this class, otherwise system will call parent class._get_balance first
        'balance': fields.function(_get_balance, 'Balance', multi='balance'),
        'debit': fields.function(_get_balance, 'Debit', multi='balance'),
        'credit': fields.function(_get_balance, 'Credit', multi="balance"),        
    }
    _defaults = {'operator':'+'}
    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'The code of the report must be unique !')
    ]
    
account_financial_report()

'''
The account items for a report
'''
class account_financial_report_account_item(osv.osv):
    _name = "account.financial.report.account.item"
    _description = "Account Report Account Item"
    _columns = {
        'report_id': fields.many2one('account.financial.report', 'Report', ondelete='cascade'),
        'name': fields.char('Account Item Name', size=128, required=True),
        'account_id':fields.many2one('account.account','Account', required=True, select=True),
        'operator': fields.selection([('+','Plus'),('-','Subtract')],'Operator', required=True),
        'fetch_logic': fields.selection([
            ('db', 'Debit Balance'),
            ('cb', 'Credit Balance'),
            ('dt', 'Debit Total'),
            ('ct', 'Credit Total'),
        ], 'Fetch Logic', required=True) 
    }
    _defaults={'operator':'+'}
    _sql_constraints = [
        ('item_account_uniq', 'unique(report_id,account_id)', 'Account must be unique per report!'),
    ]
    
    def create(self, cr, uid, vals, context=None):
        #set default name, this should be called by code, since the name is required on GUI
        if vals.get('account_id') and not vals.get('name'):
            name = self.pool.get('account.account').read(cr, uid, vals['account_id'],['name'],context=context)['name']
            vals['name'] = name        
        return super(account_financial_report_account_item,self).create(cr, uid, vals, context)
        
    def onchange_account_id(self,cr ,uid, ids, account_id, context=None):
        res = {}
        if not account_id:
            return res
        account_data = self.pool.get('account.account').read(cr, uid, account_id,['bal_direct','name'], context=context)
        bal_direct = account_data['bal_direct']
        if not bal_direct or  bal_direct == 'd':
            bal_direct = 'db'
        if bal_direct == 'c':
            bal_direct = 'db'
                
        res.update({'value':{'fetch_logic':bal_direct,'name':account_data['name']}})
        return res
'''
1.Add 'code' match exactly function for the name_search, 
this is for the account_financial_report_account_item importing using account code in csv
use 'code:1001' in csv to replace the account name column is OK
2.Add related finance report items
'''
class account_account(osv.osv):
    _inherit = "account.account"

    '''
    account.financial.report
    
            'type': fields.selection([
                ('sum','View'),
    'children_ids':  fields.one2many('account.financial.report', 'parent_id', 'Account Report'),
    
                ('accounts','Accounts'),
    'account_ids': fields.many2many('account.account', 'account_account_financial_report', 'report_line_id', 'account_id', 'Accounts'),
    
                ('account_item','Account Items'),
    'account_item_ids': fields.one2many('account.financial.report.account.item', 'report_id', string='Account Items'),
    
                ('account_type','Account Type'),
    'account_type_ids': fields.many2many('account.account.type', 'account_account_financial_report_type', 'report_id', 'account_type_id', 'Account Types'),
    
                ('account_report','Report Value'),
                ],'Type'),
    'account_report_id':  fields.many2one('account.financial.report', 'Report Value'),
    
    '''    
    def _parent_report_items(self, cr, uid, ids, field_names=None, arg=False, context=None):
        if context is None:
            context = {}
        res = {}
        for id in ids:
            res[id] = []
            
        for account in self.browse(cr, uid, ids, context=context):
            for item in account.report_item_ids:
                if item.report_id.code:
                    #only add the report with code
                    res[item.account_id.id].append( item.report_id.id)
                           
        return res
            
    _columns={        
              'report_item_ids':fields.one2many('account.financial.report.account.item','account_id', string='Report Items', readonly=True),
              'parent_report_item_ids':fields.function(_parent_report_items, string="Parent Report Items", type="many2many", relation="account.financial.report")
              }
    
    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        args = args[:]
        ids = []
        try:
            if name and str(name).startswith('partner:'):
                part_id = int(name.split(':')[1])
                part = self.pool.get('res.partner').browse(cr, user, part_id, context=context)
                args += [('id', 'in', (part.property_account_payable.id, part.property_account_receivable.id))]
                name = False
            if name and str(name).startswith('type:'):
                type = name.split(':')[1]
                args += [('type', '=', type)]
                name = False
            #add 'code:####' logic, by johnw, 10/29/2014
            #begin
            if name and str(name).startswith('code:'):
                code = name.split(':')[1]
                args += [('code', '=', code)]
                name = False
            #end
        except:
            pass
        if name:
            ids = self.search(cr, user, [('code', '=like', name+"%")]+args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, user, [('shortcut', '=', name)]+ args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, user, [('name', operator, name)]+ args, limit=limit, context=context)
            if not ids and len(name.split()) >= 2:
                #Separating code and name of account for searching
                operand1,operand2 = name.split(' ',1) #name can contain spaces e.g. OpenERP S.A.
                ids = self.search(cr, user, [('code', operator, operand1), ('name', operator, operand2)]+ args, limit=limit, context=context)
        else:
            ids = self.search(cr, user, args, context=context, limit=limit)
        return self.name_get(cr, user, ids, context=context)

account_account()    
    
from openerp.addons.account.report.account_financial_report import report_account_common
'''
Add the 'account_item' type data retrieving 
'''
def financial_report_sxw_get_lines(self, data):
    lines = []
    account_obj = self.pool.get('account.account')
    currency_obj = self.pool.get('res.currency')
    ids2 = self.pool.get('account.financial.report')._get_children_by_order(self.cr, self.uid, [data['form']['account_report_id'][0]], context=data['form']['used_context'])
    for report in self.pool.get('account.financial.report').browse(self.cr, self.uid, ids2, context=data['form']['used_context']):
        vals = {
            'name': report.name,
            'balance': report.balance * report.sign or 0.0,
            'type': 'report',
            'level': bool(report.style_overwrite) and report.style_overwrite or report.level,
            'account_type': report.type =='sum' and 'view' or False, #used to underline the financial report balances
        }
        if data['form']['debit_credit']:
            vals['debit'] = report.debit
            vals['credit'] = report.credit
        if data['form']['enable_filter']:
            vals['balance_cmp'] = self.pool.get('account.financial.report').browse(self.cr, self.uid, report.id, context=data['form']['comparison_context']).balance * report.sign or 0.0
        lines.append(vals)
        account_ids = []
        if report.display_detail == 'no_detail':
            #the rest of the loop is used to display the details of the financial report, so it's not needed here.
            continue
        #for the account_item report, get the account list of the all items, johnw, 10/27/2014
        #begin
        if report.type == 'account_item':
            account_ids = account_obj._get_children_and_consol(self.cr, self.uid, [x.account_id.id for x in report.account_item_ids])
        #end
        if report.type == 'accounts' and report.account_ids:
            account_ids = account_obj._get_children_and_consol(self.cr, self.uid, [x.id for x in report.account_ids])
        elif report.type == 'account_type' and report.account_type_ids:
            account_ids = account_obj.search(self.cr, self.uid, [('user_type','in', [x.id for x in report.account_type_ids])])
        if account_ids:
            for account in account_obj.browse(self.cr, self.uid, account_ids, context=data['form']['used_context']):
                #if there are accounts to display, we add them to the lines with a level equals to their level in
                #the COA + 1 (to avoid having them with a too low level that would conflicts with the level of data
                #financial reports for Assets, liabilities...)
                if report.display_detail == 'detail_flat' and account.type == 'view':
                    continue
                flag = False
                vals = {
                    'name': account.code + ' ' + account.name,
                    'balance':  account.balance != 0 and account.balance * report.sign or account.balance,
                    'type': 'account',
                    'level': report.display_detail == 'detail_with_hierarchy' and min(account.level + 1,6) or 6, #account.level + 1
                    'account_type': account.type,
                }

                if data['form']['debit_credit']:
                    vals['debit'] = account.debit
                    vals['credit'] = account.credit
                if not currency_obj.is_zero(self.cr, self.uid, account.company_id.currency_id, vals['balance']):
                    flag = True
                if data['form']['enable_filter']:
                    vals['balance_cmp'] = account_obj.browse(self.cr, self.uid, account.id, context=data['form']['comparison_context']).balance * report.sign or 0.0
                    if not currency_obj.is_zero(self.cr, self.uid, account.company_id.currency_id, vals['balance_cmp']):
                        flag = True
                if flag:
                    lines.append(vals)
    return lines    
report_account_common.get_lines = financial_report_sxw_get_lines
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
