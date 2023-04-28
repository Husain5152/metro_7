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
from datetime import timedelta
class task_group(osv.osv_memory):
    _name = "task.group"
    _columns = {
        'name': fields.char('Group', size=64, required=True),
        'team_leader': fields.char('Team Leader', size=64, required=False),
        'team_members': fields.char('Team Members', size=1024, required=False),
#        'group_task_ids': fields.one2many('task.group.tasks','group_id','Group Tasks')
        'task_ids': fields.many2many('project.task','task_group_tasks','group_id','task_id',string='Group Tasks'),
        'task_day': fields.date('Day', ),
        
    }
class task_print(osv.osv_memory):
    _name = "task.print"
    _columns = {
        'task_day': fields.date('Day', ),
        'print_type': fields.selection([('by_assignee','Task List By Assignee'),('by_employee','Task List By Employee'),('by_team','Task List By Team')],'Type', required=True, select=False),
        'task_type': fields.selection([('all','All'),('simple','Simple'),('software','Software'),('engineer','Engineering'),('gtd','GTD'),('mfg','Manufacture')],'Task Type', required=True, select=False),
    }
    _defaults = {'print_type':'by_assignee','task_type':'all'}
    
    def default_get(self, cr, uid, fields_list, context=None):
        values = super(task_print,self).default_get(cr, uid, fields_list, context)
        if context.get('mfg_daily'):
            today = datetime.datetime.utcnow().strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
            values.update({'print_type':'by_team','task_day':today,'task_type':'mfg'})
        return values
        
    def _get_assignee_name(self, cr, uid, task, context=None):
        resu = 'No Assignee'
        if task.user_id:
            resu = task.user_id.name
        return resu
    
    def _get_emps_name(self, cr, uid, task, context=None):
        resu = 'No Employee'
        if task.emp_ids:
            resu = ''
            for emp in task.emp_ids:
                resu += (resu != '' and ',' or '') + emp.name
        return resu
    
    def _get_team_name(self, cr, uid, task, context=None):
        dept_name = 'No Team'
        if task.dept_id:
            dept_name = task.dept_id.name    
        return dept_name
    
    def do_print(self, cr, uid, ids, context=None):
        if context is None:
            context = {}    
        active_ids = context and context.get('active_ids', [])
        data = self.browse(cr, uid, ids, context=context)[0]
        #set the group field name and function to get related name
        group_name_func = None
        if data.print_type == 'by_assignee':
            group_name_func = self._get_assignee_name
        elif data.print_type == 'by_employee':
            group_name_func = self._get_emps_name
        elif data.print_type == 'by_team':
            group_name_func = self._get_team_name
        #get the tasks by day
        task_day = ''
        task_domain = []  
        if data.task_type != 'all':
            project_ids = self.pool.get('project.project').search(cr, uid, [('project_type','=',data.task_type)],order='priority asc, sequence asc, production_id desc',context=context)
            task_domain += [('project_id','in',project_ids)]
        if data.task_day:
            #task_domain += ['|',('date_start','=',False),('date_start','<=', data.task_day + ' 23:59:59'),'|',('date_end','=',False),('date_end','>=', data.task_day + ' 00:00:00')]
            #task_domain += [('state','!=','cancelled')]
            task_day = data.task_day
        if task_domain:
            active_ids = self.pool.get('project.task').search(cr, uid, task_domain, context=context)
            
        #get the group data
        groups = {}
        for task in self.pool.get('project.task').browse(cr, uid, active_ids, context=context):
            group_name = group_name_func(cr, uid, task, context)
            if not groups.get(group_name):                
                group_vals = {'task_ids':[]}
                #Add the team fields for the by_team report
                if data.print_type == 'by_team' and task.dept_id:
                    team_leader = task.dept_mgr_id and task.dept_mgr_id.name
                    team_leader_id = task.dept_mgr_id and task.dept_mgr_id.id or 0
                    team_members = ''
                    if task.emp_ids:
                        team_members = [emp.name for emp in task.emp_ids if emp.id != team_leader_id]
                        team_members = ', '.join(team_members)
                    group_vals.update({'team_leader':team_leader,'team_members':team_members})
                groups.update({group_name:group_vals})
            #append the tasks
            groups.get(group_name)['task_ids'].append((4,task.id))
        #create group data
        task_group_obj = self.pool.get('task.group')
        group_ids = []
        for group_name,group_data in groups.items():
            vals = {'name':group_name}
            vals.update(group_data)
            if task_day:
                vals.update({'task_day':task_day})
            group_ids.append(task_group_obj.create(cr, uid, vals, context=context))
        #print tasks by group
        if not group_ids:
            return {'type': 'ir.actions.act_window_close'}     
        datas = {
                 'model': 'task.group',
                 'ids': group_ids,
        }
        context.update({'group_ids': group_ids})
        return {'type': 'ir.actions.report.xml', 'report_name': 'task.group.%s'%(data.print_type,), 'datas': datas, 'nodestroy': True,'context': context}        

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
