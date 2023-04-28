# -*- coding: utf-8 -*-

import datetime
import time
from itertools import groupby
from operator import itemgetter

import math
from openerp import netsvc
from openerp import tools
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp.addons.metro import utils

class hr_holidays_status(osv.osv):
    _inherit = "hr.holidays.status"
    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        res = []
        for record in self.browse(cr, uid, ids, context=context):
            name = record.name
            if not record.limit:
                #各个假期类型每个人的已用和可用时间的计算,"抹掉小数点"的问题
                #since the %d will remove the digit number, so use %s, like 0.05 will be converted zero in %d format
                #name = name + ('  (%d/%d)' % (record.leaves_taken or 0.0, record.max_leaves or 0.0))
                name = name + ('  (%s/%s)' % (record.leaves_taken or 0.0, record.max_leaves or 0.0))
            res.append((record.id, name))
        return res
    
class hr_holidays(osv.osv):
    _inherit = "hr.holidays"
    _order = "date_from desc, type desc"
    def _double_validation(self, cr, uid, ids, field_names, arg, context=None):
        res = {}
        for leave in self.browse(cr, uid, ids, context=context):
            res[leave.id] = leave.holiday_status_id.double_validation
            if not res[leave.id] and leave.type == 'remove':
                if leave.number_of_days_temp > leave.company_id.hr_holiday_leave_second_approve_days:
                    res[leave.id] = True
        return res
                
    _columns = {
            'job_id': fields.related('employee_id', 'job_id', string='Job', type='many2one', relation='hr.job', readonly=True),
            'ticket_approve_id': fields.many2one('hr.employee', 'Department Approval(ticket)', help='The department approve user on the leave ticket'),
            'ticket_approve_id2': fields.many2one('hr.employee', 'CEO Approval(ticket)', help='The CEO approve user on the leave ticket'),
            #redefine this field, add the days checking
            'double_validation': fields.function(_double_validation, 'double_validation', type='boolean', relation='hr.holidays.status', string='Apply Double Validation'),
            'company_id': fields.many2one('res.company','Company',required=True,),
    }

    _defaults = {
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'hr.holidays', context=c),
    }
    def unlink(self, cr, uid, ids, context=None):
        for order in self.read(cr, uid, ids, ['state','name'], context=context):
            if order['state'] not in ('draft','cancel'):
                raise osv.except_osv(_('Error!'),_('%s can not be delete, only "To Submit" or "Cancelled" request can be delete!')%(order['name'],))
        return super(hr_holidays, self).unlink(cr, uid, ids, context)
    def onchange_employee(self, cr, uid, ids, employee_id):
        result = {'value': {'department_id': False, 'job_id': False, 'emp_code': False}}
        if employee_id:
            employee = self.pool.get('hr.employee').browse(cr, uid, employee_id)
            result['value'] = {'department_id': employee.department_id.id,
                               'job_id': employee.job_id.id,}
        return result   
        
    EMAIL_ACTIONS = {'confirmed':{'msg':'need your approval','groups':[]},
                  'first_validated':{'msg':'manager approved, need your super approval','groups':[]},
                  'validated':{'msg':'approved','groups':[]},
                  'refused':{'msg':'refused','groups':[],},
                  }
    def _email_notify(self, cr, uid, ids, action, context=None):        
        order = self.browse(cr, uid, ids[0], context=context)
        email_to = []
        #send to manager
        if action == 'confirmed' \
            and order.employee_id \
            and order.employee_id.parent_id \
            and order.employee_id.parent_id.user_id \
            and order.employee_id.parent_id.user_id.email:
            email_to.append(order.employee_id.parent_id.user_id.email)
        #send to super manager, manager's manager
        if action == 'first_validated' \
            and order.employee_id \
            and order.employee_id.parent_id:
            manager_id_emp = order.employee_id.parent_id
            if manager_id_emp.parent_id \
                and manager_id_emp.parent_id.user_id \
                and manager_id_emp.parent_id.user_id.email:
                email_to.append(manager_id_emp.parent_id.user_id.email)
            elif manager_id_emp.user_id \
                and manager_id_emp.user_id.email:
                email_to.append(manager_id_emp.user_id.email)
        #send to the employee on the leave, final approved or refused
        if order.employee_id.user_id \
            and order.employee_id.user_id.email:
            email_to.append(order.employee_id.user_id.email)
            
        subject_fields = ['employee_id.name', 'name']
        utils.email_notify(cr, uid, self._name, ids, self.EMAIL_ACTIONS, action, subject_fields = subject_fields, email_to = email_to, context=context)

'''
remove this checking, since it use 'hr.holidays.status' rights to check, useless
johnw, 11/29/2014
'''
from openerp.addons.hr_holidays.hr_holidays import hr_holidays as hr_holidays_super
def _holiday_write(self, cr, uid, ids, vals, context=None):
    '''
    check_fnct = self.pool.get('hr.holidays.status').check_access_rights
    for  holiday in self.browse(cr, uid, ids, context=context):
        if holiday.state in ('validate','validate1') and not check_fnct(cr, uid, 'write', raise_exception=True):
            raise osv.except_osv(_('Warning!'),_('You cannot modify a leave request that has been approved. Contact a human resource manager.'))
    '''
    return super(hr_holidays_super, self).write(cr, uid, ids, vals, context=context)
hr_holidays_super.write = _holiday_write
                     
class res_company(osv.osv):
    _inherit = "res.company"
    _columns = {
        'hr_holiday_leave_second_approve_days': fields.integer('Max days that do not need CEO approval',
                                                help="The maximal days that do not need CEO approval "),  
    }    
    _defaults={'hr_holiday_leave_second_approve_days':2}
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
