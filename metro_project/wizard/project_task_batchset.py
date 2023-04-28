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

from openerp.osv import osv,fields
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
        
class project_task_batchset(osv.osv_memory):
    _name = 'project.task.batchset'
    _description = 'Set task in batch'
    _columns = {
        'dept_id':fields.many2one('hr.department',string='Team',),
        'dept_mgr_id':fields.many2one('hr.employee',string='Team Leader'),
        'emp_ids': fields.many2many("hr.employee",string="Employees"),
    }
    
    def onchange_dept_id(self,cr,uid,ids,dept_id,context=None):
        resu = {}
        if dept_id:
            dept = self.pool.get('hr.department').read(cr, uid, dept_id, ['manager_id'],context=context)
            manager_id = dept['manager_id']
            emp_ids = self.pool.get('hr.employee').search(cr, uid, [('department_id','=',dept_id)],context=context)
            value={'dept_mgr_id':manager_id, 'emp_ids':emp_ids}
            resu['value'] = value
        return resu
        
    def set_data(self, cr, uid, ids, context=None):
        order = self.browse(cr, uid, ids[0], context=context)
        task_ids = context.get('active_ids')
        task_ids = self.pool.get('project.task').search(cr, uid, [('state', 'not in', ('done','cancelled')), ('id','in',task_ids)],context=context)
        if task_ids:
            #field names to read
            field_names = ['dept_id','dept_mgr_id','emp_ids']
            if field_names:
                data_write = {}
                data_write['dept_id'] = order.dept_id.id
                data_write['dept_mgr_id'] = order.dept_mgr_id.id
                emp_ids = [(6,False,[emp.id for emp in order.emp_ids])]
                data_write['emp_ids'] = emp_ids
            #write data
            self.pool.get('project.task').write(cr, uid, task_ids, data_write,context=context)
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
