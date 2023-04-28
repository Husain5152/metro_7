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
import xlrd
from xlutils.copy import copy
from xlutils.styles import Styles
from xlwt.Style import XFStyle

import os
import base64
import cStringIO
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP
from dateutil.relativedelta import relativedelta
from datetime import date, datetime
'''
Add the excel output feature
'''
class accounting_report(osv.osv_memory):
    _inherit = "accounting.report"
    
    def get_excel_lines(self, cr, uid, data):
        lines = {}
        ids2 = self.pool.get('account.financial.report')._get_children_by_order(cr, uid, [data['form']['account_report_id'][0]], context=data['form']['used_context'])
        for report in self.pool.get('account.financial.report').browse(cr, uid, ids2, context=data['form']['used_context']):
            balance =  report.balance * report.sign or 0.0
            lines[report.code] = {'balance':balance}            
            balance_cmp = 0.0
            if data['form']['enable_filter']:
                balance_cmp = self.pool.get('account.financial.report').browse(cr, uid, report.id, context=data['form']['comparison_context']).balance * report.sign or 0.0
                lines[report.code]['balance_cmp'] = balance_cmp
        return lines
    
    def check_report(self, cr, uid, ids, context=None):
        resu = super(accounting_report, self).check_report(cr, uid, ids, context=context)
        #clear the fiscal year parameter to make sure to query date by period only,  the reason see the account_move_line._query_get() method
        used_context = resu['datas']['form']['used_context']
        used_context['fiscalyear'] = False
        used_context['all_fiscalyear'] = True
        comparison_context = resu['datas']['form']['comparison_context']
        comparison_context['fiscalyear'] = False
        comparison_context['all_fiscalyear'] = True
        #set the flag for plcn report to ingore the journal items in the closed journals
        rpt_code = self.pool.get('account.financial.report').read(cr, uid, resu['datas']['form']['account_report_id'][0], ['code'], context=context)['code']
        if rpt_code == 'plcn':
            company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
            journal_ids = self.pool.get('account.journal').search(cr, uid, [('company_id','=',company_id),('period_close','=',False),('year_close','=',False)],context=context)
            used_context['journal_ids'] = journal_ids
            comparison_context['journal_ids'] = journal_ids
        
        return resu
    
    def check_report_excel(self, cr, uid, ids, context=None):
        data = self.check_report(cr, uid, ids, context)['datas']
        #get report meta data
        rpt_meta = self.pool.get('account.financial.report').browse(cr, uid, data['form']['account_report_id'][0], context=context)
        if not rpt_meta.excel_template_file \
            and not rpt_meta.default_excel_template_file \
            and not rpt_meta.default_excel_template_file_name:
            raise osv.except_osv(_('Error'), _('Please define the report''s excel template file name'))
        #get the report data
        excel_data = self.get_excel_lines(cr, uid, data)
        #output excel
        params = {'report_name': rpt_meta.name,
                        'report_title': rpt_meta.name,
                        'report_data': excel_data,
                        'tmpl_file_data': rpt_meta.excel_template_file or rpt_meta.default_excel_template_file,
                        'tmpl_file_name': rpt_meta.excel_template_file_name or rpt_meta.default_excel_template_file_name,
                        'dc_prefix': 'rpt:'}
        return self.down_report_excel(cr, uid, params, context=context)
    
    #output excel by data and template
    def down_report_excel(self, cr, uid, params , context=None):    
        report_name = params['report_name']
        report_title = params['report_title']
        #the data will update to excel: {'code':{'fieldname1':fieldvalue1,'fieldname2':fieldvalue2}}
        report_data = params['report_data']
        #template file dara or file name
        tmpl_file_data = params.get('tmpl_file_data',False)
        tmpl_file_name = params.get('tmpl_file_name',False)
        #dc_prefix: data cell prefix, data cell format: dc_prefix:fieldname@code
        dc_prefix = params['dc_prefix']
        
        #1.get excel template data
        if tmpl_file_data:
            tmpl_file_data = base64.decodestring(tmpl_file_data)
        elif tmpl_file_name:
            cur_path = os.path.split(os.path.realpath(__file__))[0]
            tmpl_file_path = os.path.join(cur_path,tmpl_file_name)
            tmpl_file_data = open(tmpl_file_path,'rb').read()
        if not tmpl_file_data:
            raise osv.except_osv(_('Error'), _('No file data found for down_report_excel()!'))
    
        #2.read template data, and write the data cell
        wb_rd = xlrd.open_workbook(file_contents = tmpl_file_data, formatting_info=True, on_demand=True)        
        sheet_rd = wb_rd.sheets()[0]
        #for write
        wb_wt = copy(wb_rd)
        sheet_wt = wb_wt.get_sheet(0)
        row_cnt = sheet_rd.nrows
        
        styles = Styles(wb_rd)
        #loop to check rows one by one
        lang = self.pool.get('res.users').browse(cr, uid, uid, context=context).lang
        lang_obj = self.pool.get('res.lang')
        lang_id = lang_obj.search(cr,uid,[('code','=',lang)])[0]
        
        for i in range(0,row_cnt):
            col_cnt = sheet_rd.row_len(i)
            for j in range(0,col_cnt):
                field_val = sheet_rd.cell(i,j).value
                #cell data format:  "rpt:balance@bscn_1_2"             
                if isinstance(field_val,type(u' ')) and field_val.startswith(dc_prefix) and field_val.find('@')>0:
                    #find the report code and field name
                    rpt_flag = field_val[field_val.index(dc_prefix)+len(dc_prefix):]
                    field_name, rpt_code = rpt_flag.split('@')
                    #write data to the writable sheet
                    rpt_fld_val = 0.0
                    if rpt_code and report_data.get(rpt_code,False):
                        rpt_fld_val = report_data[rpt_code].get(field_name,0.0)
