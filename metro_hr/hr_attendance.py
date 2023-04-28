# -*- coding: utf-8 -*-

import time
from win32com.client import Dispatch
import sys  
from datetime import datetime  
import hashlib
import logging
from dateutil.relativedelta import relativedelta
from openerp.tools.translate import _
import traceback
import hr_clock_util as clock_util

from openerp.addons.metro import utils
import openerp.addons.decimal_precision as dp

from openerp.osv import fields, osv
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.misc import DEFAULT_SERVER_DATE_FORMAT
from openerp.addons.metro import utils

import pytz
'''
Working time group, handle the working time as a group:
date_from, date_to, calendar_id, name
...
'''
class hr_wt_grp(osv.osv):
    _name = "hr.wt.grp"
    _description="working time group"
    _columns = {
        'name' : fields.char('Name', size=32, required=True),
        'worktime_ids': fields.one2many('hr.wt.grp.line', 'grp_id', 'Working times'),  
    }

    def _check_wt(self,cr,uid,ids,context=None):
        date_wts=[]
        for grp in self.browse(cr, uid, ids):
            date_wts=[]
            for wt in grp.worktime_ids:
                if wt.date_to < wt.date_from:
                    raise osv.except_osv(_('Error'),_('Date to can not be earlier than from!'))                
                for period in date_wts:
                    if (wt.date_from >= period['from'] and wt.date_from <= period['to']) \
                            or (wt.date_to >= period['from'] and wt.date_to <= period['to']) \
                            or (wt.date_from <= period['from'] and wt.date_to >= period['to']):
                        raise osv.except_osv(_('Error'),_('Period duration of %s is conflicted with other periods!'%(wt.name)))
                date_wts.append({'from':wt.date_from, 'to':wt.date_to})
        return True
    
    def create(self, cr, uid, vals, context=None):
        new_id = super(hr_wt_grp, self).create(cr, uid, vals, context=context)
        self._check_wt(cr, uid, [new_id], context=context)
        return new_id    
        
    def write(self, cr, uid, ids, vals, context=None):
        resu = super(hr_wt_grp, self).write(cr, uid, ids, vals, context=context)
        self._check_wt(cr, uid, ids, context=context)
        return resu    
    
class hr_wt_grp_line(osv.osv):
    _name = 'hr.wt.grp.line'
    _description="working time group line"
    _columns = {
        'name' : fields.char('Name', size=32, required=True),
        'date_from' : fields.date('From Date', required=True),
        'date_to' : fields.date('To Date', required=True),
        'calendar_id' : fields.many2one("resource.calendar", "Working Time", required=True),
        'grp_id': fields.many2one('hr.wt.grp', 'Group', required=True, ondelete='cascade'),
    }  
    def onchange_calendar(self, cr, uid, ids, calendar_id, name, context=None):
        res = {'value':{}}
        if not calendar_id or (name and name != ''):
            return res
        cale_name = self.pool.get('resource.calendar').read(cr, uid, calendar_id, ['name'], context=context)['name']
        res['value']['name'] = cale_name
        return res

