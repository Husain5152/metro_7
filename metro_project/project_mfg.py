# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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
from openerp.osv import fields,osv
from openerp.addons.base_status.base_stage import base_stage
from openerp.tools.translate import _
from lxml import etree
from openerp import netsvc
from openerp import tools

class project_task(base_stage, osv.osv):
    _inherit = "project.task"
    _columns = {
        'workorder_id': fields.many2one('mrp.production.workcenter.line', string='Work Order', ondelete='cascade'),
        'workcenter_id': fields.related('workorder_id','workcenter_id', type='many2one', relation="mrp.workcenter", string='Work Center', readonly=True),
        'production_id': fields.related('workorder_id','production_id', type='many2one', relation="mrp.production", string='Manufacture Order', readonly=True, store=True),
#        'mfg_ids': fields.related('production_id','mfg_ids', type='many2many', relation='sale.product',rel='mrp_task_id_rel',id1='task_id',id2='mfg_id',string='MFG IDs', readonly=False,store=True),
        #+++ HoangTK - 11/23/2015: Change mfg_ids to related, add drawing order
        #+++ HoangTK - 01/07/2018: Change back due to need to separate id for warsehouse task
        'mfg_ids': fields.many2many(obj='sale.product',rel='mrp_task_id_rel',id1='task_id',id2='mfg_id',string='MFG IDs', states={'draft':[('readonly',False)]}),
        #'mfg_ids': fields.related('production_id','mfg_ids',type="many2many",  relation="sale.product", string="MFG IDs",readonly=True),
        #--- HoangTK - 11/23/2015
        'product':fields.related('production_id','product_id',type='many2one',relation='product.product',string='Product', readonly=True),
        'dept_id':fields.many2one('hr.department',string='Team',readonly=True),
        'dept_mgr_id':fields.many2one('hr.employee',string='Team Leader'),
        'multi_mfg_ids_search':fields.function(lambda *a,**k:{}, type='char',string="Multi MFG IDs",),
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
    def default_get(self, cr, uid, fields_list, context=None):
        resu = super(project_task,self).default_get(cr, uid, fields_list, context=context)
        if context.get('force_workorder'):
            wo_id = context.get('force_workorder')
            priority = self.pool.get('mrp.production.workcenter.line').read(cr, uid, wo_id, ['priority'],context=context)['priority']
            resu.update({'workorder_id': wo_id, 'priority':priority})
        return resu
    def on_change_wo(self,cr,uid,ids,wo_id,context=None):
        resu = {}
        if wo_id:
            wo = self.pool.get('mrp.production.workcenter.line').read(cr, uid, wo_id, ['priority','mfg_ids'],context=context)
            value={'priority':wo['priority'],'mfg_ids':wo['mfg_ids']}
            resu['value'] = value
#            resu['domain'] = {'mfg_ids': [('id','in',wo['mfg_ids'])]}
        return resu
    
    def _check_before_save(self, cr, uid, ids, vals, context=None):
        assert ids == None or len(ids) == 1, 'This option should only be used for a single task update at a time'
        '''
        from GUI: [[6, False, [418, 416]]]
        from code to create: [4, [418, 416]]
        Only check from GUI
        ''' 
        project_type = ''
        if ids == None:
            if vals.get('project_type',False):
                project_type = vals['project_type']
            else:            
                project_type = self.pool.get('project.project').read(cr, uid, vals['project_id'], ['project_type'], context=context)['project_type']
        else:
            project_type = self.read(cr, uid, ids[0], ['project_type'],context=context)['project_type']
        if project_type == 'mfg' and 'mfg_ids' in vals and len(vals['mfg_ids']) == 1 and len(vals['mfg_ids'][0]) == 3:    
            wo = None
            #get the workorder data
            if not 'workorder_id' in vals:
                task = self.browse(cr, uid, ids[0], context=context)
                wo = task.workorder_id
            else:
                wo = self.pool.get('mrp.production.workcenter.line').browse(cr,uid,vals['workorder_id'],context=context)
            #get the workorder's MFG ID's ID&Name list
            wo_mfg_ids = []
            wo_mfg_names = []
            for mfg_id in wo.mfg_ids:
                wo_mfg_ids.append(mfg_id.id)
                wo_mfg_names.append(mfg_id.name)
            #loop to check make sure the MFG IDs of task belongs to work order's MFG IDs
            for task_mfg_id in vals['mfg_ids'][0][2]:
                if not task_mfg_id in wo_mfg_ids:
                    task_mfg_name = self.pool.get('sale.product').read(cr, uid, task_mfg_id, ['name'], context=context)['name']
                    raise osv.except_osv(_('Invalid Action!'), _('The task MFG IDs:%s must match the work order''s MFG IDs:%s')%(task_mfg_name,','.join(wo_mfg_names)))
        return True
    
    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for task_id in ids:
            self._check_before_save(cr, uid, [task_id], vals, context=context)
        return super(project_task,self).write(cr, uid, ids, vals, context=context)
        
    def create(self, cr, uid, vals, context=None):
        self._check_before_save(cr, uid, None, vals, context=context)
        return super(project_task,self).create(cr, uid, vals, context=context)
        
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        for arg in args:
            #add the multi part# query
            if arg[0] == 'multi_mfg_ids_search':
                mfg_ids = []
                for mfg_id in arg[2].split(','):
                    mfg_ids.append(mfg_id.strip())
                if mfg_ids:
                    ids = self.pool.get('sale.product').search(cr, user, [('name','in',mfg_ids)],context=context)
                    if ids:
                        idx = args.index(arg)
                        args.remove(arg)
                        args.insert(idx, ['mfg_ids','in',ids])
                break
                            
        #get the search result        
        ids = super(project_task,self).search(cr, user, args, offset, limit, order, context, count)

        return ids    

#class sale_product(osv.osv):
#    _inherit = 'sale.product'
#    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
#        if operator == 'in' and isinstance(name, type(u'aaa')):
#                mfg_ids = []
#                for mfg_id in name.split(','):
#                    mfg_ids.append(mfg_id.strip())
#                name = mfg_ids
#        return super(sale_product,self).name_search( cr, user, name, args, operator, context, limit)
            
class mrp_production_workcenter_line(osv.osv):
    _inherit = 'mrp.production.workcenter.line'

    _columns = {
        'task_ids': fields.one2many('project.task', 'workorder_id',string='Working Tasks'),
    }
    #add the 'update=True, mini=True' inhreited from mrp_operations.mrp_production_workcenter_line
    def write(self, cr, uid, ids, vals, context=None, update=True):
        resu = super(mrp_production_workcenter_line, self).write(cr, uid, ids, vals, context=context,update=update)        
        if 'priority' in vals.keys():
            self.set_priority(cr,uid,ids,vals['priority'],context)
        return resu
    
    def set_priority(self,cr,uid,ids,priority,context=None):
        if context is None:
            context = {}
        #set all of the sub manufacture orders, work orders, MFG tasks priority
        set_ids = []
        task_ids = []
        for wo in self.browse(cr,uid,ids,context=context):
            if wo.state in ('cancel','done'):
                continue
            set_ids.append(wo.id)
            task_ids += [task.id for task in wo.task_ids if task.state not in ('cancelled','done')]
        if set_ids:
            #update work order
            cr.execute("update mrp_production_workcenter_line set priority=%s where id  = ANY(%s)", (priority, (set_ids,)))
            #update manufacture order
            self.pool.get('project.task').write(cr, uid, task_ids, {'priority':priority}, context=context)

    def action_close(self, cr, uid, ids, context=None):
        #TODO generate the working hours time sheet 
        return super(mrp_production_workcenter_line,self).action_close(cr, uid, ids, context)
    
class project_task_work(osv.osv):
    _inherit = "project.task.work"
    _columns = {
        'emp_ids': fields.many2many("hr.employee","task_work_emp","work_id","emp_id",string="Employees"),
        'mfg_ids': fields.many2many('sale.product', 'task_id_rel','task_id','mfg_id',string='MFG IDs',),
    }    

    def default_get(self, cr, uid, fields_list, context=None):
        res = super(project_task_work,self).default_get(cr, uid, fields_list, context=context)
        if not res:
            res = {}
        if context.get('workorder_id',False):
            wo_data = self.pool.get('mrp.production.workcenter.line').browse(cr, uid, context['workorder_id'], context=context)
            mfg_ids = [mfg_id.id for mfg_id in wo_data.production_id.mfg_ids]
            res.update({'mfg_ids':mfg_ids})
        if context.get('task_employee_ids',False):
            #task_employee_ids structure is like: 'task_employee_ids': [[6, False, [392, 391]]
            res.update({'emp_ids':context['task_employee_ids'][0][2]})
        return res
    def get_emp_related_details(self, cr, uid, emp_id):
        res = {}
        emp_obj = self.pool.get('hr.employee')
        emp = emp_obj.browse(cr, uid, emp_id)
        if not emp.product_id:
            raise osv.except_osv(_('Bad Configuration !'),
                 _('Please define product and product category property account on the related employee.\nFill in the HR Settings tab of the employee form.%s')%(emp.name,))

        if not emp.journal_id:
            raise osv.except_osv(_('Bad Configuration !'),
                 _('Please define journal on the related employee.\nFill in the timesheet tab of the employee form.%s')%(emp.name,))

        acc_id = emp.product_id.property_account_expense.id
        if not acc_id:
            acc_id = emp.product_id.categ_id.property_account_expense_categ.id
            if not acc_id:
                raise osv.except_osv(_('Bad Configuration !'),
                        _('Please define product and product category property account on the related employee.\nFill in the timesheet tab of the employee form.%s')%(emp.name,))

        res['product_id'] = emp.product_id.id
        res['journal_id'] = emp.journal_id.id
        res['general_account_id'] = acc_id
        res['product_uom_id'] = emp.product_id.uom_id.id
        res['employee_id'] = emp_id
        return res
    
    def get_user_related_details(self, cr, uid, user_id):
        res = {}
        emp_obj = self.pool.get('hr.employee')
        emp_id = emp_obj.search(cr, uid, [('user_id', '=', user_id)])
        if not emp_id:
            user_name = self.pool.get('res.users').read(cr, uid, [user_id], ['name'])[0]['name']
            raise osv.except_osv(_('Bad Configuration !'),
                 _('Please define employee for user "%s". You must create one.')% (user_name,))
        return self.get_emp_related_details(cr, uid, emp_id[0])

from openerp.addons.project_timesheet import project_timesheet   
'''
Improve the timesheet account analytic generating logic, replace the account analytic account for the mfg task
''' 
def _project_timesheet_create(self, cr, uid, vals, context=None):
    timesheet_obj = self.pool.get('hr.analytic.timesheet')
    task_obj = self.pool.get('project.task')
    uom_obj = self.pool.get('product.uom')        
    vals_line = {}
    if not context:
        context = {}
    if not context.get('no_analytic_entry',False):
        #johnw, 08/08/2014, Improve the timesheet account analytic generating logic, replace the account analytic account for the mfg task
        def _add_ana_line(ana_acc_id, employee_id):
            #set data from employee
            result = self.get_emp_related_details(cr, uid, employee_id)
            vals_line['employee_id'] = employee_id
            vals_line['product_id'] = result['product_id']            
            vals_line['product_uom_id'] = result['product_uom_id']
            vals_line['general_account_id'] = result['general_account_id']
            vals_line['journal_id'] = result['journal_id']
            # Calculate quantity based on employee's product's uom
            if result['product_uom_id'] != default_uom:
                vals_line['unit_amount'] = uom_obj._compute_qty(cr, uid, default_uom, vals_line['unit_amount'], result['product_uom_id'])
                        
            vals_line['account_id'] = ana_acc_id
            res = timesheet_obj.on_change_account_id(cr, uid, False, ana_acc_id)
            if res.get('value'):
                vals_line.update(res['value'])
                
            vals_line['amount'] = 0.0
            
            timeline_id = timesheet_obj.create(cr, uid, vals=vals_line, context=context)
            
            amount = vals_line['unit_amount']
            prod_id = vals_line['product_id']
            unit = False
            # Compute based on pricetype
            #add the employee_id parameter, so metro_hr.hr_timesheet.on_change_unit_amount() will calculate cost based on employee setting
            context.update({'employee_id':vals_line['employee_id']})
            amount_unit = timesheet_obj.on_change_unit_amount(cr, uid, timeline_id,
                prod_id, amount, False, unit, vals_line['journal_id'], context=context)
            if amount_unit and 'amount' in amount_unit.get('value',{}):
                updv = { 'amount': amount_unit['value']['amount'] }
                timesheet_obj.write(cr, uid, [timeline_id], updv, context=context)
            vals['hr_analytic_timesheet_id'] = timeline_id
                    
        task_data = task_obj.browse(cr, uid, vals['task_id'])
        emp_obj = self.pool.get('hr.employee')
        default_uom = self.pool.get('res.users').browse(cr, uid, uid).company_id.project_time_mode_id.id
        #check mfg_ids, employee_id, they are required for mfg task working hours
        if task_data.project_type == 'mfg':
            #mfg_ids structure is like: 'mfg_ids': [[6, False, [392, 391]]
            if len(vals.get('mfg_ids')[0][2]) <= 0:
                raise osv.except_osv(_('Error!'),_('The MFG IDs are required for the work order task\'s working hour!'))
            if not vals.get('emp_ids')[0][2]:
                raise osv.except_osv(_('Error!'),_('The Employees are required for the work order task\'s working hour!'))
        #set the common values
        vals_line['name'] = '%s: %s' % (tools.ustr(task_data.name), tools.ustr(vals['name'] or '/'))
        vals_line['user_id'] = vals['user_id']
        vals_line['date'] = vals['date'][:10]
        vals_line['unit_amount'] = vals['hours']
        #get the employee ids
        emp_ids = vals['emp_ids'][0][2]
        if not emp_ids:
            emp_id = emp_obj.search(cr, uid, [('user_id', '=', vals.get('user_id', uid))])
            if not emp_id:
                user_name = self.pool.get('res.users').read(cr, uid, [vals.get('user_id', uid)], ['name'])[0]['name']
                raise osv.except_osv(_('Bad Configuration !'),
                     _('Please define employee for user "%s". You must create one.')% (user_name,))
            emp_ids.append(emp_id[0])
                                    
        if task_data.project_type != 'mfg':
            acc_id = task_data.project_id and task_data.project_id.analytic_account_id.id or False
            for emp_id in emp_ids:
                _add_ana_line(acc_id, emp_id)
        else:            
            #mfg_ids structure is like: 'mfg_ids': [[6, False, [392, 391]]
            mfg_ids = vals['mfg_ids'][0][2]
            #split the hours by the count of ID
            vals_line['unit_amount'] = vals_line['unit_amount']/float(len(mfg_ids))
            #add ref
            vals_line['ref'] = '%s : %s'%(task_data.workorder_id.production_id.name, task_data.workorder_id.code)
            #loop to generate analytic lines by ID list, 
            for mfg_id in self.pool.get('sale.product').read(cr,uid,mfg_ids,['analytic_account_id'],context=context):
                if not mfg_id.get('analytic_account_id'):
                    continue
                acc_id = mfg_id.get('analytic_account_id')[0]
                for emp_id in emp_ids:
                    _add_ana_line(acc_id, emp_id)
    return super(project_timesheet.project_work,self).create(cr, uid, vals, context=context)   
project_timesheet.project_work.create = _project_timesheet_create     