#                    print sheet_rd.cell(i,j)
#                    print sheet_rd.cell(i,j).xf_index
#                    print styles[sheet_rd.cell(i,j)]
#                    print styles.cell_styles[sheet_rd.cell(i,j).xf_index]
                    style_wt = self.style_rd2wt(wb_rd,styles[sheet_rd.cell(i,j)].xf)
                    if rpt_fld_val != 0.0:
                        rpt_fld_val = lang_obj.format(cr, uid, [lang_id], '%.2f', rpt_fld_val, grouping=True, context=context)
                        sheet_wt.write(i, j, rpt_fld_val, style_wt)
                    else:
                        sheet_wt.write(i, j, '', style_wt)
        #output the file
        buf = cStringIO.StringIO()
        wb_wt.save(buf)
        filedata = base64.encodestring(buf.getvalue())
        buf.close()
        #goto file download page
        file_ext = tmpl_file_name.split('.')
        file_ext = file_ext[len(file_ext)-1]
        return self.pool.get('file.down').download_data(cr, uid, "%s.%s"%(report_title, file_ext), filedata, context)      

    def style_rd2wt(self,rdbook, rdxf):

            wtxf = XFStyle()
            #
            # number format
            #
            wtxf.num_format_str = rdbook.format_map[rdxf.format_key].format_str
            #
            # font
            #
            wtf = wtxf.font
            rdf = rdbook.font_list[rdxf.font_index]
            wtf.height = rdf.height
            wtf.italic = rdf.italic
            wtf.struck_out = rdf.struck_out
            wtf.outline = rdf.outline
            wtf.shadow = rdf.outline
            wtf.colour_index = rdf.colour_index
            wtf.bold = rdf.bold #### This attribute is redundant, should be driven by weight
            wtf._weight = rdf.weight #### Why "private"?
            wtf.escapement = rdf.escapement
            wtf.underline = rdf.underline_type #### 
            # wtf.???? = rdf.underline #### redundant attribute, set on the fly when writing
            wtf.family = rdf.family
            wtf.charset = rdf.character_set
            wtf.name = rdf.name
            # 
            # protection
            #
            wtp = wtxf.protection
            rdp = rdxf.protection
            wtp.cell_locked = rdp.cell_locked
            wtp.formula_hidden = rdp.formula_hidden
            #
            # border(s) (rename ????)
            #
            wtb = wtxf.borders
            rdb = rdxf.border
