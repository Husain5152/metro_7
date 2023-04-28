import time
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST
class print_pr_mfg_wizard(osv.osv_memory):
    _name = 'print.pr.mfg.wizard'
    _description = 'Print PR MFG Wizard'
    _columns = {
        'type': fields.selection([('all','Print All'),
                                  ('missing','Print Missing Parts'),
                                  ('all_sort_by_supplier','Print All Sorted By Supplier'),
                                  ('all_sort_by_supplier_missing', 'Print Missing Parts Sorted By Supplier')],string='Select Type Of Print', required=True),
    }
    _defaults = {
        'type': 'all',
    }
    def do_print(self, cr, uid, ids, context=None):
        print_pr_wizard = self.browse(cr, uid, ids, context)[0]
        pr_ids = context.get('pr_ids',False)
        if not pr_ids:
             return {'type': 'ir.actions.act_window_close'}
        datas = {
            'model': 'pur_req',
            'ids': pr_ids,
        }
        context.update({'type': print_pr_wizard.type})
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'pr.mfg.part',
            'datas': datas,
            'nodestroy': True,
            'context': context
        }
print_pr_mfg_wizard()
