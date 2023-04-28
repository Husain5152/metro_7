# -*- encoding: utf-8 -*-
import time
from openerp.report import report_sxw
from openerp.osv import osv, fields
from openerp.osv import osv
from datetime import datetime
import openerp.tools as tools
from datetime import timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
PR_TYPE_DESC = {
    'mfg': 'MFG PR 生产部请购',
    'mfg_o': 'MFG-O PR 生产部请购',
    'normal': 'Warehouse PR 采购申请',
    'procurement': 'Procurement PR 自动申请',
    'canada': 'Canada PR 加拿大申请',
    'sourcing': 'Other PR 其他申请',
}

class print_pr_mfg(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(print_pr_mfg, self).__init__(cr, uid, name, context=context)
        type = context.get('type','all')
        pr_line_ids = context.get('pr_line_ids',[])
        self.show_price = context.get('show_price',True)
        self.context = context
        self.type = type
        self.pr_line_ids = pr_line_ids
        self.localcontext.update({
            'show_price': self.show_price,
            'type': self.type,
            'time': time,
            'get_mfg_parts': self._get_mfg_parts,
            'get_total_qty': self._get_total_qty,
            'date_time_hint': self._get_date_time_hint,
            'get_pr_type_desc': self._get_pr_type_desc,
        })

    def _get_pr_type_desc(self, pr_type):
        return PR_TYPE_DESC[pr_type]

    def _get_date_time_hint(self):
        pool_lang = self.pool.get('res.lang')
        lang = self.localcontext.get('lang', 'en_US') or 'en_US'
        lang_ids = pool_lang.search(self.cr, self.uid, [('code', '=', lang)])[0]
        lang_obj = pool_lang.browse(self.cr, self.uid, lang_ids)
        return lang_obj.date_format.replace('%m','MM').replace('%d','DD').replace('%Y','YYYY')

    def _get_mfg_parts(self, req, type='all'):
        result = []
        req_line_obj = self.pool.get('pur.req.line')
        if self.pr_line_ids:
            return req_line_obj.browse(self.cr, self.uid, self.pr_line_ids, context=self.context)
        elif type=='all':
            return req.line_ids
        elif type=='missing':
            for part in req.line_ids:
                if part.product_qty_remain > 0:
                    result.append(part)
        elif type == 'all_sort_by_supplier':
            line_ids = req_line_obj.search(self.cr, self.uid, [('req_id','=',req.id)], order="supplier_id asc")
            result = req_line_obj.browse(self.cr, self.uid, line_ids)
        elif type == 'all_sort_by_supplier_missing':
            line_ids = req_line_obj.search(self.cr, self.uid, [('req_id', '=', req.id)],
                                               order="supplier_id asc")
            for part in req_line_obj.browse(self.cr, self.uid, line_ids):
                if part.product_qty_remain > 0:
                    result.append(part)
        return result
    def _get_total_qty(self, req):
        result = 0
        pr_lines = self._get_mfg_parts(req, self.type)
        for line in pr_lines:
            result += line.product_qty
        return result

report_sxw.report_sxw('report.pr.mfg.part','pur.req','addons/metro_mrp_drawing/report/pr_mfg_part.rml',parser=print_pr_mfg, header='internal')
report_sxw.report_sxw('report.pr.mfg.form','pur.req','addons/metro_mrp_drawing/report/pr_mfg_form.rml',parser=print_pr_mfg, header='external')
