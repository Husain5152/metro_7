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

class rpt_account_partner(osv.osv_memory):
    _name = "rpt.account.partner"
    _inherit = "rpt.base"
    _description = "China Account Report"
    _columns = {
        #report data lines
        'rpt_lines': fields.one2many('rpt.account.partner.line', 'rpt_id', string='Report Line'),
        'period_from': fields.many2one('account.period', 'Start Period'),
        'period_to': fields.many2one('account.period', 'End Period'),
        'target_move': fields.selection([('posted', 'All Posted Entries'),
                                         ('draft', 'All Unposted Entries'),
                                         ('all', 'All Entries'),
                                        ], 'Target Moves', required=True),
        'reconcile': fields.selection([('all', 'All Entries'),
                                         ('full','Full Reconciled'),
                                         ('partial','Partial Reconciled'),
                                         ('no','UnReconciled'),
                                        ], 'Reconcile', required=True),
        'partner_ids': fields.many2many('res.partner', string='Partners', required=False),
        'account_ids': fields.many2many('account.account', string='Accounts', required=True),
        #report level       
        'level': fields.selection([('general', 'General'),('detail', 'Detail'),], "Report Level", required=True), 
        #report level       
        'partner_type': fields.selection([('customer', 'Customer'),('supplier', 'Supplier'),], "Partner Type", required=True),         
        #Show counterpart account flag for detail report level   
        'show_counter': fields.boolean("Show counterpart", required=False),   
        'no_zero_balance': fields.boolean("Hide data with zero balance", required=False, 
                                          help="Check this to hide: \n1.The period without entries\n2.The partner with zero initial balance and all periods have no entries"),
        }
        
    _defaults = {
        'type': 'account_partner',     
        'target_move': 'all',
        'level': 'general',   
        'partner_type': 'supplier',   
        'reconcile':'all',
        'no_zero_balance':True
    }
    def default_get(self, cr, uid, fields_list, context=None):
        resu = super(rpt_account_partner,self).default_get(cr, uid, fields_list, context)
        account_ids = []
        company_id = self.pool.get('res.company')._company_default_get(cr, uid, 'account.rptcn', context=context)
        #handle the "default_partner_type" parameter, set the default account_ids
        default_partner_type = context and context.get('default_partner_type', False) or False
        if default_partner_type:            
            account_types = []
            if default_partner_type == 'customer':
                account_types = ['receivable']
            if default_partner_type == 'supplier':
                account_types = ['payable']
            if account_types:
                account_ids_inc = self.pool.get('account.account').search(cr, uid, [('type','in',account_types),('company_id','=',company_id)],context=context)
                if account_ids_inc:
                    account_ids += account_ids_inc
        if account_ids:
            resu['account_ids'] = account_ids
        #set default periods
        period_from, period_ro = self.get_default_periods(cr, uid, self.pool.get('res.users').browse(cr,uid,uid,context=context).company_id.id,context)
        resu['period_from'] = period_from
        resu['period_to'] = period_ro
        return resu
    def fields_get(self, cr, uid, allfields=None, context=None, write_access=True):
        resu = super(rpt_account_partner,self).fields_get(cr, uid, allfields,context,write_access)
        #set  the 'account_id'/'partner_id' domain dynamically by the default_project_type
        default_partner_type = context and context.get('default_partner_type', False) or False
        if default_partner_type:            
            if default_partner_type == 'customer':
                resu['account_ids']['domain'] = [('type','=','receivable')]
                resu['partner_ids']['domain'] = [('customer','=',True)]
            if default_partner_type == 'supplier':
                resu['account_ids']['domain'] = [('type','=','payable')]
                resu['partner_ids']['domain'] = [('supplier','=',True)]
        return resu         
    def _check_periods(self, cr, uid, ids, context=None):
        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.period_from and wiz.period_to and wiz.period_from.company_id.id != wiz.period_to.company_id.id:
                return False
        return True

    _constraints = [
        (_check_periods, 'The chosen periods have to belong to the same company.', ['period_from','period_to']),
    ]

    def get_default_periods(self, cr, uid, company_id, context=None):
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
        return end_period, end_period
    
    def _get_date_range(self, cr, uid, data, context=None):
        if not data.period_from or not data.period_to:
            raise osv.except_osv(_('Error!'),_('Select a starting and an ending period.'))
        return data.period_from.date_start, data.period_to.date_stop
                
    def _get_account_balance(self, partner_type, debit, credit):
        if debit == credit: bal_direct = 'balanced'
        if debit > credit: bal_direct = 'debit'
        if debit < credit: bal_direct = 'credit'
        balance = partner_type == 'supplier' and (credit-debit) or (debit-credit) 
        return balance, bal_direct          
        
    def onchange_company_id(self, cr, uid, ids, company_id, current_account_ids, rpt_name, context):
        val = {}
        resu = {'value':val}
        if not company_id:
            return resu
        account_ids = []
        #filter currenet account ids using company_id
        current_account_ids = current_account_ids and current_account_ids[0][2] or None        
        if current_account_ids:
            domain = [('id','in',current_account_ids),('company_id','=',company_id)]
            account_ids = self.pool.get('account.account').search(cr, uid, domain,context=context)       
            
        #refresh the accounting list
        default_partner_type = context and context.get('default_partner_type', False) or False
        if not account_ids and default_partner_type:            
            account_types = []
            if default_partner_type == 'customer':
                account_types = ['receivable']
            if default_partner_type == 'supplier':
                account_types = ['payable']
            if account_types:
                account_ids = self.pool.get('account.account').search(cr, uid, [('type','in',account_types),('company_id','=',company_id)],context=context)    
        val['account_ids'] = [[6, False, account_ids]]
        #refresh the periods
        period_from, period_to = self.get_default_periods(cr, uid, company_id, context=context)
        val.update({'period_from':period_from, 'period_to':period_to})
        return resu
            
    def run_account_partner(self, cr, uid, ids, context=None):
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
        if rpt.reconcile == 'full':
            aml_common_query += '\n and aml.reconcile_id is not null '
        if rpt.reconcile == 'partial':
            aml_common_query += '\n and aml.reconcile_partial_id is not null '
        if rpt.reconcile == 'no':
            aml_common_query += '\n and (aml.reconcile_id is null and aml.reconcile_partial_id is null) '
                                    
        seq = 1
        rpt_lns = []        
        #the search account ids
        search_account_ids = []
        for act in rpt.account_ids:
            search_account_ids += account_obj._get_children_and_consol(cr, uid, [act.id], context=context)
        search_account_ids = tuple(search_account_ids)
        #get partner_ids
        partner_ids = rpt.partner_ids
        if not partner_ids:
            partner_domain = [('parent_id','=',False),('company_id','=',company_id)]
            if rpt.partner_type == 'supplier':
                partner_domain += [('supplier','=',True)]
            if rpt.partner_type == 'customer':
                partner_domain += [('customer','=',True)]
            partner_ids = self.pool.get('res.partner').search(cr, uid, partner_domain, context=context)
            partner_ids = self.pool.get('res.partner').browse(cr, uid, partner_ids, context=context)
        for partner in partner_ids:
            rpt_lns_row = []
            balance_sum = 0.0
            #1.the initial balance line
            cr.execute('SELECT COALESCE(SUM(aml.debit),0) as debit, COALESCE(SUM(aml.credit), 0) as credit \
                    FROM account_move_line aml \
                    JOIN account_move am ON (am.id = aml.move_id) \
                    WHERE (aml.account_id IN %s) \
                    AND (aml.partner_id = %s) \
                    AND (am.state IN %s) \
                    AND (am.date < %s) \
                    AND '+ aml_common_query +' '
                    ,(search_account_ids, partner.id, tuple(move_state), date_from))
            row = cr.fetchone()
            debit = row[0]
            credit = row[1]            
            balance, direction = self._get_account_balance(rpt.partner_type, debit, credit)
            rpt_ln = {'seq':seq,
#                        'code':account.code, 
                        'name':partner.name,
                        'period_id':rpt.period_from.id,
                        'notes':labels['init_bal'],
                        'debit':debit,
                        'credit':credit,
                        'bal_direct':labels['bal_direct_%s'%(direction,)],
                        'balance':balance,
                        'data_level':'init_bal'}
            seq += 1
            rpt_lns_row.append(rpt_ln)
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
                                AND (aml.partner_id = %s) \
                                AND (am.state IN %s) \
                                AND (am.date >= %s) \
                                AND (am.date < %s) \
                                AND '+ aml_common_query +' '
                                ,(search_account_ids, partner.id, tuple(move_state), period.fiscalyear_id.date_start, date_from))
                        row = cr.fetchone()            
                        year_sum[period.fiscalyear_id.code] = {'debit':row[0],'credit':row[1]}   
                    else:
                        year_sum[period.fiscalyear_id.code] = {'debit':0.0,'credit':0.0}

                #detail lines
                if rpt.level == 'detail':
                    cr.execute('SELECT aml.account_id,aml.debit, aml.credit,aml.date_biz as move_date, am.name as move_name, aml.name as move_line_name, \
                            aml.id,aml.move_id \
                            FROM account_move_line aml \
                            JOIN account_move am ON (am.id = aml.move_id) \
                            WHERE (aml.account_id IN %s) \
                            AND (aml.partner_id = %s) \
                            AND (am.state IN %s) \
                            AND (am.period_id = %s) \
                            AND '+ aml_common_query +' \
                            ORDER by aml.date, aml.move_id'
                            ,(search_account_ids, partner.id, tuple(move_state), period.id))
                    rows = cr.dictfetchall()
                    balance_detail = balance_sum
                    for row in rows:
                        #move detail line
                        debit = row['debit']
                        credit = row['credit']            
                        balance, direction = self._get_account_balance(rpt.partner_type, debit, credit)
                        balance_detail += balance
                        rpt_ln = {'seq':seq,
                                    'code':'', 
                                    'name':'',
                                    'period_id':period.id,
                                    'aml_id':row['id'], # for detail
                                    'account_id':row['account_id'], # for detail
                                    'date':row['move_date'], # for detail
                                    'am_name':row['move_name'], # for detail
                                    'notes':row['move_line_name'],
                                    'debit':debit,
                                    'credit':credit,
                                    'bal_direct':labels['bal_direct_%s'%(direction,)],
                                    'balance':balance_detail,
                                    'data_level':'detail'}
                        if rpt.show_counter:
                            rpt_ln['counter_account'] = ''
                        rpt_lns_row.append(rpt_ln)
                        seq += 1
                
                #the period credit/debit
                cr.execute('SELECT COALESCE(SUM(aml.debit),0) as debit, COALESCE(SUM(aml.credit), 0) as credit \
                        FROM account_move_line aml \
                        JOIN account_move am ON (am.id = aml.move_id) \
                        WHERE (aml.account_id IN %s) \
                        AND (aml.partner_id = %s) \
                        AND (am.state IN %s) \
                        AND (am.period_id = %s) \
                        AND '+ aml_common_query +' '
                        ,(search_account_ids, partner.id, tuple(move_state), period.id))
                row = cr.fetchone()
                #period sum line
                debit = row[0]
                credit = row[1]            
                balance, direction = self._get_account_balance(rpt.partner_type, debit, credit)                               
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
                rpt_lns_row.append(rpt_ln)    
                seq += 1                
                
                #year sum line  
                debit_year = debit + year_sum[period.fiscalyear_id.code]['debit']
                credit_year = credit + year_sum[period.fiscalyear_id.code]['credit']
                balance_year, direction_year = self._get_account_balance(rpt.partner_type, debit_year, credit_year)
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
                
                rpt_lns_row.append(rpt_ln)
                seq += 1
            
            #if only have the initial balance row, and the initial balance is zero then skip this partner        
            if rpt.no_zero_balance and len(rpt_lns_row) == 1 and rpt_lns_row[0]['balance'] == 0.0:                    
                    continue
            rpt_lns += rpt_lns_row
              
        #update the reconcile and residual data
        if rpt.level == 'detail':
            mvln_ids = [ln['aml_id'] for ln in rpt_lns if ln.get('aml_id',False)]
            mvln_data = self.pool.get('account.move.line').read(cr, uid, mvln_ids, ['reconcile','amount_residual'])