class hr_employee(osv.osv):
    _inherit = "hr.employee"
    _columns = {
        'last_punch_time': fields.datetime('Last Punching Time', required=False, select=1,readonly=True),
        'wt_grp_id': fields.many2one('hr.wt.grp', 'Working time group'),  
    }
    def get_wt(self, cr, uid, emp_id, dt_para=None, context=None):
        '''
        @param dt_para: time with timezone, can be local or UTC tz, but the real time should be in local, that is the employee punching time 
        '''
        emp = self.browse(cr, uid, emp_id, context=context)
        if not emp.wt_grp_id or not emp.wt_grp_id.worktime_ids:
            return None
        if not dt_para:
            dt_para = datetime.now()
            #Assume above returns UTC time, convert it to time with local TZ
            dt_para = fields.datetime.context_timestamp(cr, uid, dt_para, context=context) 
        wt_found = None
        for wt in emp.wt_grp_id.worktime_ids:            
            wt_from =  datetime.strptime(wt.date_from + ' 00:00:00',DEFAULT_SERVER_DATETIME_FORMAT)
            wt_to  = datetime.strptime(wt.date_to + ' 23:59:59', DEFAULT_SERVER_DATETIME_FORMAT)
            #above from/to shoule be treated as same as user's local time, so need convert them from local to UTC
            wt_from = utils.utc_timestamp(cr, uid, wt_from, context=context)
            wt_to = utils.utc_timestamp(cr, uid, wt_to, context=context)
            #the dt_para with local TZ can be compare with the from/to with UTC TZ 
            if dt_para >= wt_from and dt_para <= wt_to:
                wt_found = wt.calendar_id
                break
        return wt_found
    def update_punch_time(self, cr, uid, emp_id, dt_punch, context):
        if not emp_id or not dt_punch:
            return
        dt_punch_current = None
        dt_current = self.read(cr, uid, emp_id, ['last_punch_time'])
        if dt_current.get('last_punch_time'):
            dt_punch_current = datetime.strptime(dt_current.get('last_punch_time'),DEFAULT_SERVER_DATETIME_FORMAT)
            #convert to the offset aware datetime, since the dt_punch is offset aware, then they can be compared
            dt_punch_current = pytz.UTC.localize(dt_punch_current)
        if isinstance(dt_punch, type(u' ')):
            dt_punch = datetime.strptime(dt_punch,DEFAULT_SERVER_DATETIME_FORMAT)
            #convert to the offset aware datetime
            dt_punch = pytz.UTC.localize(dt_punch)
            
        if not dt_punch_current or dt_punch_current < dt_punch:
            self.write(cr, uid, emp_id, {'last_punch_time': dt_punch}, context=context)
    
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #the day search support
        new_args = utils.deal_args_dt(cr, user, self, args,['last_punch_time'],context=context)
        return super(hr_employee,self).search(cr, user, new_args, offset, limit, order, context, count)
        
