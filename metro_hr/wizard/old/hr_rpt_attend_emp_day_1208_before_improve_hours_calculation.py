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
from lxml import etree
from dateutil import rrule
from datetime import datetime, timedelta
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.misc import DEFAULT_SERVER_DATE_FORMAT
from openerp.addons.metro import utils

from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
'''
Attendance report by employee and day, working period
'''
class hr_rpt_attend_emp_day(osv.osv_memory):
    _name = "hr.rpt.attend.emp.day"
    _inherit = "rpt.base"
    _description = "HR Attendance Employee Day Report"
    _columns = {
        #report data lines
        'rpt_lines': fields.one2many('hr.rpt.attend.emp.day.line', 'rpt_id', string='Report Line'),
        'date_from': fields.datetime("Start Date", required=True),
        'date_to': fields.datetime("End Date", required=True),
        'emp_ids': fields.many2many('hr.employee', string='Employees'),
        }

    _defaults = {
        'type': 'attend_emp_day',     
#        'emp_ids':[342,171]
    }
    def default_get(self, cr, uid, fields, context=None):
        vals = super(hr_rpt_attend_emp_day, self).default_get(cr, uid, fields, context=context)
        if 'date_from' in fields:
            #For the datetime value in defaults, need convert the local time to UTC, the web framework will convert them back to local time on GUI
            date_from =datetime.strptime(time.strftime('%Y-%m-01 00:00:00'), '%Y-%m-%d %H:%M:%S')
            date_from_utc = utils.utc_timestamp(cr, uid, date_from, context)
            vals.update({'date_from':date_from_utc.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                         
        if 'date_to' in fields:
            date_to = datetime.strptime(time.strftime('%Y-%m-%d 23:59:59'), '%Y-%m-%d %H:%M:%S')        
            date_to_utc = utils.utc_timestamp(cr, uid, date_to, context)        
            vals.update({'date_to':date_to_utc.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        
        return vals
                
    def _check_dates(self, cr, uid, ids, context=None):
        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.date_from and wiz.date_to and wiz.date_from > wiz.date_to:
                return False
        return True

    _constraints = [
        (_check_dates, 'The date end must be after the date start.', ['date_from','date_to']),
    ]
    
    def get_report_name(self, cr, uid, id, rpt_name, context=None):
        return "Attendance Employee Day Report"
            
    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        res = []
        for id in ids:
            res.append((id,'%s'%(id,) ))
        return res
    def _convert_save_dates(self, cr, uid, vals, context):
        #convert to the date like '2013-01-01' to UTC datetime to store
        if 'date_from' in vals and len(vals['date_from']) == 10:
            date_from = vals['date_from']
            date_from = utils.utc_timestamp(cr, uid, datetime.strptime(date_from + ' 00:00:00', DEFAULT_SERVER_DATETIME_FORMAT),context=context)
            date_from = date_from.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            vals['date_from'] = date_from
        if 'date_to' in vals and len(vals['date_to']) == 10:
            date_to = vals['date_to']
            date_to = utils.utc_timestamp(cr, uid, datetime.strptime(date_to + ' 23:59:59', DEFAULT_SERVER_DATETIME_FORMAT),context=context)
            date_to = date_to.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            vals['date_to'] = date_to
            
    def create(self, cr, uid, vals, context=None):
        self._convert_save_dates(cr, uid, vals, context)
        id_new = super(hr_rpt_attend_emp_day, self).create(cr, uid, vals, context=context)
        return id_new
    def write(self, cr, uid, ids, vals, context=None):
        self._convert_save_dates(cr, uid, vals, context)
        resu = super(hr_rpt_attend_emp_day, self).write(cr, uid, ids, vals, context=context)
        return resu
    
    def _attend_hours(self, hours_valid, period):
        '''
        if hours_valid > period.hours_work_normal:
            hours_normal = period.hours_work_normal
        else:
            hours_normal = hours_valid
        hours_ot = hours_valid - hours_normal
        if hours_ot > period.hours_work_ot:
            hours_ot = period.hours_work_ot
        #the second time group                        
        if hours_valid > period.hours_work_normal2:
            hours_normal2 = period.hours_work_normal2
        else:
            hours_normal2 = hours_valid
        hours_ot2 = hours_valid - hours_normal2
        if hours_ot2 > period.hours_work_ot2:
            hours_ot2 = period.hours_work_ot2
        '''
        if hours_valid > period.hours_work_normal:
            hours_normal = period.hours_work_normal
        else:
            hours_normal = hours_valid
        hours_ot = hours_valid - hours_normal
        if hours_ot > period.hours_work_ot:
            hours_ot = period.hours_work_ot
        #the second time group                        
        if hours_valid > period.hours_work_normal2:
            hours_normal2 = period.hours_work_normal2
        else:
            hours_normal2 = hours_valid
        hours_ot2 = hours_valid - hours_normal2
        if hours_ot2 > period.hours_work_ot2:
            hours_ot2 = period.hours_work_ot2        
        return hours_normal, hours_ot, hours_normal2, hours_ot2
    
    def run_attend_emp_day(self, cr, uid, ids, context=None):
        '''
        1.Query all data with both in/out by date range, store the result in attends_normal
        2.Loop on by days and employees
        '''
        emp_obj = self.pool.get('hr.employee')
        attend_obj = self.pool.get('hr.attendance')
        
        if context is None: context = {}         
        rpt = self.browse(cr, uid, ids, context=context)[0]
        date_from = datetime.strptime(rpt.date_from,DEFAULT_SERVER_DATETIME_FORMAT)
        date_to = datetime.strptime(rpt.date_to,DEFAULT_SERVER_DATETIME_FORMAT)
        #report data line
        rpt_lns = []
        #context for the query
        c = context.copy()
        #get the employees
        emp_ids = [emp.id for emp in rpt.emp_ids]
        if not emp_ids:
            emp_ids = emp_obj.search(cr, uid, [], context=context)

        '''
        1.Query all data with both in/out by date range, store the result in attends_normal
        '''
        sql = '''
                select emp.id as emp_id, 
                period.id as period_id, 
                sign_in.day,
                sign_in.action as in_action, sign_in.name as in_time, sign_out.action out_action, sign_out.name out_time
                from hr_employee emp
                left join 
                    (select name,employee_id,cale_period_id,action,day from hr_attendance where name between %s and %s and action in('sign_in','sign_in_late')) as sign_in
                    on emp.id = sign_in.employee_id
                left join 
                    (select name,employee_id,cale_period_id,action,day from hr_attendance where name between %s and %s and action in('sign_out','sign_out_early')) as sign_out
                    on emp.id = sign_out.employee_id and sign_in.day = sign_out.day and sign_in.cale_period_id = sign_out.cale_period_id
                join resource_calendar_attendance period on sign_in.cale_period_id = period.id and sign_out.cale_period_id = period.id
                where emp.id = ANY(%s)
                '''
        cr.execute(sql,(date_from, date_to, date_from, date_to, (emp_ids,)))
        attends = cr.dictfetchall()
        #use the emp_id-day-period_id as the key to store the normal attendance
#        attends_normal = dict(('%s-%s-%s'%(attend['emp_id'], attend['day'], attend['period_id']), attend) for attend in attends)
        attends_normal = {}
        for attend in attends:
            key = '%s-%s-%s'%(attend['emp_id'], attend['day'], attend['period_id'])
            in_time = fields.datetime.context_timestamp(cr, uid, datetime.strptime(attend['in_time'],DEFAULT_SERVER_DATETIME_FORMAT), context=context)
            out_time = fields.datetime.context_timestamp(cr, uid, datetime.strptime(attend['out_time'],DEFAULT_SERVER_DATETIME_FORMAT), context=context)
            attend['in_time'] = in_time
            attend['out_time'] = out_time
            attends_normal[key] = attend
        
        '''
        2.Loop on by days and employees
        '''
        date_from_local = fields.datetime.context_timestamp(cr, uid, date_from, context)
        date_to_local = fields.datetime.context_timestamp(cr, uid, date_to, context)
        days = rrule.rrule(rrule.DAILY, dtstart=date_from_local,until=date_to_local)
        emps = emp_obj.browse(cr, uid, emp_ids, context)
        seq = 0
        for emp in emps:            
            for day_dt in days:
                day = day_dt.strftime('%Y-%m-%d')
                #if there is no working time defined to employee then continue to next employee directly
                if not emp.calendar_id or not emp.calendar_id.attendance_ids:
                    seq += 1
                    '''
                    init a new empty line by employee/day without period info
                    '''
                    rpt_line = {'seq': seq,
                                    'emp_id': emp.id,
                                    'day': day,
                                    'period_id': None,
                                    'sign_in':None,
                                    'sign_out':None,
                                    'hours_normal':None,
                                    'hours_ot':None,
                                    'is_late':False,
                                    'is_early':False,
                                    'is_absent':False, 
                                    'hours_normal2':None,
                                    'hours_ot2':None,}
                    rpt_lns.append(rpt_line)
                    continue
                for period in emp.calendar_id.attendance_ids:
                    if day_dt.isoweekday() != (int(period.dayofweek) + 1):
                        continue
                    '''
                    init a new empty line by employee/day/period
                    '''
                    seq += 1
                    rpt_line = {'seq': seq,
                                    'emp_id': emp.id,
                                    'day': day,
                                    'period_id': period.id,
                                    'sign_in':None,
                                    'sign_out':None,
                                    'hours_normal':None,
                                    'hours_ot':None,
                                    'is_late':False,
                                    'is_early':False,
                                    'is_absent':False, 
                                    'hours_normal2':None,
                                    'hours_ot2':None,}
                    rpt_lns.append(rpt_line)
                    #find the normal attendance by employee/day/period
                    attend_key = '%s-%s-%s'%(emp.id, day, period.id)
                    attend = attends_normal.get(attend_key, False)                    
                    if attend:
                        #found the normal attendance, with sign in and out record, put the data directly
                        hour_in = attend['in_time'].hour + attend['in_time'].minute/60.0
                        hour_out = attend['out_time'].hour + attend['out_time'].minute/60.0
                        hours_valid = hour_out - hour_in - period.hours_non_work
                        attend_hours = self._attend_hours(hours_valid, period)                            
                        rpt_line.update({'period_id':period.id, 
                                            'sign_in':hour_in,
                                            'sign_out':hour_out,
                                            'hours_normal':attend_hours[0],
                                            'hours_ot':attend_hours[1],
                                            'is_late':attend['in_action']=='sign_in_late',
                                            'is_early':attend['out_action']=='sign_out_early',
                                            'hours_normal2':attend_hours[2],
                                            'hours_ot2':attend_hours[3],
                                            })
                        continue
                    #the abnormal attendance, with sign in or out record only, or without any attendance
                    attend_ids = attend_obj.search(cr, uid, [('employee_id','=',emp.id),('day','=',day),('cale_period_id','=',period.id), 
                                                    ('action','in',('sign_in','sign_in_late','sign_out','sign_out_early'))], context=context)
                    if attend_ids:
                        #found sign in or sign out data, there shoule be only one record, so use the first ID to get data
                        attend = attend_obj.browse(cr, uid, attend_ids[0], context=context)
                        attend_time = fields.datetime.context_timestamp(cr, uid, datetime.strptime(attend.name,DEFAULT_SERVER_DATETIME_FORMAT), context)
                        hour_in = None
                        hour_out = None
                        hours_valid = None
                        hours_normal = None
                        hours_ot = None
                        is_late = False
                        is_early = False
                        is_absent = False    
                        hours_normal2 = None
                        hours_ot2 = None                                            
                        #Only have sign in record
                        if attend.action in ('sign_in','sign_in_late'):
                            hour_in = attend_time.hour + attend_time.minute/60.0
                            if emp.calendar_id.no_out_option == 'early':
                                #treat as leave early
                                if not period.is_full_ot:
                                    is_early = True
                                hours_valid = period.hour_to - hour_in -  period.hours_non_work - emp.calendar_id.no_out_time/60.0
                            else:
                                #treat as absent
                                if not period.is_full_ot:
                                    is_absent = True
                                hours_valid = 0.0
                        #Only have sign out record
                        if attend.action in ('sign_out','sign_out_early'):
                            hour_out = attend_time.hour + attend_time.minute/60.0
                            if emp.calendar_id.no_in_option == 'late':
                                #treat as leave early
                                if not period.is_full_ot:
                                    is_late = True
                                hours_valid = hour_out - period.hour_from - period.hours_non_work - emp.calendar_id.no_in_time/60.0
                            else:
                                #treat as absent
                                if not period.is_full_ot:
                                    is_absent = True
                                hours_valid = 0.0
                        if hours_valid:
                            hours_normal, hours_ot, hours_normal2, hours_ot2 = self._attend_hours(hours_valid, period)
                            
                        rpt_line.update({'period_id':period.id, 
                                            'sign_in':hour_in,
                                            'sign_out':hour_out,
                                            'hours_normal':hours_normal,
                                            'hours_ot':hours_ot,
                                            'is_late':is_late,
                                            'is_early':is_early,
                                            'is_absent':is_absent,
                                            'hours_normal2':hours_normal2,
                                            'hours_ot2':hours_ot2,
                                            })
                    else:
                        if not period.is_full_ot:
                            rpt_line.update({'is_absent':True})
        '''========return data to rpt_base.run_report()========='''    
        return self.pool.get('hr.rpt.attend.emp.day.line'), rpt_lns
    
    def _pdf_data(self, cr, uid, ids, form_data, context=None):
        return {'xmlrpt_name': 'hr.rpt.attend.emp.day'}
    
hr_rpt_attend_emp_day()

class hr_rpt_attend_emp_day_line(osv.osv_memory):
    _name = "hr.rpt.attend.emp.day.line"
    _inherit = "rpt.base.line"
    _description = "HR Attendance Employee Day Report Lines"
    _columns = {
        'rpt_id': fields.many2one('hr.rpt.attend.emp.day', 'Report'),
        'seq': fields.integer('Sequence',),
        'emp_id': fields.many2one('hr.employee', 'Employee',),
        'emp_code': fields.related('emp_id','emp_code',string='Code', type='char'),
        'emp_name': fields.related('emp_id','name',string='Name', type='char'),
        
        'day': fields.char('Day', store=True, size=32),
        'period_id': fields.many2one('resource.calendar.attendance','Period'),
        'p_weekday': fields.related('period_id','dayofweek',type='selection',
                                    selection=[('0','Monday'),('1','Tuesday'),('2','Wednesday'),('3','Thursday'),('4','Friday'),('5','Saturday'),('6','Sunday')],
                                    string='Day of Week'),        
        'p_hour_from': fields.related('period_id','hour_from',type='float',string='From'),
        'p_hour_to': fields.related('period_id','hour_to',type='float',string='To'),
        'p_hours_normal': fields.related('period_id','hours_work_normal',type='float',string='Normal'),
        'p_hour_ot': fields.related('period_id','hours_work_ot',type='float',string='OT'),
        
        'sign_in':fields.float('Sign In'),
        'sign_out':fields.float('Sign Out'),
        #the hours that working normal in fact
        'hours_normal':fields.float('Work Normal'),
        #the hours that working OT in fact
        'hours_ot':fields.float('Work OT'),
        'is_late':fields.boolean('Be Late'),
        'is_early':fields.boolean('Leave Early'),
        'is_absent':fields.boolean('Absenteeism'),
        #the hours that working normal2 in fact
        'hours_normal2':fields.float('Work Normal2'),
        #the hours that working OT2 in fact
        'hours_ot2':fields.float('Work OT2'),
    }

hr_rpt_attend_emp_day_line()

from openerp.report import report_sxw
from openerp.addons.metro.rml import rml_parser_ext
report_sxw.report_sxw('report.hr.rpt.attend.emp.day', 'hr.rpt.attend.emp.day', 'addons/metro_hr/wizard/hr_rpt_attend_emp_day.rml', parser=rml_parser_ext, header='internal')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