#            {'amount_residual': 0.0, 'id': 58854, 'reconcile': 'A1167'}
            mvlns = {}
            for mvln in mvln_data:
                mvlns[mvln['id']] = {'amount_residual':mvln['amount_residual'],'reconcile':mvln['reconcile']}
            for ln in rpt_lns:
                aml_id = ln.get('aml_id',False)
                if aml_id:
                    mvln = mvlns.get(aml_id,False)
                    if mvln:
                        ln.update(mvln)
        return self.pool.get('rpt.account.partner.line'), rpt_lns    
        return True
    
    def _pdf_data(self, cr, uid, ids, form_data, context=None):
        rpt_name = 'rpt.account.partner.gl'
        if form_data['level'] == 'detail':
            rpt_name = 'rpt.account.partner.detail'
        return {'xmlrpt_name': rpt_name}
    
rpt_account_partner()

class rpt_account_partner_line(osv.osv_memory):
    _name = "rpt.account.partner.line"
    _inherit = "rpt.base.line"
    _description = "China Account Report Lines"
    _columns = {
        'rpt_id': fields.many2one('rpt.account.partner', 'Report'),
        #for GL
        'period_id': fields.many2one('account.period', 'Period',),
        
        #for detail
        'aml_id': fields.many2one('account.move.line', 'Move Line', ),
        'aml_source_id': fields.related('aml_id', 'source_id', string='Source',type='reference'),
        
        'account_id': fields.many2one('account.account','Account'),
        'date': fields.date('Move Date', ),
        'am_name': fields.char('Move Name', size=64, ),
        'counter_account': fields.char('Counter Account', size=64, ),
        'reconcile': fields.char('Reconcile', size=64 ),
#        'reconcile_partial': fields.char('Partial Reconcile', size=64 ),
        'amount_residual': fields.float('Residual Amount', digits_compute=dp.get_precision('Account')),
        
        #for both Gl and detail, move line name or static:期初,本期合计,本年合计
        'notes': fields.char('Notes', size=64, ),
        
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
        
rpt_account_partner_line()

from openerp.report import report_sxw
report_sxw.report_sxw('report.rpt.account.partner.gl', 'rpt.account.partner', 'addons/metro_accounts/report/rpt_account_partner_gl.rml', parser=report_sxw.rml_parse, header='internal landscape')
report_sxw.report_sxw('report.rpt.account.partner.detail', 'rpt.account.partner', 'addons/metro_accounts/report/rpt_account_partner_detail.rml', parser=report_sxw.rml_parse, header='internal landscape')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