#            wtb.left   = rdb.left_line_style
#            wtb.right  = rdb.right_line_style
#            wtb.top    = rdb.top_line_style
#            wtb.bottom = rdb.bottom_line_style
            wtb.left   = 1
            wtb.right  = 1
            wtb.top    = 1
            wtb.bottom = 1 
            wtb.diag   = rdb.diag_line_style
            wtb.left_colour   = rdb.left_colour_index 
            wtb.right_colour  = rdb.right_colour_index 
            wtb.top_colour    = rdb.top_colour_index
            wtb.bottom_colour = rdb.bottom_colour_index 
            wtb.diag_colour   = rdb.diag_colour_index 
            wtb.need_diag1 = rdb.diag_down
            wtb.need_diag2 = rdb.diag_up
            #
            # background / pattern (rename???)
            #
            wtpat = wtxf.pattern
            rdbg = rdxf.background
            wtpat.pattern = rdbg.fill_pattern
            wtpat.pattern_fore_colour = rdbg.pattern_colour_index
            wtpat.pattern_back_colour = rdbg.background_colour_index
            #
            # alignment
            #
            wta = wtxf.alignment
            rda = rdxf.alignment
            wta.horz = rda.hor_align
            wta.vert = rda.vert_align
            wta.dire = rda.text_direction
            # wta.orie # orientation doesn't occur in BIFF8! Superceded by rotation ("rota").
            wta.rota = rda.rotation
            wta.wrap = rda.text_wrapped
            wta.shri = rda.shrink_to_fit
            wta.inde = rda.indent_level
            # wta.merg = ????
            #
            return wtxf
                
    def default_get(self, cr, uid, fields, context=None):
        res = super(accounting_report, self).default_get(cr, uid, fields, context=context)
        if 'period_to' in fields:
            period_to = self.pool.get('account.period').find(cr, uid, date.today(), context=context)[0]
            res['period_to'] = period_to
        #set the default report id
        if context.get('report_type_field',False):
            fld_name = context.get('report_type_field',False)
            company_obj = self.pool.get('res.company')
            company_id = company_obj._company_default_get(cr, uid, 'account.common.report',context=context)
            fld_info = company_obj.read(cr, uid, company_id, [fld_name])[fld_name]
            if fld_info:
                #if there are report type setting on company related field, then use it as default report
                res['account_report_id'] = fld_info[0]
            
        return res
            
    def create(self, cr, uid, vals, context=None):
        #set default report search parameter by context parameter and vals parameter
        if context.get('report_type_field',False):
            #get the report that run directly from company related field
            fld_name = context.get('report_type_field',False)
            company_obj = self.pool.get('res.company')
            company_id = company_obj._company_default_get(cr, uid, 'account.common.report',context=context)
            fld_info = company_obj.read(cr, uid, company_id, [fld_name])[fld_name]
            if fld_info:
                #if there are report type setting on company related field, then use it as default report
                vals['account_report_id'] = fld_info[0]
                #set the default values by report id
                if fld_name == 'report_bscn_id':
                    #++++++++Balance Sheet+++++++++
                    period_obj = self.pool.get('account.period')
                    #the first period as the period from
                    period_earliest_id = period_obj.search(cr, uid, [], limit=1, order='date_start', context=context)[0]
                    #find last year's last period as the comparing period to
                    this_year_start_day = period_obj.browse(cr,uid,vals['period_to'],context=context).fiscalyear_id.date_start
                    last_year_end_day = datetime.strptime(this_year_start_day, DEFAULT_SERVER_DATE_FORMAT)  - relativedelta(days=1)
                    period_to_cmp_id = period_obj.find(cr, uid, last_year_end_day, context=context)[0]
                    
                    vals.update({'filter':'filter_period',
                                     'period_from':period_earliest_id, # the earlist period
                                     'enable_filter':True, #Enable Comparison
                                     'label_filter':'Lasy Year', #Last year label for balance sheet
                                     'filter_cmp':'filter_period',
                                     'period_from_cmp':period_earliest_id, # the earlist period
                                     'period_to_cmp':period_to_cmp_id,
                                     'debit_credit':False, # no need to generate debit/credit data
                                     })
                    
                    #clear the fiscal year parameter to make sure to query date by period only,  the reason see the account_move_line._query_get() method
