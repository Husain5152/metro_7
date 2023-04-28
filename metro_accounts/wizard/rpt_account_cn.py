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
from lxml import etree

from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class rpt_account_cn(osv.osv_memory):
    _name = "rpt.account.cn"
    _inherit = "rpt.base"
    _description = "China Account Report"
            
    _columns = {
        #report data lines
        'rpt_lines': fields.one2many('rpt.account.cn.line', 'rpt_id', string='Report Line'),
#        'filter': fields.selection([('filter_date', 'Date'), ('filter_period', 'Periods')], "Filter by", required=True),
        'filter': fields.selection([('filter_period', 'Periods')], "Filter by", required=True),        
        'period_from': fields.many2one('account.period', 'Start Period'),
        'period_to': fields.many2one('account.period', 'End Period'),
        'date_from': fields.date("Start Date"),
        'date_to': fields.date("End Date"),
        'target_move': fields.selection([('posted', 'All Posted Entries'),
                                         ('draft', 'All Unposted Entries'),
                                         ('all', 'All Entries'),
                                        ], 'Target Moves', required=True),
        'account_ids': fields.many2many('account.account', string='Accounts', required=True),
        #report level       
        'level': fields.selection([('general', 'General'),('detail', 'Detail'),], "Report Level", required=True),     
        #Show counterpart account flag for detail report level   
        'show_counter': fields.boolean("Show counterpart", required=False),
        'no_zero_balance': fields.boolean("Hide data with zero balance", required=False, 
                                          help="Check this to hide: \n1.The periods without entries\n2.The accounts with zero initial balance and all periods have no entries"),
        }
    
    def _get_accounts_default(self, cr, uid, context=None):
        company_id = self.pool.get('res.users').browse(cr,uid,uid,context).company_id.id
        return self.pool.get('account.account').search(cr, uid ,[('company_id','=',company_id),'|',('type','=','liquidity'),('type','=','payable')])
        
    _defaults = {
        'name': 'Account Report',
        'type': 'account_cn',     
        'filter': 'filter_period',        
        'target_move': 'posted',
#        'account_ids': _get_accounts_default,
        'level': 'general',   
        'no_zero_balance':True
    }
    def default_get(self, cr, uid, fields_list, context=None):
        resu = super(rpt_account_cn,self).default_get(cr, uid, fields_list, context)
        company_id = self.pool.get('res.company')._company_default_get(cr, uid, 'account.rptcn', context=context)
        #handle the "default_account_type" and "default_account_user_type" parameter
        account_ids = []
        if context.get('default_account_type',False):
            account_types = context.get('default_account_type').split(',')
            account_ids_inc = self.pool.get('account.account').search(cr, uid, [('type','in',account_types),('type','!=','view'),('company_id','=',company_id)],context=context)
            if account_ids_inc:
                account_ids += account_ids_inc
        if context.get('default_account_user_type',False):
            account_types = context.get('default_account_user_type').split(',')
            account_ids_inc = self.pool.get('account.account').search(cr, uid, [('user_type.code','in',account_types),('type','!=','view'),('company_id','=',company_id)],context=context)
            if account_ids_inc:
                account_ids += account_ids_inc
        if account_ids:
            resu['account_ids'] = account_ids
        return resu
        
    def _check_periods(self, cr, uid, ids, context=None):
        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.period_from and (wiz.period_from.company_id.id != wiz.period_to.company_id.id or wiz.period_from.company_id.id != wiz.company_id.id) :
                return False
        return True

    _constraints = [
        (_check_periods, 'The chosen periods have to belong to the same company.', ['period_from','period_to']),
    ]

    def onchange_filter(self, cr, uid, ids, filter, company_id, context=None):
        res = {'value': {}}
        if filter == 'filter_no':
            res['value'] = {'period_from': False, 'period_to': False, 'date_from': False ,'date_to': False}
        if filter == 'filter_date':
            res['value'] = {'period_from': False, 'period_to': False, 'date_from': time.strftime('%Y-01-01'), 'date_to': time.strftime('%Y-%m-%d')}
        if filter == 'filter_period' and company_id:
            start_period = end_period = False
            cr.execute('''
                SELECT * FROM (SELECT p.id
                               FROM account_period p
                               WHERE p.company_id = %s
                               AND p.special = false
                               AND p.state = 'draft'
                               ORDER BY p.date_start ASC, p.special ASC
                               LIMIT 1) AS period_start
                UNION ALL
                SELECT * FROM (SELECT p.id
                               FROM account_period p
                               WHERE p.company_id = %s
                               AND p.date_start < NOW()
                               AND p.special = false
                               AND p.state = 'draft'
                               ORDER BY p.date_stop DESC
                               LIMIT 1) AS period_stop''', (company_id, company_id))
            periods =  [i[0] for i in cr.fetchall()]
            if periods and len(periods) > 1:
                start_period = periods[0]
                end_period = periods[1]