class hr_attendance(osv.osv):
    _inherit = "hr.attendance"
    def _day_compute(self, cr, uid, ids, fieldnames, args, context=None):
        res = dict.fromkeys(ids, '')
        for obj in self.browse(cr, uid, ids, context=context):
            utc_time = datetime.strptime(obj.name, '%Y-%m-%d %H:%M:%S')
            local_time = fields.datetime.context_timestamp(cr, uid, utc_time, context=context)
            res[obj.id] = local_time.strftime('%Y-%m-%d')
        return res    
    _order = 'day desc, name asc'
    _columns = {
        'action': fields.selection([('sign_in', 'Sign In'), ('sign_out', 'Sign Out'), 
                                    ('sign_in_late', 'Sign In Late'), ('sign_out_early', 'Sign Out Early'), 
                                    ('invalid', 'Invalid') ,('action','Action')],
                                    'Action', required=True, select=True),
        'clock_log_id': fields.char('Clock Log ID', size=32, select=1),
        'clock_id': fields.many2one('hr.clock', string='Clock'),
        'notes': fields.char('Notes', size=128),
        'calendar_id' : fields.many2one("resource.calendar", "Working Time", required=False),
        'cale_period_id' : fields.many2one("resource.calendar.attendance", "Working Period", required=False, select=True),
        #redefined the _day_compute() method, to record the local day on this field
        'day': fields.function(_day_compute, type='char', string='Day', store=True, select=1, size=32),
        #the fields record the creation and write info
        'create_uid':  fields.many2one('res.users', 'Creator', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'write_uid':  fields.many2one('res.users', 'Modifier', readonly=True),
        'write_date': fields.datetime('Modify Date', readonly=True, select=True),        
        #the fields only for search usage
        'date_search_from':fields.function(lambda *a,**k:{}, type='datetime',string="From Date",),
        'date_search_to':fields.function(lambda *a,**k:{}, type='datetime',string="To Date",),
    }

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        res = []
        for data in self.read(cr, uid, ids, ['name', 'employee_id'], context=context):
            #convert date to local data
            name_local = utils.dtstr_utc2local(cr, uid, data['name'])
            res.append((data['id'],'%s[%s]'%(data['employee_id'][1],name_local) ))
        return res
        
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        name_old = self.read(cr, uid, id, ['name'], context=context)['name']
        default.update({
            'notes':None,
            'clock_log_id':None,
            'clock_id':None,
            'day':None,
        })
        return super(hr_attendance, self).copy(cr, uid, id, default, context)
    
    def _altern_si_so(self, cr, uid, ids, context=None):
        #disable this constraint
        return True

    _constraints = [(_altern_si_so, 'Error ! Sign in (resp. Sign out) must follow Sign out (resp. Sign in)', ['action'])]    
    
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #the day search support
        new_args = utils.deal_args_dt(cr, user, self, args,['name'],context=context)
        #the date_start/end parameter
        for arg in new_args:
            if arg[0] == 'date_search_from':
                arg[0] = 'name'
                arg[1] = '>='
            if arg[0] == 'date_search_to':
                arg[0] = 'name'
                arg[1] = '<='
                #for the end date, need add one day to use as the end day
                time_obj = datetime.strptime(arg[2],DEFAULT_SERVER_DATETIME_FORMAT)
                time_obj += relativedelta(days=1)                                
                arg[2] = time_obj.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        return super(hr_attendance,self).search(cr, user, new_args, offset, limit, order, context, count)
    
    def create(self, cr, uid, vals, context=None):
        new_id = super(hr_attendance, self).create(cr, uid, vals, context=context)
        self.pool.get('hr.employee').update_punch_time(cr, uid, vals.get('employee_id'), vals.get('name'), context=context)
        return new_id

    def write(self, cr, uid, ids, vals, context=None):
        resu = super(hr_attendance, self).write(cr, uid, ids, vals, context=context)
        emp_obj = self.pool.get('hr.employee')
        if vals.get('name'):
            if not vals.get('employee_id'):
                for attend in self.read(cr, uid, ids, ['employee_id', 'name'], context=context):
                    emp_obj.update_punch_time(cr, uid, attend['employee_id'][0], vals['name'], context=context)
            else:
                emp_obj.update_punch_time(cr, uid, vals['employee_id'], vals['name'], context=context)
        return resu
                
    def calc_action(self, cr, uid, ids, context=None):
        upt_vals = {}
        days = self._day_compute(cr, uid, ids, [], [], context=context)
        emp_obj = self.pool.get('hr.employee')
        for attend in self.browse(cr, uid, ids, context=context):
            #get the calendar id
            calendar_id = attend.calendar_id
            if not calendar_id:
                dt_para = fields.datetime.context_timestamp(cr, uid, datetime.strptime(attend.name,DEFAULT_SERVER_DATETIME_FORMAT), context=context)
                calendar_id = emp_obj.get_wt(cr, uid,  attend.employee_id.id, dt_para, context=context)
            if not calendar_id:
                continue
            dt_action = datetime.strptime(attend.name,DEFAULT_SERVER_DATETIME_FORMAT)
            #dt_uid = attend.employee_id.user_id and attend.employee_id.user_id.id or uid
            dt_uid = uid
            #the db value is UTC time, need to convert local time, since the attendance is by local hour setting
            dt_action_local = fields.datetime.context_timestamp(cr, dt_uid, dt_action, context=context)
            #get the action name and period
            action = 'invalid'
            cale_period_id = None
            action,cale_period_id = self.action_by_cale_time(cr, uid, calendar_id, dt_action_local , context=context)
            if action != 'invalid':
                '''
                check if there are existing same record or not, if yes, then set the action to invalid
                invalid standard: same period/action/day/employee, and the log time(name) is earlier than this attendance
                '''
                same_attend_ids = self.search(cr, uid, [('employee_id','=',attend.employee_id.id), 
                                      ('cale_period_id','=',cale_period_id),
                                      ('action','=',action),
                                      ('day','=',dt_action.strftime('%Y-%m-%d')),
                                      ('name','<',attend.name),
                                      ('id','!=',attend.id),
                                      ], context=context)
                if same_attend_ids:
                    action = 'invalid'
                    
            vals = {'action':action, 'cale_period_id':cale_period_id}
            if not attend.calendar_id:
                vals['calendar_id'] = calendar_id.id
            if days[attend.id]:
                vals['day'] = days[attend.id]
            self.write(cr, uid, attend.id, vals, context=context)
        
        return True
    
    def action_by_emp_cale_time(self, cr, uid, emp_id, cale_id, dt_action, context=None):
        actions = ['invalid',None]
        if emp_id:
            calendar_id = self.pool.get('hr.employee').get_wt(cr, uid,  emp_id, context=context)
            actions = self.action_by_cale_time(cr, uid, calendar_id, dt_action, context)
        return actions
    
    def action_by_cale_time(self, cr, uid, calendar_id, dt_action, context=None):
        """Calculates the  attendance action based on calendar and the datetime
        given working day (datetime object).
        @param calendar_id: resource.calendar id or browse record
        @param dt_action: given datetime object to get attendance action
        @return: returns the list [action,work_period_id]:
        attendance action: sign_in, sign_in_late, sign_out, sign_out_early, action
        work_period_id: resource_calednar_attendance.id
        """
        action = 'invalid'
        working_period_id = None
        if not calendar_id:
            return action
        if isinstance(calendar_id,(int, long)):
            calendar_id = self.browse(cr, uid, calendar_id, context=context)
        for working_day in calendar_id.attendance_ids:
            if (int(working_day.dayofweek) + 1) == dt_action.isoweekday():
                hour_check = dt_action.hour + dt_action.minute/60.0
                #default gap is 10 minutes
                default_start_stop_gap = calendar_id.tolerence_start_stop_default/60.0
                default_late_early_gap = calendar_id.tolerence_late_early_default/60.0
                
                punch_in_start = working_day.punch_in_start
                if punch_in_start == 0 or punch_in_start > working_day.hour_from:
                    punch_in_start = working_day.hour_from - default_start_stop_gap
                punch_in_late = working_day.punch_in_late
                if punch_in_late == 0 or punch_in_late < working_day.hour_from:
                    punch_in_late = working_day.hour_from + default_late_early_gap
                punch_in_stop = working_day.punch_in_stop
                if punch_in_stop == 0 or punch_in_stop < working_day.hour_from:
                    punch_in_stop = working_day.hour_from + default_start_stop_gap
                #sign in checking
                if hour_check >= punch_in_start and hour_check <=  punch_in_late:
                    action = 'sign_in'
                #sign in late checking
                if hour_check > punch_in_late and hour_check <=  punch_in_stop:
                    action = 'sign_in_late'

                punch_out_start = working_day.punch_out_start
                if punch_out_start == 0 or punch_out_start > working_day.hour_to:
                    punch_out_start = working_day.hour_to - default_start_stop_gap
                punch_out_early = working_day.punch_out_early
                if punch_out_early == 0 or punch_out_early > working_day.hour_to:
                    punch_out_early = working_day.hour_to - default_late_early_gap
                punch_out_stop = working_day.punch_out_stop
                if punch_out_stop == 0 or punch_out_stop < working_day.hour_to:
                    punch_out_stop = working_day.hour_to + default_start_stop_gap                    
                #sign our early checking
                if hour_check > punch_out_start and hour_check <  punch_out_early:
                    action = 'sign_out_early'
                #sign out checking
                if hour_check >= punch_out_early and hour_check <=  punch_out_stop:
                    action = 'sign_out'
                    
                #find value then break
                if action != 'invalid':
                    working_period_id = working_day.id
                    break
        return action, working_period_id

class resource_calendar(osv.osv):
    _inherit = "resource.calendar"
    _columns = {
        'type' : fields.selection([('emp_wt','Employee Working Time'),('simple','Simple')], string='Type', required=True),
        'tolerence_start_stop_default': fields.integer('Default Start/Stop Tolerance (minutes)',
                                  help="default tolerance for the punching start/stop time comparing to the resource_calendar_attendance's hour from/to"),
        'tolerence_late_early_default': fields.integer('Default Late/Early Tolerance (minutes)',
                                  help="default tolerance in minutes for the punching late/early time comparing to the resource_calendar_attendance's hour from/to"),
        'no_in_option':fields.selection([('late', 'Be Late'), ('absent', 'Absenteeism')], 'How to Deal No Sign In',
                                                help="the configuration how to deal with the attendance only have sign in"),
        'no_in_time': fields.integer('No In to Subtract Minutes',
                                                help="if 'Be Late', then this field identify the minutes that will be substract from the 'WorkHours'"),
        'no_out_option':fields.selection([('early', 'Leave Early'), ('absent', 'Absenteeism')], 'How to Deal No Sign Out',
                                                help = " the configuration how to deal with the attendance only have sign out"),
        'no_out_time': fields.integer('No Out to Subtract Minutes',
                                                help="if 'Leave Early', then this field identify the minutes that will be substract from the 'WorkHours'"),                     
    }
    _defaults={'type':'simple', 'tolerence_start_stop_default':10, 'tolerence_late_early_default':10}
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Calendar must be unique!'),
    ]
    
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        name_old = self.read(cr, uid, id, ['name'], context=context)['name']
        default.update({
            'name':'%s(Copy)'%(name_old,),
        })
        return super(resource_calendar, self).copy(cr, uid, id, default, context)
        
    
    def default_get(self, cr, uid, fields, context=None):
        vals = super(resource_calendar, self).default_get(cr, uid, fields, context=context)
        if not vals:
            vals = {}
        company_obj = self.pool.get('res.company')
        company_id = company_obj._company_default_get(cr, uid, 'resource.calendar', context=context)
        if company_id:
            vals.update({'company_id':company_id})
            flds = ['hr_att_tole_start_stop_default', 'hr_att_tole_late_early_default', 
                    'hr_att_no_in_option', 'hr_att_no_in_time', 'hr_att_no_out_option', 'hr_att_no_out_time']
            company_data = company_obj.browse(cr, uid, company_id, context=context)
            if company_data:
                vals.update({
                             'tolerence_start_stop_default':company_data.hr_att_tole_start_stop_default,
                             'tolerence_late_early_default':company_data.hr_att_tole_late_early_default,
                             'no_in_option':company_data.hr_att_no_in_option,
                             'no_in_time':company_data.hr_att_no_in_time,
                             'no_out_option':company_data.hr_att_no_out_option,
                             'no_out_time':company_data.hr_att_no_out_time,
                             })                                
        return vals    
    

