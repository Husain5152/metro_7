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
    'name': 'Metro MRP Drawing',
    'version': '1.0',
    'category': 'Metro',
    'description': """
        Metro MRP Drawing
        """,
    'author': 'Metro Tower Trucks',
    'website': 'http://www.metrotowtrucks.com',
    'depends': ["web", "web_kanban", "metro", "stock", "metro_project","metro_purchase","metro_hr","metro_mrp_id_stock","metro_product","metro_mrp","metro_stock"],
    'css' : [
        "static/src/css/mrp_drawing.css",
        "static/src/lib/defaultTheme.css",
    ],
    'qweb' : [
        'static/src/xml/web_kanban.xml',
        "static/src/xml/base.xml",
    ],
    'js' : [
        #"static/src/lib/jquery.floatThead.min.js",
        "static/src/js/mrp_drawing.js",
        "static/src/js/view_list.js",
        "static/src/js/kanban.js",
    ],        
    'data': [
             'res_company_view.xml',
             'project_data.xml',
             'project_ir_cron_data.xml',
             'task_report.xml',
             'pr_report.xml',
             'pur_req_email_template.xml',
             'purchase_email_template.xml',
             'wizard/pr_generate_po_wizard.xml',
             'wizard/task_print.xml',
             'wizard/generate_pr_wizard.xml',
             'wizard/update_do_bom.xml',
             'wizard/print_pr_wizard.xml',
             'wizard/generate_pr_xls_wizard.xml',
             'wizard/mo_select_do_wizard.xml',
             'wizard/pur_req_group.xml',
             'wizard/pr_send_email_wizard.xml',
             'wizard/po_send_email_wizard.xml',
             'wizard/task_deadline_wizard.xml',
             'wizard/move_po_line_wizard.xml',
             'wizard/set_pr_line_supplier_wizard.xml',
             'wizard/confirm_set_pr_line_supplier_wizard.xml',
             'wizard/link_po_to_pr_wizard.xml',
             'wizard/force_close_task_wizard.xml',
             'wizard/task_partial_transfer_wizard.xml',
             'wizard/fix_pdf_dxf_corrupt_wizard.xml',
             'wizard/reserved_list_wizard.xml',
             'wizard/shipping_list_wizard.xml',
             'wizard/pr_lines_generate_po_wizard.xml',
             'wizard/pr_lines_export_wizard.xml',
             'wizard/calculate_pr_available_qty_wizard.xml',
             'wizard/manually_done_pr_wizard.xml',
             'wizard/do_link_cnc_workorder_wizard.xml',
             'upload_multi_drawings_view.xml',
             'upload_multi_dxfs_view.xml',
             'drawing_order_view.xml',
             'project_task_report.xml',
             'warehouse_task_report.xml',
             'drawing_step_view.xml',
             'product_view.xml',
             'pur_req_view.xml',
             'pur_req_line_report_view.xml',
             'purchase_view.xml',
             'mrp_view.xml',
             'cnc_work_order_view.xml',
             'security/ir.model.access.csv',
             'pur_req_workflow.xml',
             ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
