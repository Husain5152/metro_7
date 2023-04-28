#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    d$
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

import time
from datetime import date
from datetime import datetime
from datetime import timedelta
from dateutil import relativedelta
import traceback
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT

from openerp import netsvc
from openerp.osv import fields, osv
from openerp import tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

from openerp.tools.safe_eval import safe_eval as eval
from openerp.addons.metro import utils

class hr_dimission_item_template(osv.osv):
    _name = 'hr.dimission.item.template'
    _description = 'Dimission item template'
    _order = 'type, sequence'
    
    _columns = {
        'type':fields.selection([('approve','Approval'),('transfer','Transfer')], string='Type', required=True ),
        'sequence': fields.integer('#', required=True),
        'name':fields.char('Name', size=64, required=True),
        'note':fields.char('Description', size=256, required=True),
        'department_id':fields.many2one('hr.department','Department'),
        'done_required':fields.boolean('Required for Done'),
        'company_id':fields.many2one('res.company', 'Company', required=True),   
    }
    
    _defaults = {
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'hr.dimission', context=c),
        'done_required': True
    }
    
    _sql_constraints = [
        ('name_uniq', 'unique(name, type)', 'Name must be unique per Type!'),
    ]
    
class hr_dimission(osv.osv):
    _name = 'hr.dimission'
    _description = 'Employee Dimission'
    _order = 'id desc'
    _rec_name = 'employee_id'
    def _emp_clocks(self, cr, uid, ids, field_names, args, context=None):
        '''
        Get the clocks that the employee is on
        '''
        resu = dict.fromkeys(ids,None)
        clock_sync_obj = self.pool.get("hr.clock.emp.sync")
        clock_ids = self.pool.get("hr.clock").search(cr, uid, [], context=context)
        clock_ids_exist = []
        try:
            for order in self.browse(cr, uid, ids, context=context):
                emp_code = order.employee_id.emp_code
                for clock_id in clock_ids:
                    emps_clock = clock_sync_obj.clock_emps_get(cr, uid, clock_id, [emp_code], context=context)
                    if emps_clock:
                        clock_ids_exist.append(clock_id)
                resu[order.id] = clock_ids_exist
        except Exception,e:
            traceback.print_exc()
            pass 
        return resu
    _columns = {
        'employee_id': fields.many2one('hr.employee',  'Employee', required=True, select=True),
        'department_id':fields.related('employee_id','department_id', type='many2one', relation='hr.department', string='Department', store=True),
        'job_id':fields.related('employee_id','job_id', type='many2one', relation='hr.job', string='Title', store=True),
        'emp_code':fields.related('employee_id','emp_code', type='char', string='Employee Code', store=True),
        'mobile_phone':fields.related('employee_id','mobile_phone', type='char', string='Work Mobile', store=True),
        'borrow_money_residual':fields.related('employee_id','money_residual', type='float', string='Borrowed residual', readonly=True),
        
        'dimmission_reason':fields.text('Dimission Reason', required=True),
        'advice_to_company':fields.text('Advice to company'),
        'employment_start':fields.date('Employment Started'),
        'date_request':fields.date('Request Date', required=True),
        'date_done':fields.date('Done Date', required=False, readonly=True),
        
        'approve_ids': fields.one2many('hr.dimission.item', 'dimission_id', 'Approvals', domain=[('type','=','approve')]),
        'transfer_ids': fields.one2many('hr.dimission.item', 'dimission_id', 'Transfers', domain=[('type','=','transfer')]),
        
        'payslip_id': fields.many2many('hr.emppay', string='Payslip'),
        'attrpt_ids': fields.many2many('hr.rpt.attend.month', string='Attendance Reports'),
        'hr_clock_ids': fields.function(_emp_clocks, string='HR Clocks', type='many2many', relation='hr.clock', readonly=True),
        'attachment_lines': fields.one2many('ir.attachment', 'hr_admission_id','Attachment'),    
        'company_id':fields.many2one('res.company', 'Company', required=True),   
                                                     
        'state': fields.selection([
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('cancel', 'Cancel'),
        ], 'Status', select=True, readonly=True),
    }
    
    _defaults = {
        'state': 'draft',
    }
    
    def default_get(self, cr, uid, fields_list, context=None):
        defaults = super(hr_dimission, self).default_get(cr, uid, fields_list, context=context)
        if not defaults:
            defaults = {}
        
        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        item_tmpl_obj = self.pool.get('hr.dimission.item.template')
        #dimission approve items
        approve_ids = []
        approve_items = company_id.approve_ids
        if not approve_items:
            item_ids = item_tmpl_obj.search(cr, uid, [('type','=','approve')], context=context)
            approve_items = item_tmpl_obj.browse(cr, uid, item_ids, context=context)
        for item in approve_items:
            approve_ids.append({'template_id':item.id,
                                            'type':item.type,
                                            'sequence':item.sequence,
                                            'name':item.name,
                                            'note':item.note,
                                            'department_id':item.department_id.id,
                                            'done_required':item.done_required,
                                            })
        #dimission transfer items
        transfer_ids = []
        transfer_items = company_id.transfer_ids
        if not transfer_items:
            item_ids = item_tmpl_obj.search(cr, uid, [('type','=','transfer')], context=context)
            transfer_items = item_tmpl_obj.browse(cr, uid, item_ids, context=context)
        for item in transfer_items:
            transfer_ids.append({'template_id':item.id,
                                            'type':item.type,
                                            'sequence':item.sequence,
                                            'name':item.name,
                                            'note':item.note,
                                            'department_id':item.department_id.id,
                                            'done_required':item.done_required,
                                            })
            
        defaults.update({'company_id':company_id.id, 'approve_ids':approve_ids, 'transfer_ids':transfer_ids})
        return defaults
        
    def onchange_employee(self, cr, uid, ids, emp_id, context=None):
        if not emp_id:
            return {'value':{}}
        emp = self.pool.get('hr.employee').browse(cr, uid, emp_id, context=context)
        vals = {'department_id':emp.department_id.id, 'job_id':emp.job_id.id, 'emp_code':emp.emp_code, 'mobile_phone':emp.mobile_phone, 'employment_start':emp.employment_start}
        return {'value':vals}        

    def unlink(self, cr, uid, ids, context=None):
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.state not in  ['draft', 'cancel']:
                raise osv.except_osv(_('Warning!'),_('You cannot delete a payslip which is not draft or cancel!'))
        return super(hr_dimission, self).unlink(cr, uid, ids, context)            

    def action_confirm(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'in_progress'}, context=context)   
    
    def action_done(self, cr, uid, ids, context=None):
        if not ids:
            return False
        if isinstance(ids, (int,long)):
            ids = [ids]
        order_id = ids[0]
        '''
        do done checking and auto update hr.employee and hr.contract
        1.Payslip is required
        2.Employee can not have Borrowed money residual 
        3.All approvals and transders with 'done_required' flag must be approved or done.
        '''        
        order = self.browse(cr, uid, order_id, context)
        if not order.payslip_id:
            raise osv.except_osv(_('Error!'),_('Payslip is required for done!'))
        if order.borrow_money_residual != 0:
            raise osv.except_osv(_('Error!'),_('Borrowed residual must be zero for done!'))
        for item in order.approve_ids:
            if item.done_required and item.state_approve != 'approved':
                raise osv.except_osv(_('Error!'),_('%s is not approved, can not finish the dimission!')%(item.name,))
        for item in order.transfer_ids:
            if item.done_required and item.state_transfer != 'done':
                raise osv.except_osv(_('Error!'),_('%s is not done, can not finish the dimission!')%(item.name,))            
        '''
        update related data
        '''
        #1.设置员工:辞职申请: employment_resigned, 离职日期:employment_finish , active=false