#            res['value'] = {'period_from': start_period, 'period_to': end_period, 'date_from': False, 'date_to': False}
            res['value'] = {'period_from': end_period, 'period_to': end_period, 'date_from': False, 'date_to': False}
        return res

    def _get_date_range(self, cr, uid, data, context=None):
        if data.filter == 'filter_date':
            return data.date_from, data.date_to
        elif data.filter == 'filter_period':
            if not data.period_from or not data.period_to:
                raise osv.except_osv(_('Error!'),_('Select a starting and an ending period.'))
            return data.period_from.date_start, data.period_to.date_stop
        
    def _get_account_balance(self, account, debit, credit):
        if debit == credit: bal_direct = 'balanced'
        if debit > credit: bal_direct = 'debit'
        if debit < credit: bal_direct = 'credit'
        balance = account.bal_direct == 'c' and (credit-debit) or (debit-credit) 
        return balance, bal_direct          
        
    def onchange_company_id(self, cr, uid, ids, company_id, current_account_ids, rpt_name, context):
        val = {}
        resu = {'value':val}
        if not company_id or not rpt_name:
            return resu
        account_ids = []
        #filter currenet account ids using company_id
        current_account_ids = current_account_ids and current_account_ids[0][2] or None        
        if current_account_ids:
            domain = [('id','in',current_account_ids),('company_id','=',company_id)]
            account_ids = self.pool.get('account.account').search(cr, uid, domain,context=context)       
        #refresh the accounting list
        account_user_types = None
        if rpt_name == 'actrpt_dtl_money':
            account_user_types = 'cash,bank'
        if rpt_name == 'actrpt_dtl_cash':
            account_user_types = 'cash'
        if rpt_name == 'actrpt_dtl_bank':
            account_user_types = 'bank'
        if account_user_types:
            account_user_types = account_user_types.split(',')                
            if not account_ids:
                account_ids = self.pool.get('account.account').search(cr, uid, [('user_type.code','in',account_user_types),('type','!=','view'),('company_id','=',company_id)],context=context)            
        val['account_ids'] = [[6, False, account_ids]]
        #refresh the periods
        period_resu = self.onchange_filter(cr, uid, ids, 'filter_period', company_id, context=context)
        val.update(period_resu['value'])
        return resu
        
    def run_account_cn(self, cr, uid, ids, context=None):
        if context is None: context = {}         
        rpt = self.browse(cr, uid, ids, context=context)[0]
        account_obj = self.pool.get('account.account')
        period_obj = self.pool.get('account.period') 
        
        labels = {'init_bal':_('Initial balance'),
                            'period_sum':_('Period total'),
                            'year_sum':_('Year total'),
                            'bal_direct_debit':_('Debit'),
                            'bal_direct_credit':_('Credit'),
                            'bal_direct_balanced':_('Balanced')}          
        company_id = rpt.company_id.id
        date_from,date_to = self._get_date_range(cr, uid, rpt, context)
        period_ids = period_obj.build_ctx_periods(cr, uid, rpt.period_from.id, rpt.period_to.id)
        move_state = ['draft','posted']
        if rpt.target_move == 'posted':
            move_state = ['posted']      
        if rpt.target_move == 'draft':
            move_state = ['draft']          
        #move line common query where
        aml_common_query = 'aml.company_id=%s'%(company_id,)
        seq = 1
        rpt_lns = []
        for account in rpt.account_ids:
            balance_sum = 0.0
            search_account_ids = tuple(account_obj._get_children_and_consol(cr, uid, [account.id], context=context))
            #1.the initial balance line
            cr.execute('SELECT COALESCE(SUM(aml.debit),0) as debit, COALESCE(SUM(aml.credit), 0) as credit \
                    FROM account_move_line aml \
                    JOIN account_move am ON (am.id = aml.move_id) \
                    WHERE (aml.account_id IN %s) \
                    AND (am.state IN %s) \
                    AND (am.date < %s) \
                    AND '+ aml_common_query +' '
                    ,(search_account_ids, tuple(move_state), date_from))
            row = cr.fetchone()
            debit = row[0]
            credit = row[1]            
            balance, direction = self._get_account_balance(account, debit, credit)
            rpt_ln = {'seq':seq,
                        'code':account.code, 
                        'name':account.name,
                        'period_id':rpt.period_from.id,
                        'notes':labels['init_bal'],
                        'debit':debit,
                        'credit':credit,
                        'bal_direct':labels['bal_direct_%s'%(direction,)],
                        'balance':balance,
                        'data_level':'init_bal'}
            seq += 1
            rpt_lns.append(rpt_ln)
            balance_sum += balance
            
            #2.loop by periods            
            year_sum = {}
            for period in period_obj.browse(cr, uid, period_ids,context=context):
                #the year sum data for credit/debit
                if not year_sum.get(period.fiscalyear_id.code,False):
                    if period.fiscalyear_id.date_start < date_from:
                        #Only when we start from the middle of a year, then need to sum year
                        cr.execute('SELECT COALESCE(SUM(aml.debit),0) as debit, COALESCE(SUM(aml.credit), 0) as credit \
                                FROM account_move_line aml \
                                JOIN account_move am ON (am.id = aml.move_id) \
                                WHERE (aml.account_id IN %s) \
                                AND (am.state IN %s) \
                                AND (am.date >= %s) \
                                AND (am.date < %s) \
                                AND '+ aml_common_query +' '
                                ,(search_account_ids, tuple(move_state), period.fiscalyear_id.date_start, date_from))
                        row = cr.fetchone()            
                        year_sum[period.fiscalyear_id.code] = {'debit':row[0],'credit':row[1]}   
                    else:
                        year_sum[period.fiscalyear_id.code] = {'debit':0.0,'credit':0.0}

                #detail lines
                if rpt.level == 'detail':
                    cr.execute('SELECT aml.debit, aml.credit,am.date as move_date, am.name as move_name, am.narration as move_notes, aml.name as move_line_name, \
                            aml.id,aml.move_id \
                            FROM account_move_line aml \
                            JOIN account_move am ON (am.id = aml.move_id) \
                            WHERE (aml.account_id IN %s) \
                            AND (am.state IN %s) \
                            AND (am.period_id = %s) \
                            AND '+ aml_common_query +' \
                            ORDER by aml.date, aml.move_id'
                            ,(search_account_ids, tuple(move_state), period.id))
                    rows = cr.dictfetchall()
                    balance_detail = balance_sum
                    for row in rows:
                        #move detail line
                        debit = row['debit']
                        credit = row['credit']            
                        balance, direction = self._get_account_balance(account, debit, credit)
                        balance_detail += balance
                        rpt_ln = {'seq':seq,
                                    'code':'', 
                                    'name':'',
                                    'period_id':period.id,
                                    'aml_id':row['id'], # for detail
                                    'date':row['move_date'], # for detail
                                    'am_name':row['move_name'], # for detail
                                    'notes':'%s,%s'%(row['move_line_name'], row['move_notes']),
                                    'debit':debit,
                                    'credit':credit,
                                    'bal_direct':labels['bal_direct_%s'%(direction,)],
                                    'balance':balance_detail,
                                    'data_level':'detail'}
                        if rpt.show_counter:
                            rpt_ln['counter_account'] = ''
                        rpt_lns.append(rpt_ln)    
                        seq += 1
                
                #the period credit/debit
                cr.execute('SELECT COALESCE(SUM(aml.debit),0) as debit, COALESCE(SUM(aml.credit), 0) as credit \
                        FROM account_move_line aml \
                        JOIN account_move am ON (am.id = aml.move_id) \
                        WHERE (aml.account_id IN %s) \
                        AND (am.state IN %s) \
                        AND (am.period_id = %s) \
                        AND '+ aml_common_query +' '
                        ,(search_account_ids, tuple(move_state), period.id))
                row = cr.fetchone()
                #period sum line
                debit = row[0]
                credit = row[1]            
                balance, direction = self._get_account_balance(account, debit, credit)                             
                #if "no zero balance period" is set, and no entries of this period, then do not show this period
                if rpt.no_zero_balance and debit == 0.0 and credit == 0:
                    continue                
                balance_sum += balance
                rpt_ln = {'seq':seq,
                            'code':'', 
                            'name':'',
                            'period_id':period.id,
                            'notes':labels['period_sum'],
                            'debit':debit,
                            'credit':credit,
                            'bal_direct':labels['bal_direct_%s'%(direction,)],
                            'balance':balance_sum,
                            'data_level':'period_sum'}
                rpt_lns.append(rpt_ln)    
                seq += 1  
                
                #year sum line  
                debit_year = debit + year_sum[period.fiscalyear_id.code]['debit']
                credit_year = credit + year_sum[period.fiscalyear_id.code]['credit']
                balance_year, direction_year = self._get_account_balance(account, debit_year, credit_year)
                balance_year = balance_sum
                rpt_ln = {'seq':seq,
                            'code':'', 
                            'name':'',
                            'period_id':period.id,
                            'notes':labels['year_sum'],
                            'debit':debit_year,
                            'credit':credit_year,
                            'bal_direct':labels['bal_direct_%s'%(direction_year,)],
                            'balance':balance_year,
                            'data_level':'year_sum'}
                #increase the year sum value
                year_sum[period.fiscalyear_id.code]['debit'] = debit_year
                year_sum[period.fiscalyear_id.code]['credit'] = credit_year
                
                rpt_lns.append(rpt_ln)     
                seq += 1
                
                    
            if rpt.no_zero_balance:
                #get the last report line of this account
                rpt_ln = rpt_lns.pop()
                #if only have the initial balance row, and the initial balance is zero then skip this account
                if not (rpt_ln['data_level'] == 'init_bal' and rpt_ln['balance'] == 0.0):
                    rpt_lns.append(rpt_ln)
                              
        return self.pool.get('rpt.account.cn.line'), rpt_lns    