class hr_worktime_type(osv.osv):
    _name = "hr.worktime.type"
    _description = "Working time type"
    _columns = {
        'sequence':fields.integer('Sequence'),
        'name':fields.char('Type', size=64, required=True),
    }
        
class resource_calendar_attendance(osv.osv):
    _inherit = "resource.calendar.attendance"
    def _calc_hours(self, cr, uid, ids, field_names, args, context=None):
        vals = dict((id,dict((field_name,0) for field_name in field_names)) for id in ids)
        for data in self.read(cr, uid, ids, ['hour_to','hour_from','hours_non_work','hours_work_ot','hours_work_ot2'], context=context):
            vals[data['id']]['hours_total'] = data['hour_to'] - data['hour_from']
            vals[data['id']]['hours_work'] = vals[data['id']]['hours_total'] - data['hours_non_work']
            vals[data['id']]['hours_work_normal'] = vals[data['id']]['hours_work'] - data['hours_work_ot']
            vals[data['id']]['is_full_ot'] = vals[data['id']]['hours_work'] == data['hours_work_ot']
            vals[data['id']]['hours_work_normal2'] = vals[data['id']]['hours_work'] - data['hours_work_ot2']
            vals[data['id']]['is_full_ot2'] = vals[data['id']]['hours_work'] == data['hours_work_ot2']
        return vals
        
    '''
    HourForm-HourTo=Total Hours = Normal Working Hours + OT Hours + NonWorkingHours 
    TotalHours-NonWorkingHours=WorkHours
    WorkHours-OTHours = Normal Working Hours
    '''    
    _columns = {                
        'type_id': fields.many2one('hr.worktime.type', string='Type'),
        
        'punch_in_start': fields.float('Sign in punching start'),
        'punch_in_late': fields.float('Sign in punching late'),
        'punch_in_stop': fields.float('Sign in punching stop'),
                        
        'punch_out_start': fields.float('Sign out punching start'),
        'punch_out_early': fields.float('Sign out punching early'),
        'punch_out_stop': fields.float('Sign out punching stop'),
        
        'hours_non_work': fields.float('Non work hours'),
        'hours_work_ot': fields.float('Working hours(OT)'),
    
        'hours_total': fields.function(_calc_hours, type='float', string='Total hours', multi='hours_all', help='[Work to] - [Work from]'),
        'hours_work': fields.function(_calc_hours, type='float', string='Working hours', multi='hours_all', help='[Total hours] - [Non work hours]'),
        'hours_work_normal': fields.function(_calc_hours, type='float', string='Working hours(normal)', multi='hours_all', help='[Working hours] - [Working hours(OT)]'),
        
        'is_full_ot': fields.function(_calc_hours, type='boolean', string='Full OT', multi='hours_all'),
        'days_work': fields.float('Work Days', digits_compute=dp.get_precision('Product Unit of Measure')),
        
        #second setting
        'hours_work_ot2': fields.float('Working hours(OT)2'),        
        'hours_work_normal2': fields.function(_calc_hours, type='float', string='Working hours(normal)2', multi='hours_all', help='[Working hours] - [Working hours(OT)2]'),
        'is_full_ot2': fields.function(_calc_hours, type='boolean', string='Full OT2', multi='hours_all'),
        'days_work2': fields.float('Work Days2', digits_compute=dp.get_precision('Product Unit of Measure')),        
        }   
    _defaults={'days_work':1, 'days_work2':1}

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        res = []
        for data in self.read(cr, uid, ids, ['name', 'calendar_id'], context=context):
            if context.get('name_with_calendar'):
                res.append((data['id'],'%s of %s'%(data['name'], data['calendar_id'][1]) ))
            else:
                res.append((data['id'], data['name']))
        return res    
    