#        emp_vals = {'employment_resigned':order.date_request, 'employment_finish': datetime.now(), 'active':False}
#        self.pool.get('hr.employee').write(cr, uid, order.employee_id.id, emp_vals, context=context)
        #2.禁用相关res_users
        if order.employee_id.user_id:
            self.pool.get('res.users').write(cr, uid, order.employee_id.user_id.id, {'active':False}, context=context)
            
        #update dimission order
        return self.write(cr, uid, ids, {'state': 'done', 'date_done':datetime.now()}, context=context)
    
    
    def action_rehire(self, cr, uid, ids, context=None):
        if not ids:
            return False
        if isinstance(ids, (int,long)):
            ids = [ids]
        order_id = ids[0]        
        order = self.browse(cr, uid, order_id, context)
        if order.employee_id.active:
            return True            
        '''
        update related data
        '''
        #1.设置员工:开始工作:employment_start, 辞职申请: employment_resigned, 离职日期:employment_finish , active=True
        emp_vals = {'employment_start':datetime.now(), 'employment_resigned':None, 'employment_finish': None, 'active':True}
        self.pool.get('hr.employee').write(cr, uid, order.employee_id.id, emp_vals, context=context)
        #2.可用相关res_users
        if order.employee_id.user_id:
            self.pool.get('res.users').write(cr, uid, order.employee_id.user_id.id, {'active':True}, context=context)
        
        #goto employee form page, let user change other employee's data
        form_view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'hr', 'view_employee_form')
        form_view_id = form_view and form_view[1] or False
        return {
            'name': _('Employee'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [form_view_id],
            'res_model': 'hr.employee',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': order.employee_id.id,
        }
        
    def print_attendance(self, cr, uid, ids, context=None):
        order = self.browse(cr, uid, ids[0], context=context)
        if not order.attrpt_ids:
            return True
        #call attend month report to get the PDF
        return self.pool.get('hr.rpt.attend.month').pdf_attend_emp(cr, uid, [att.id for att in order.attrpt_ids], context=context, emp_ids=[order.employee_id.id])
        
    def print_payslip(self, cr, uid, ids, context=None):
        order = self.read(cr, uid, ids[0], ['payslip_id'], context=context)
        if not order['payslip_id']:
            return True
        #call attend month report to get the PDF
        return self.pool.get('hr.emppay').print_slip(cr, uid, order['payslip_id'], context=None)

    def remove_from_clock(self, cr, uid, ids, context=None):
        order = self.browse(cr, uid, ids[0], context=context)
        if not order.hr_clock_ids:
            return True
        #call attend month report to get the PDF
        return self.pool.get('hr.clock.emp.sync').clock_emps_delete_exec(cr, uid, order.hr_clock_ids, [order.employee_id], context=None)          

    def action_cancel(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'cancel'}, context=context)    

    def action_cancel2draft(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'draft'}, context=context)
                    
