# -*- coding: utf-8 -*-
import time
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST
import xlrd
import StringIO

class generate_pr_xls_wizard(osv.osv_memory):
    _name = 'generate.pr.xls.wizard'
    _inherit = 'generate.pr.wizard'
    _description = 'Generate PR From Xls Wizard'
    _columns = {
        'filename': fields.char('Filename',size=128),
        'bom_file': fields.binary('BOM File',required=True),
    }

    def do_generate(self, cr, uid, ids, context=None):
        drawing_order_obj = self.pool.get('drawing.order')
        product_obj = self.pool.get('product.product')
        generate_pr = self.browse(cr, uid, ids, context)[0]
        if generate_pr.bom_file:
            error_logs = drawing_order_obj.check_bom_file_content(cr, uid, order_name=False, bom_file_name=False,
                                                                  bom_content=generate_pr.bom_file, check_bom_file_name=False,
                                                                  check_item_no=False,
                                                                  check_erp_no_missing=False,
                                                                  check_erp_no_duplicate=False,
                                                                  check_total_qty=True,
                                                                  check_description_instead_of_part_name=True,
                                                                  use_row_instead_of_item_no_for_error=True
                                                                  )
            if len(error_logs) > 0:
                return self.pool.get('warning').info(cr, uid, title='Error', message="\n".join(error_logs))
            inputStr = StringIO.StringIO()
            inputStr.write(generate_pr.bom_file.decode('base64'))
            workbook = xlrd.open_workbook(file_contents=inputStr.getvalue())
            worksheet = workbook.sheet_by_index(0)
            row = 2
            sequence = 1
            pur_req_id = False

            while row < worksheet.nrows:
                bom_line = drawing_order_obj.read_bom_line(worksheet=worksheet, row=row)
                if bom_line['description'] and bom_line['bom_qty']:
                    bom_line.update({'quantity': int(bom_line['total_qty'])})
                    if bom_line['part_type'] not in ['ASM','CD']:
                        if bom_line['erp_no']:
                            product_ids = product_obj.search(cr, uid, [
                                ('default_code', '=', bom_line['erp_no'])
                            ])
                            if product_ids:
                                product_id = product_obj.browse(cr, uid, product_ids[0])
                                bom_line.update({'product_id': product_id,
                                                 })
                        if not pur_req_id:
                            pur_req_id = self._create_pr(cr, uid, {
                                'warehouse_id': generate_pr.warehouse_id.id,
                                'delivery_date': generate_pr.delivery_date,
                                'pr_type': 'mfg',
                            })
                        new_pr_line = self._create_pr_line(cr, uid, pur_req_id, bom_line, sequence, generate_pr.delivery_date, False)
                        if new_pr_line:
                            sequence += 1
                row += 1
        return True

generate_pr_xls_wizard()
