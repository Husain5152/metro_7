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
from openerp.report import report_sxw
from openerp.osv import osv

class project_task_print(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(project_task_print, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'get_priority':self.get_priority,
            'get_emp_names':self.get_emp_names,
            'get_mfg_ids':self.get_mfg_ids,
        })
    def get_priority(self,priority):
        return self._get_sellection_name('project.task','priority',priority)  
    def get_emp_names(self,emps):
        emp_names = [emp.name for emp in emps]
        return ', '.join(emp_names)  
    def get_mfg_ids(self,mfg_ids):
        mfg_ids_name = [mfg_id.name for mfg_id in mfg_ids]
        return ','.join(mfg_ids_name)                 
    #get the selection display value by the selection key(field_value)
    def _get_sellection_name(self,model_name,field_name,field_value):
        field_sel = self.pool.get(model_name)._columns[field_name].selection
        trans_src = field_value;
        for sel_item in field_sel:
            if(sel_item[0] == field_value):
                trans_src = sel_item[1]
                break
        trans_obj = self.pool.get('ir.translation')
        trans_name = model_name + ',' + field_name
        trans_result = trans_obj._get_source(self.cr, self.uid, trans_name, 'selection', self.localcontext.get('lang'), trans_src)
        return trans_result   
report_sxw.report_sxw('report.project.task.print','project.task','addons/metro_project/report/project_task_print.rml',parser=project_task_print, header='internal')
report_sxw.report_sxw('report.project.task.list','project.task','addons/metro_project/report/project_task_list.rml',parser=project_task_print, header='internal')
report_sxw.report_sxw('report.project.task.sheet','project.task','addons/metro_project/report/project_task_sheet.rml',parser=project_task_print, header='internal')
#tasks by group
report_sxw.report_sxw('report.task.group.by_assignee','task.group','addons/metro_project/report/task_group_by_assignee.rml',parser=project_task_print, header='internal')
report_sxw.report_sxw('report.task.group.by_employee','task.group','addons/metro_project/report/task_group_by_employee.rml',parser=project_task_print, header='internal')
report_sxw.report_sxw('report.task.group.by_team','task.group','addons/metro_project/report/task_group_by_team.rml',parser=project_task_print, header='internal')
#daily task
#report_sxw.report_sxw('report.task.daily.mfg','task.group','addons/metro_project/report/task_daily_mfg.rml',parser=project_task_print, header='internal')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