class ir_attachment(osv.osv):
    _inherit = "ir.attachment"
    _columns = {
        'hr_admission_id': fields.many2one('hr.dimission', 'Dimission'),
    }
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if vals.get('hr_admission_id'):
            vals['res_id'] = vals['hr_admission_id']
            vals['res_model'] = 'hr.dimission'            
        return super(ir_attachment, self).create(cr, uid, vals, context)    
            
class hr_dimission_item(osv.osv):
    _name = 'hr.dimission.item'
    _description = 'Dimission Items'
    _rec_name = 'template_id'
    
    _columns = {
        'dimission_id':fields.many2one('hr.dimission', 'Dimission', required=True, ondelete='cascade'),
        'template_id':fields.many2one('hr.dimission.item.template', 'Name', required=True),
        
        #copy from template
        'type': fields.related('template_id', 'type', type='selection', selection=[('approve','Approval'),('transfer','Transfer')], store=True),        
        'sequence': fields.integer('#', required=True),
        'name':fields.char('Name', size=64, required=True),
        'note':fields.char('Description', size=256, required=True),
        'department_id':fields.many2one('hr.department','Department'),
        'done_required':fields.boolean('Required for Done'),
        
        #the result selection
        'state_approve':fields.selection([('approved','Approved'),('rejected','Rejected')], 'State of Approve'),
        'state_transfer':fields.selection([('done','Done'),('pending','Pending')], 'State of Transfer'),
        #related employee
        'process_emp_id':fields.many2one('hr.employee', 'Employee'),
        'process_date':fields.date('Date'),
        #attached docment
        'doc_file': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file,  type='binary',  string = 'Document', multi="_get_file"),
        'doc_file_name': fields.char('Document File Name'), 
    }
        
    def onchange_department(self, cr, uid, ids, dept_id, context=None):
        if not dept_id:
            return {'value':{}}
        dept = self.pool.get('hr.department').read(cr, uid, dept_id, ['manager_id'], context=context)        
        vals = {'process_emp_id':None}
        if dept['manager_id']:
            vals = {'process_emp_id':dept['manager_id'][0]}
        return {'value':vals}       

class res_company(osv.osv):
    _inherit = "res.company"
    _columns = {
        #supply the relation parameter, otherwise, the data wll be saved to same relation table, that will make issue
        'approve_ids':fields.many2many('hr.dimission.item.template', rel='company_dimission_approvals', string='Dimission Approvals', domain=[('type','=','approve')]),
        'transfer_ids':fields.many2many('hr.dimission.item.template', rel='company_dimission_transfers', string='Dimission Transfers', domain=[('type','=','transfer')]),
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