class res_company(osv.osv):
    _inherit = "res.company"
    _columns = {
        'hr_att_tole_start_stop_default': fields.integer('Default Start/Stop Tolerance (minutes)',
                                                help="default tolerance for the punching start/stop time comparing to the resource_calendar_attendance's hour from/to"),
        'hr_att_tole_late_early_default': fields.integer('Default Late/Early Tolerance (minutes)',
                                                help="default tolerance in minutes for the punching late/early time comparing to the resource_calendar_attendance's hour from/to"),
        'hr_att_no_in_option':fields.selection([('late', 'Be Late'), ('absent', 'Absenteeism')], 'How to Deal No Sign In',
                                                help="the configuration how to deal with the attendance only have sign in"),
        'hr_att_no_in_time': fields.integer('No In to Subtract Minutes',
                                                help="if 'Be Late', then this field identify the minutes that will be substract from the 'WorkHours'"),
        'hr_att_no_out_option':fields.selection([('early', 'Leave Early'), ('absent', 'Absenteeism')], 'How to Deal No Sign Out',
                                                help = " the configuration how to deal with the attendance only have sign out"),
        'hr_att_no_out_time': fields.integer('No Out to Subtract Minutes',
                                                help="if 'Leave Early', then this field identify the minutes that will be substract from the 'WorkHours'"),      
        'month_attend_days_law': fields.float('Month working days in law')  
    }    
    _defaults={'month_attend_days_law':21.75}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