#                    if 'fiscalyear_id' in vals: vals.pop('fiscalyear_id')
#                    if 'fiscalyear_id_cmp' in vals: vals.pop('fiscalyear_id_cmp')
#                    vals.update({'fiscalyear_id':None,
#                                 'fiscalyear_id_cmp':None,
#                                 })
                    '''
                    *-from GUI, *#-from GUI and clear, #-set by code, //-leave it as original
                    *'chart_account_id': fields.many2one('account.account', 'Chart of Account', help='Select Charts of Accounts', required=True, domain = [('parent_id','=',False)]),
                    *'company_id': fields.related('chart_account_id', 'company_id', type='many2one', relation='res.company', string='Company', readonly=True),
                    *#'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal Year', help='Keep empty for all open fiscal year'),
                    #'filter': fields.selection([('filter_no', 'No Filters'), ('filter_date', 'Date'), ('filter_period', 'Periods')], "Filter by", required=True),
                    #'period_from': fields.many2one('account.period', 'Start Period'),
                    *'period_to': fields.many2one('account.period', 'End Period'),
                    //'journal_ids': fields.many2many('account.journal', string='Journals', required=True),
                    //'date_from': fields.date("Start Date"),
                    //'date_to': fields.date("End Date"),
                    *'target_move': fields.selection([('posted', 'All Posted Entries'),
                    
                    #'enable_filter': fields.boolean('Enable Comparison'),
                    #'account_report_id': fields.many2one('account.financial.report', 'Account Reports', required=True),
                    #'label_filter': fields.char('Column Label', size=32, help="This label will be displayed on report to show the balance computed for the given comparison filter."),
                    *#'fiscalyear_id_cmp': fields.many2one('account.fiscalyear', 'Fiscal Year', help='Keep empty for all open fiscal year'),
                    #'filter_cmp': fields.selection([('filter_no', 'No Filters'), ('filter_date', 'Date'), ('filter_period', 'Periods')], "Filter by", required=True),
                    #'period_from_cmp': fields.many2one('account.period', 'Start Period'),
                    #'period_to_cmp': fields.many2one('account.period', 'End Period'),
                    //'date_from_cmp': fields.date("Start Date"),
                    //'date_to_cmp': fields.date("End Date"),
                    #'debit_credit': fields.boolean('Display Debit/Credit Columns',
                    '''

                if fld_name == 'report_plcn_id':
                    #++++++++Balance Sheet+++++++++
                    period_obj = self.pool.get('account.period')
                    period_to = period_obj.read(cr, uid, vals['period_to'], ['fiscalyear_id'], context=context)
                    #the first period for the period to's year
                    period_year_start_id = period_obj.search(cr, uid, [('fiscalyear_id','=',period_to['fiscalyear_id'][0])], limit=1, order='date_start', context=context)[0]
                    
                    vals.update({'filter':'filter_period',
                                     'period_from':vals['period_to'], # for the profit loss report, only sum one period account
                                     'enable_filter':True, #Enable Comparison
                                     'label_filter':'This Year', #This year summary label for profit loss
                                     'filter_cmp':'filter_period',
                                     'period_from_cmp':period_year_start_id, # the earlist period
                                     'period_to_cmp':vals['period_to'],
                                     'debit_credit':False, # no need to generate debit/credit data
                                     })
                    
                    #clear the fiscal year parameter to make sure to query date by period only, the reason see the account_move_line._query_get() method
                    if 'fiscalyear_id' in vals: vals.pop('fiscalyear_id')
                    if 'fiscalyear_id_cmp' in vals: vals.pop('fiscalyear_id_cmp')
                    
        return super(accounting_report,self).create(cr, uid, vals, context)
      
accounting_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
