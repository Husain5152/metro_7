# -*- coding: utf-8 -*-
import time
from openerp import netsvc
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
from dateutil.relativedelta import relativedelta
import openerp.tools as tools
import openerp.addons.decimal_precision as dp
import xlwt
import tempfile

class pr_lines_export_wizard(osv.osv_memory):
    _name='pr.lines.export.wizard'
    _description = 'PR Lines Export Wizard'
    _columns = {
        'from_date': fields.datetime('From Date'),
        'to_date': fields.datetime('To Date'),
    }
    def do_export(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids, context=context)[0]
        if wizard:
            wheres = [('order_state','not in',['done','cancel'])]
            if wizard.from_date:
                wheres.append(('order_date_request','>=',wizard.from_date))
            if wizard.to_date:
                wheres.append(('order_date_request','<=',wizard.to_date))
            pr_line_obj = self.pool.get('pur.req.line')
            line_ids = pr_line_obj.search(cr, uid, wheres, order='req_id desc', context=context)
            workbook = xlwt.Workbook()
            row = 0
            sheet = workbook.add_sheet('PR Lines')
            sheet.write(row, 0, _('PR'))
            sheet.write(row, 1, _('ERP #'))
            sheet.write(row, 2, _('Product'))
            sheet.write(row, 3, _('Part type'))
            sheet.write(row, 4, _('Price'))
            sheet.write(row, 5, _('Stock qty'))
            sheet.write(row, 6, _('Qty available'))
            sheet.write(row, 7, _('MO'))
            sheet.write(row, 8, _('Unit'))
            sheet.write(row, 9, _('Drawing Order'))
            sheet.write(row, 10, _('Quantity'))
            sheet.write(row, 11, _('PO Generated'))
            sheet.write(row, 12, _('PO Quantity'))
            sheet.write(row, 13, _('Product UOM'))
            sheet.write(row, 14, _('Date Required'))
            sheet.write(row, 15, _('Unit IDs'))
            sheet.write(row, 16, _('Reason and Use'))
            sheet.write(row, 17, _('Requisition Ticket #'))
            sheet.write(row, 18, _('Warehouse'))
            sheet.write(row, 19, _('Requester'))
            sheet.write(row, 20, _('Requisition Date'))
            sheet.write(row, 21, _('Status'))
            for line in pr_line_obj.browse(cr, uid, line_ids, context=context):
                row += 1
                sheet.write(row, 0, line.req_id.name)
                sheet.write(row, 1, line.product_id.default_code)
                sheet.write(row, 2, line.product_id.name)
                sheet.write(row, 3, line.part_type)
                sheet.write(row, 4, line.price)
                sheet.write(row, 5, line.product_onhand_qty)
                sheet.write(row, 6, line.product_available_qty)

                sheet.write(row, 7, line.req_id.mo_id.name)
                sheet.write(row, 8, line.req_id.unit.name)
                sheet.write(row, 9, line.req_id.bigsubassembly_id.name)
                sheet.write(row, 10, line.product_qty)
                sheet.write(row, 11, line.generated_po)
                sheet.write(row, 12, line.po_info)

                sheet.write(row, 13, line.product_uom_id.name)
                sheet.write(row, 14, line.date_required)
                mfg_ids = ','.join([mfg_id.name for mfg_id in line.req_id.sale_product_ids])
                sheet.write(row, 15, mfg_ids)
                sheet.write(row, 16, line.req_reason)

                sheet.write(row, 17, line.req_ticket_no)
                sheet.write(row, 18, line.order_warehouse_id.name)
                sheet.write(row, 19, line.order_user_id.name)
                sheet.write(row, 20, line.order_date_request)
                sheet.write(row, 21, line.order_state)

            file_name = u'PR Lines-%s.xls'%datetime.datetime.utcnow()
            temp_xls_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xls')
            temp_xls_file_name = temp_xls_file.name
            temp_xls_file.close()
            workbook.save(temp_xls_file_name)

            return {
                'type': 'ir.actions.act_url',
                'url': '/web/export/drawing_order_print_pdf?file_name=%s&file_data=%s' % (
                    file_name, temp_xls_file_name),
                'target': 'self',
            }


        return {'type': 'ir.actions.act_window_close'}