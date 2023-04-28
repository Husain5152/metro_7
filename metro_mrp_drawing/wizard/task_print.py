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
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools

class task_print(osv.osv_memory):
    _inherit = "task.print"
    _columns = {
        'is_full_mode': fields.boolean('Is full mode report?'),
        'report_mode': fields.selection([
                                        #('legacy','Legacy Report'),
                                         ('brief','Task List 任务表'),
                                         ('full','Daily Report by Parts Done 每日零部件完成情况报表'),
                                         ('issue','List of Issued Drawings 发布图纸清单')],string='Report Mode')
    }
    _defaults = {
                 'is_full_mode': False,
                 'report_mode': 'full',
                 } 
    #TODO: Implement report name  
#     def get_report_name(self, cr, uid, id, rpt_name, context=None):
#         if rpt_name == 'report.task.group.by_team_full':
#             return "Tasks Done By Team Full"
#         elif rpt_name == 'report.task.group.by_assignee_full':
#             return "Tasks Done By Assignee Full"
#         elif rpt_name == 'report.task.group.by_employee_full':
#             return "Tasks Done By Employee Full"
#         elif rpt_name == 'report.task.group.by_team_brief':
#             return "Tasks Done By Team Brief"
#         elif rpt_name == 'report.task.group.by_assignee_brief':
#             return "Tasks Done By Assignee Brief"
#         elif rpt_name == 'report.task.group.by_employee_brief':
#             return "Tasks Done By Employee Brief"
#         elif rpt_name == 'report.task.group.by_team':
#             return "Tasks By Team"
#         elif rpt_name == 'report.task.group.by_assignee':
#             return "Tasks By Assignee"
#         elif rpt_name == 'report.task.group.by_employee':
#             return "Tasks Done Employee"
#         return None
    def do_print(self, cr, uid, ids, context=None):
        result = super(task_print,self).do_print(cr, uid, ids, context=context)
        data = self.browse(cr, uid, ids, context=context)[0]
        context = context and context or {}
        if context.get('warehouse_report',False):
            warehouse_report = context.get('warehouse_report')
            if warehouse_report == 'fulllist':
                result['report_name'] = result['report_name'] + '_warehouse_fulllist'
            elif warehouse_report == 'missing':
                result['report_name'] = result['report_name'] + '_warehouse_missing'
            else:
                result['report_name'] = result['report_name'] + '_warehouse_transfer'
        elif data.report_mode == 'brief':
            result['report_name'] = result['report_name'] + '_brief'
        elif data.report_mode == 'full':
            result['report_name'] = result['report_name'] + '_full'
        elif data.report_mode == 'issue':
            result['report_name'] = result['report_name'] + '_issue'
        return result        

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