#        upt_lines = [(0,0,rpt_ln) for rpt_ln in rpt_lns]
#        self.write(cr, uid, rpt.id, {'rpt_lines':upt_lines,'show_search':False},context=context)
        return True
    
#    def fields_view_get(self, cr, user, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
#        resu = super(rpt_account_cn, self).fields_view_get(cr, user, view_id, view_type, context, toolbar, submenu)
#        return resu
    
    def _pdf_data(self, cr, uid, ids, form_data, context=None):
        rpt_name = 'rpt.account.cn.gl'
        if form_data['level'] == 'detail':
            rpt_name = 'rpt.account.cn.detail'
            if form_data['name'] == 'actrpt_dtl_money':
                rpt_name = 'rpt.account.cn.detail.money'
        return {'xmlrpt_name': rpt_name}    
    
    
rpt_account_cn()

class rpt_account_cn_line(osv.osv_memory):
    _name = "rpt.account.cn.line"
    _inherit = "rpt.base.line"
    _description = "China Account Report Lines"
    _columns = {
        'rpt_id': fields.many2one('rpt.account.cn', 'Report'),
        #for GL
        'period_id': fields.many2one('account.period', 'Period',),
        
        #for detail
        'aml_id': fields.many2one('account.move.line', 'Move Line', ),
        'aml_account_id': fields.related('aml_id', 'account_id', string='Account',type='many2one',relation='account.account'),
        'aml_partner_id': fields.related('aml_id', 'partner_id', string='Partner',type='many2one',relation='res.partner'),
        'aml_source_id': fields.related('aml_id', 'source_id', string='Source',type='reference'),
        
        'date': fields.date('Move Date', ),
        'am_name': fields.char('Move Name', size=64, ),
        'counter_account': fields.char('Counter Account', size=64, ),
        
        #for both Gl and detail, move line name or static:期初,本期合计,本年合计
        'notes': fields.char('Notes', size=128, ),
        
        #for all
        'debit': fields.float('Debit', digits_compute=dp.get_precision('Account')),
        'credit': fields.float('Credit', digits_compute=dp.get_precision('Account')),
        #debit/credit direction:Debit(借)/Credit(贷)
        'bal_direct': fields.char('Balance Direction', size=16, ),
        'balance': fields.float('Balance', digits_compute=dp.get_precision('Account')),
        #report level       
        'level': fields.related('rpt_id','level',type='selection',selection=[('general', 'General'),('detail', 'Detail'),], string="Report Level"),     
        #Show counterpart account flag for detail report level   
        'show_counter': fields.related('rpt_id','show_counter',type='boolean', string="Show counterpart", required=False),
        }
    
    def open_move(self, cr, uid, ids, context=None):
        res_id = None
        if isinstance(ids, list):
            res_id = ids[0]
        else:
            res_id = ids
        aml_id = self.browse(cr, uid, res_id, context=context).aml_id
        if not aml_id:
            return False
        move_id = aml_id.move_id.id
        #got to accountve move form

        form_view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'view_move_form')
        form_view_id = form_view and form_view[1] or False
        return {
            'name': _('Account Move'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [form_view_id],
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'res_id': move_id,
        }
    
    def open_source(self, cr, uid, ids, context=None):
        res_id = None
        if isinstance(ids, list):
            res_id = ids[0]
        else:
            res_id = ids
        aml_id = self.browse(cr, uid, res_id, context=context).aml_id
        if not aml_id or not aml_id.source_id:
            return False
        res_model = aml_id.source_id._model._name
        res_id = aml_id.source_id.id
        #got to source model's form
        return {
            'name': _('Source Detail'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': res_model,
            'type': 'ir.actions.act_window',
            'res_id': res_id,
        }
                
rpt_account_cn_line()

from openerp.report import report_sxw
report_sxw.report_sxw('report.rpt.account.cn.gl', 'rpt.account.cn', 'addons/metro_accounts/report/rpt_account_cn_gl.rml', parser=report_sxw.rml_parse, header='internal landscape')
report_sxw.report_sxw('report.rpt.account.cn.detail', 'rpt.account.cn', 'addons/metro_accounts/report/rpt_account_cn_detail.rml', parser=report_sxw.rml_parse, header='internal landscape')
report_sxw.report_sxw('report.rpt.account.cn.detail.money', 'rpt.account.cn', 'addons/metro_accounts/report/rpt_account_cn_detail_money.rml', parser=report_sxw.rml_parse, header='internal landscape')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
