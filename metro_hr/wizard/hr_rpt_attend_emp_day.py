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
from dateutil import relativedelta
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.misc import DEFAULT_SERVER_DATE_FORMAT
from openerp.addons.metro import utils

from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
'''
Attendance report by employee and day, working period
'''
class hr_rpt_attend_emp_day(osv.osv):
    _name = "hr.rpt.attend.emp.day"
    _description = "HR Attendance Employee Daily Report"    
    _order = 'id desc'
    _columns = {
        'name': fields.char('Report Name', size=32, required=False),
        'title': fields.char('Report Title', required=False),
        'type': fields.char('Report Type', size=16, required=True),
        'company_id': fields.many2one('res.company','Company',required=True),
        
        #report data lines
        'rpt_lines': fields.one2many('hr.rpt.attend.emp.day.line', 'rpt_id', string='Report Line'),
        'date_from': fields.datetime("Start Date", required=True),
        'date_to': fields.datetime("End Date", required=True),
        'emp_ids': fields.many2many('hr.employee', string='Selected Employees'),
        
        'state': fields.selection([
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('cancel', 'Cancel'),
        ], 'Status', select=True, readonly=True, track_visibility='onchange'),        
    
        'note': fields.text('Description', readonly=False, states={'done':[('readonly',True)]}),
        'attend_month_ids': fields.one2many('hr.rpt.attend.month', 'attend_day_id', string='Attendances Monthly', readonly=True),
        }

    _defaults = {
        'type': 'attend_emp_day',     
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.rptcn', context=c),
        'state': 'draft',  
    }
    
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default['attend_month_ids'] = None
        default['rpt_lines'] = None
        return super(hr_rpt_attend_emp_day, self).copy(cr, uid, id, default, context)
        
    def default_get(self, cr, uid, fields, context=None):
        vals = super(hr_rpt_attend_emp_day, self).default_get(cr, uid, fields, context=context)
        if 'date_from' in fields:
            #For the datetime value in defaults, need convert the local time to UTC, the web framework will convert them back to local time on GUI
            date_from =datetime.strptime(time.strftime('%Y-%m-01 00:00:00'), '%Y-%m-%d %H:%M:%S')
            date_from_utc = utils.utc_timestamp(cr, uid, date_from, context)
            vals.update({'date_from':date_from_utc.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                         
        if 'date_to' in fields:
            date_to = datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1)
            date_to = datetime.strptime(date_to.strftime('%Y-%m-%d 23:59:59'), '%Y-%m-%d %H:%M:%S')        
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
        return "Attendance Employee Daily Report"
            
    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        if isinstance(ids,(int,long)):
            ids = [ids]
        res = []
        for row in self.read(cr, uid, ids, ['name'], context=context):
            res.append((row['id'],'[%s]%s'%(row['id'],row['name']) ))
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
        if 'name' not in vals or not vals['name']:
            date_to = vals['date_to']
            if date_to and len(date_to) == 10:
                date_to = vals['date_to'] + ' 00:00:00'
            date_to = datetime.strptime(date_to, DEFAULT_SERVER_DATETIME_FORMAT)
            name = '%s-%s'%(date_to.year, date_to.month)
            vals['name'] = name
        self._convert_save_dates(cr, uid, vals, context)
        id_new = super(hr_rpt_attend_emp_day, self).create(cr, uid, vals, context=context)
        return id_new
    
    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self._convert_save_dates(cr, uid, vals, context)
        old_emp_ids = []
        if 'emp_ids' in vals:
            old_emp_ids = self.read(cr, uid, ids[0], ['emp_ids'],context=context)['emp_ids']
        resu = super(hr_rpt_attend_emp_day, self).write(cr, uid, ids, vals, context=context)
        new_emp_ids = self.read(cr, uid, ids[0], ['emp_ids'],context=context)['emp_ids']
        if old_emp_ids: 
            del_emp_ids = []
            if new_emp_ids:
                for emp_id in old_emp_ids:
                    if not emp_id in new_emp_ids:
                        del_emp_ids.append(emp_id)
            else:
                del_emp_ids = old_emp_ids
            #unlink report line of deleted employees 
            if del_emp_ids:
                rpt_line_obj = self.pool.get('hr.rpt.attend.emp.day.line')
                unlink_line_ids = rpt_line_obj.search(cr, uid, [('rpt_id','=',ids[0]),('emp_id','in',del_emp_ids)])
                rpt_line_obj.unlink(cr, uid, unlink_line_ids, context=context)
            
        return resu
    
    def unlink(self, cr, uid, ids, context=None):
        for rpt in self.read(cr, uid, ids, ['state'], context=context):
            if rpt['state'] not in ('draft','cancel'):
                raise osv.except_osv(_('Error'),_('Only order with Draft/Cancel state can be delete!'))
        return super(hr_rpt_attend_emp_day, self).unlink(cr, uid, ids, context=context)
    
    def action_confirm(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'confirmed'})
        return True

    def action_cancel_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'draft'})
        return True
    
    def action_cancel(self, cr, uid, ids, context=None):
        for rpt in self.browse(cr, uid, ids, context=context):
            if rpt.attend_month_ids:
                for attend_month in rpt.attend_month_ids:
                    if attend_month.state != 'cancel':
                        raise osv.except_osv(_('Error!'),_('There are related monthly attendance report, please cancel or delete them first!'))
                            
        self.write(cr, uid, ids, {'state':'cancel'})
        return True
            
    #generate a new monthly report
    def new_attend_month(self, cr, uid, ids, context=None):
        rpt_id = ids[0]
        #read daily report data, create new monthly report based on it.
        rpt = self.browse(cr, uid, rpt_id, context=context)
        rpt_month_obj = self.pool.get('hr.rpt.attend.month')        
        vals = {'date_from':rpt.date_from, 
                        'date_to':rpt.date_to, 
                        'emp_ids':[(4,emp.id) for emp in rpt.emp_ids],
                        'company_id':rpt.company_id.id,
                        'attend_day_id':rpt.id}
        rpt_month_id = rpt_month_obj.create(cr, uid, vals, context=context)
        #generate report
        rpt_month_obj.run_report(cr, uid, [rpt_month_id], context=context)
        #go to the attendances monthly report view page
        form_view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_hr', 'hr_rpt_attend_month_view')
        form_view_id = form_view and form_view[1] or False
        return {
            'name': _('Attendances Monthly Report'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [form_view_id],
            'res_model': 'hr.rpt.attend.month',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': rpt_month_id,
        }

    #view monthly report
    def view_attend_month(self, cr, uid, ids, context=None):
        rpt_id = ids[0]
        #read daily report data, create new monthly report based on it.
        rpt = self.read(cr, uid, rpt_id, ['attend_month_ids'], context=context)
        rpt_month_ids = rpt['attend_month_ids']
        if not rpt_month_ids:
            raise osv.except_osv(_('Error!'),_('No monthly attendance report generated!'))
        if len(rpt_month_ids) > 1:
            #got to list page
            act_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_hr', 'hr_rpt_attend_month_action')
            act_id = act_id and act_id[1] or False            
            act_win = self.pool.get('ir.actions.act_window').read(cr, uid, act_id, [], context=context)
            act_win['context'] = {'search_default_attend_day_id': rpt['id']}
            return act_win
        else:
            #go to form page
            form_view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_hr', 'hr_rpt_attend_month_view')
            form_view_id = form_view and form_view[1] or False
            return {
                'name': _('Attendances Monthly Report'),
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [form_view_id],
                'res_model': 'hr.rpt.attend.month',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': rpt_month_ids[0],
            }
                        
    def _attend_hours(self, hours_valid, period):
        
        if hours_valid+0.5 >= period.hours_work_normal:
            hours_normal = period.hours_work_normal
        else:         
            hours_normal = hours_valid
                                              
        hours_ot = hours_valid - hours_normal
        if hours_ot+0.5 >= period.hours_work_ot:
            hours_ot = period.hours_work_ot
                
        #the second time group                        
        if hours_valid+0.5 >= period.hours_work_normal2:
            hours_normal2 = period.hours_work_normal2
        else:
            hours_normal2 = hours_valid
               
        hours_ot2 = hours_valid - hours_normal2
        if hours_ot2+0.5 >= period.hours_work_ot2:
            hours_ot2 = period.hours_work_ot2
            
        return hours_normal, hours_ot, hours_normal2, hours_ot2
        
    def run_report(self, cr, uid, ids, context=None, emp_ids=None):
        rpt = self.browse(cr, uid, ids, context=context)[0]
        if not rpt.emp_ids:
            raise osv.except_osv(_('Warning!'),_('Please select employees to get attendance!'))
        rpt_method = getattr(self, 'run_%s'%(rpt.type,))
        #get report data
        rpt_line_obj,  rpt_lns = rpt_method(cr, uid, ids, context, emp_ids=emp_ids)        
        #remove the old lines
        unlink_domain = [('rpt_id','=',rpt.id)]
        if emp_ids:
            unlink_domain.append(('emp_id','in',emp_ids))
        unlink_ids = rpt_line_obj.search(cr, uid, unlink_domain, context=context)
        rpt_line_obj.unlink(cr ,uid, unlink_ids, context=context)
        #create new lines
        for rpt_line in rpt_lns:
            rpt_line['rpt_id'] = rpt.id
            rpt_line_obj.create(cr ,uid, rpt_line, context=context)  
        #update GUI elements
        self.write(cr, uid, rpt.id, {'show_search':False,'show_result':True,'save_pdf':True},context=context)
        #go to the attendances line view page
        form_view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_hr', 'view_hr_rpt_attend_emp_day_line_tree')
        form_view_id = form_view and form_view[1] or False
        return {
            'name': _('Attendances Daily Report Line'),
            'view_type': 'form',
            'view_mode': 'tree',
            'view_id': [form_view_id],
            'res_model': 'hr.rpt.attend.emp.day.line',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'domain': [('rpt_id','=',ids[0])],
            #'context': {'search_default_groupby_emp':True},
        }
                
        return True
        
    def run_attend_emp_day(self, cr, uid, ids, context=None, emp_ids=None):
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
        if not emp_ids:
            emp_ids = [emp.id for emp in rpt.emp_ids]
            if not emp_ids:
                emp_ids = emp_obj.search(cr, uid, [], context=context)
        #sort the employee ids
        emp_ids.sort()
        
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
                emp_cale = emp_obj.get_wt(cr, uid, emp.id, day_dt, context=context)
                day = day_dt.strftime('%Y-%m-%d')
                #if there is no working time defined to employee then continue to next employee directly
                if not emp_cale or not emp_cale.attendance_ids:
                    seq += 1
                    '''
                    init a new empty line by employee/day without period info
                    '''
                    rpt_line = {'seq': seq,
                                    'emp_id': emp.id,
                                    'day': day_dt,
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
                for period in emp_cale.attendance_ids:
                    if day_dt.isoweekday() != (int(period.dayofweek) + 1):
                        continue
                    '''
                    init a new empty line by employee/day/period
                    '''
                    seq += 1
                    rpt_line = {'seq': seq,
                                    'emp_id': emp.id,
                                    'day': day_dt,
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
                            if emp_cale.no_out_option == 'early':
                                #treat as leave early
                                if not period.is_full_ot:
                                    is_early = True
                                hours_valid = period.hour_to - hour_in -  period.hours_non_work - emp_cale.no_out_time/60.0
                            else:
                                #treat as absent
                                if not period.is_full_ot:
                                    is_absent = True
                                hours_valid = 0.0
                        #Only have sign out record
                        if attend.action in ('sign_out','sign_out_early'):
                            hour_out = attend_time.hour + attend_time.minute/60.0
                            if emp_cale.no_in_option == 'late':
                                #treat as leave early
                                if not period.is_full_ot:
                                    is_late = True
                                hours_valid = hour_out - period.hour_from - period.hours_non_work - emp_cale.no_in_time/60.0
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
    
    def save_pdf(self, cr, uid, ids, context=None):
        if context is None: 
            context = {}
        form_data = self.read(cr, uid, ids[0], context=context)
        rptxml_name = self._pdf_data(cr, uid, ids[0], form_data, context=context)['xmlrpt_name']
        datas = {
                 'model': self._name,
                 'ids': [ids[0]],
                 'form': form_data,
        }
        return {'type': 'ir.actions.report.xml', 'report_name': rptxml_name, 'datas': datas, 'nodestroy': True}   
    
    def print_empday_group(self, cr, uid, ids, context=None, rpt_line_ids = None, rpt_emp_ids = None):
        group_ids = []
        #parametr from hr_rpt_attend_month.pdf_attend_emp(), structure:{rpt_day_id:rpt_month_id,...}
        rpt_day_months = context.get("rpt_day_months",{})
        if not rpt_line_ids:
            for rpt_day_id in ids:
                context['attend_month_id'] = rpt_day_months.get(rpt_day_id)
                group_ids.extend(self.gen_empday_group(cr, uid, rpt_day_id, context=context, rpt_line_ids=rpt_line_ids, rpt_emp_ids=rpt_emp_ids))
        else:
            group_ids.extend(self.gen_empday_group(cr, uid, ids, context=context, rpt_line_ids=rpt_line_ids, rpt_emp_ids=rpt_emp_ids))
        #print attendances by group
        if not group_ids:
            return {'type': 'ir.actions.act_window_close'}     
        #return report action
        datas = {'model': 'attend.empday.group','ids': group_ids,}
        context.update({'active_model':'attend.empday.group', 'active_ids':group_ids})
        rpt_action = {'type': 'ir.actions.report.xml', 
                      'report_name': 'attend.empday.group', 
                      'datas': datas, 
                      'nodestroy': True,
                      'context':context}
        return rpt_action
    
    def gen_empday_group(self, cr, uid, rpt_day_id, context=None, rpt_line_ids = None, rpt_emp_ids = None):
        if context is None:
            context = {}
        '''
        store the groups in dict: {key:{
        val1,val2,...,
        #lines:{key:line_data}
        {}
        valn
        }
        }
        '''
        groups = {}
        #store the calendar worktime types in dict:{calendar_id:type_list}
        cale_wt_types = {}
        
        #get the group data       
        rptlines = []
        if not rpt_line_ids:            
            #call from self
            rpt = self.browse(cr, uid, rpt_day_id, context=context)
            rptlines = rpt.rpt_lines
        else:
            #this parameter will be called from hr_rpt_attend_emp_day_line.print_empday_line_group()
            rptlines = self.pool.get('hr.rpt.attend.emp.day.line').browse(cr, uid, rpt_line_ids, context=context)
            rpt = rptlines[0].rpt_id
        #handle the attend month report parameter, from hr_rpt_attend_month.pdf_attend_emp()
        attend_month_id = context.get('attend_month_id', None)
        emp_attend_month_lines = {}
        if attend_month_id:
            attend_month_line_obj = self.pool.get('hr.rpt.attend.month.line')
            attend_month_line_ids = attend_month_line_obj.search(cr, uid, [('rpt_id','=',attend_month_id)],context=context)
            emp_ids = attend_month_line_obj.read(cr, uid, attend_month_line_ids, ['emp_id'])
            emp_attend_month_lines = dict((item['emp_id'][0],item['id']) for item in emp_ids)
        #johnw, 01/30, add employee ids support
        if rpt_emp_ids:
            new_rptlines = []
            for rpt_line in rptlines:
                if rpt_line.emp_id.id in rpt_emp_ids:
                    new_rptlines.append(rpt_line)
            rptlines = new_rptlines
            
            new_emp_attend_month_lines = {}
            for emp_id, month_line_id in emp_attend_month_lines.items():
                if emp_id in rpt_emp_ids:
                    new_emp_attend_month_lines[emp_id] = month_line_id
            emp_attend_month_lines = new_emp_attend_month_lines
            
        for rpt_line in rptlines:
            #if from attend month report, only print the employees in the attendance report
            if attend_month_id and not emp_attend_month_lines.get(rpt_line.emp_id.id):
                continue
            key_group = '[%s]%s'%(rpt_line.emp_id.emp_code, rpt_line.emp_id.name)
            if not groups.get(key_group):
                #Add the attendance data
                #+++ 02/18/2016 - HoangTK : Fix when period is empty
                cale_id = False
                if rpt_line.period_id.calendar_id:
                #cale_id = rpt_line.period_id.calendar_id.id
                    cale_id = rpt_line.period_id.calendar_id.id
                #--- 02/18/2016 - HoangTK : Fix when period is empty
                worktime_types = cale_wt_types.get(cale_id)
                if not worktime_types and cale_id:
                    sql = 'select distinct b.id,b.sequence,b.name \
                        from resource_calendar_attendance a \
                        join hr_worktime_type b on a.type_id = b.id \
                        where a.calendar_id=%s \
                        order by b.sequence'
                    cr.execute(sql, (cale_id,))
                    worktime_types = cr.dictfetchall()
                    cale_wt_types[cale_id] = worktime_types
                #set the group values
                group_vals = {'name':key_group,
                                    'emp_id': rpt_line.emp_id.id,
                                    'date_from': rpt.date_from,
                                    'date_to': rpt.date_to,
                                    'period_type_a_id':(worktime_types and len(worktime_types) >=1) and worktime_types[0]['id'] or None,
                                    'period_type_b_id':(worktime_types and len(worktime_types) >=2) and worktime_types[1]['id'] or None,
                                    'period_type_c_id':(worktime_types and len(worktime_types) >=3) and worktime_types[2]['id'] or None,
                                    'line_ids_dict':{}}
                #add the attend month line link id
                if attend_month_id:
                    group_vals['attend_month_line_id'] = emp_attend_month_lines.get(group_vals['emp_id'])
                groups[key_group] = group_vals
            #append this line
            group_vals = groups.get(key_group)
            #get the group line values in dict
            group_lines = group_vals['line_ids_dict']
            key_group_line = rpt_line.day
            if not group_lines.get(key_group_line):
                group_lines[key_group_line] = {'day':rpt_line.day,'weekday':rpt_line.p_weekday, 'seq':0}
            #add current data
            group_line = group_lines[key_group_line]
            #set the different attendance work time fields by the line data
            if group_vals.get('period_type_a_id') and rpt_line.period_id.type_id.id == group_vals['period_type_a_id']:
                group_line['sign_in_a'] = rpt_line.sign_in
                group_line['sign_out_a'] = rpt_line.sign_out
                group_line['hours_normal_a'] = rpt_line.hours_normal
                group_line['hours_ot_a'] = rpt_line.hours_ot
                group_line['seq'] = rpt_line.seq
                
            if group_vals.get('period_type_b_id') and rpt_line.period_id.type_id.id == group_vals['period_type_b_id']:
                group_line['sign_in_b'] = rpt_line.sign_in
                group_line['sign_out_b'] = rpt_line.sign_out
                group_line['hours_normal_b'] = rpt_line.hours_normal
                group_line['hours_ot_b'] = rpt_line.hours_ot
            if group_vals.get('period_type_c_id') and rpt_line.period_id.type_id.id == group_vals['period_type_c_id']:
                group_line['sign_in_c'] = rpt_line.sign_in
                group_line['sign_out_c'] = rpt_line.sign_out
                group_line['hours_normal_c'] = rpt_line.hours_normal
                group_line['hours_ot_c'] = rpt_line.hours_ot
                
        #sum and create groups data to DB
        group_ids = []
        attend_empday_group_obj = self.pool.get('attend.empday.group')
        group_list  = groups.values()
        group_list.sort(lambda x, y: cmp(x['name'], y['name']))    
        for group in group_list:
            group_lines_list = []
            work_hours = 0
            work_hours_ot = 0
            for line in group['line_ids_dict'].values():
                line['hours_normal_total'] = line.get('hours_normal_a',0) + line.get('hours_normal_b',0) + line.get('hours_normal_c',0)
                line['hours_ot_total'] = line.get('hours_ot_a',0) + line.get('hours_ot_b',0) + line.get('hours_ot_c',0)
                work_hours += line['hours_normal_total']
                work_hours_ot += line['hours_ot_total']
                group_lines_list.append((0,0,line))
            group_lines_list.sort(lambda x, y: cmp(x[2]['seq'], y[2]['seq']))
            group['line_ids'] = group_lines_list
            group['days_attend'] = work_hours/8.0
            group['hours_ot'] = work_hours_ot
            group_ids.append(attend_empday_group_obj.create(cr, uid, group, context=context))
                    
        #return group_ids
        return group_ids    
    
hr_rpt_attend_emp_day()

class attend_empday_group(osv.osv_memory):
    _name = "attend.empday.group"
    _columns = {
        'name': fields.char('Group', size=64, required=True),
        'emp_id': fields.many2one('hr.employee', 'Employee',),
        'date_from': fields.datetime("Start Date", required=True),
        'date_to': fields.datetime("End Date", required=True),
        'line_ids': fields.one2many('attend.empday.group.line','group_id',string='Group Lines'),
        'period_type_a_id': fields.many2one('hr.worktime.type', string='Worktime A'),
        'period_type_b_id': fields.many2one('hr.worktime.type', string='Worktime B'),
        'period_type_c_id': fields.many2one('hr.worktime.type', string='Worktime C'),
        'days_attend':fields.float('Attended Days'),
        'hours_ot':fields.float('Overtime'), 
        'attend_month_line_id':fields.many2one('hr.rpt.attend.month.line', string='Attend Month Line')
    }    
    
    def get_report_name(self, cr, uid, id, rpt_name, context=None):
        return "Attendance Employee Daily Report"
        
class attend_empday_group_line(osv.osv_memory):
    _name = "attend.empday.group.line"
    _columns = {
        'group_id': fields.many2one('attend.empday.group', string='Group'),
        'seq': fields.integer('Sequence'),
        'day': fields.char('Day', store=True, size=32),
        'weekday': fields.selection([('0','Monday'),('1','Tuesday'),('2','Wednesday'),('3','Thursday'),('4','Friday'),('5','Saturday'),('6','Sunday')],string='Day of Week'),                                
                
        'sign_in_a':fields.float('Sign In'),
        'sign_out_a':fields.float('Sign Out'),
        'hours_normal_a':fields.float('Work Normal'),
        'hours_ot_a':fields.float('Work OT'),
        
        'sign_in_b':fields.float('Sign In'),
        'sign_out_b':fields.float('Sign Out'),
        'hours_normal_b':fields.float('Work Normal'),
        'hours_ot_b':fields.float('Work OT'),
        
        'sign_in_c':fields.float('Sign In'),
        'sign_out_c':fields.float('Sign Out'),
        'hours_normal_c':fields.float('Work Normal'),
        'hours_ot_c':fields.float('Work OT'),
        
        
        'hours_normal_total':fields.float('Work Normal'),
        'hours_ot_total':fields.float('Work OT'),                
    } 

class hr_rpt_attend_emp_day_line(osv.osv):
    _name = "hr.rpt.attend.emp.day.line"
    _description = "HR Attendance Employee Daily Report Lines"
    _order = 'seq'
    _columns = {                        
        'rpt_id': fields.many2one('hr.rpt.attend.emp.day', 'Report', select=True, required=True, ondelete='cascade'),
        'seq': fields.integer('Sequence',group_operator='None'),
        'emp_id': fields.many2one('hr.employee', 'Employee',),
        'emp_code': fields.related('emp_id','emp_code',string='Code', type='char',store=True),
        'emp_name': fields.related('emp_id','name',string='Name', type='char'),
        
        #'day': fields.char('Day', store=True, size=32),
        'day': fields.date("Day", required=True),
        'period_id': fields.many2one('resource.calendar.attendance','Period'),
        'p_weekday': fields.related('period_id','dayofweek',type='selection',
                                    selection=[('0','Monday'),('1','Tuesday'),('2','Wednesday'),('3','Thursday'),('4','Friday'),('5','Saturday'),('6','Sunday')],
                                    string='Day of Week'),        
        'p_hour_from': fields.related('period_id','hour_from',type='float',string='From'),
        'p_hour_to': fields.related('period_id','hour_to',type='float',string='To'),
        'p_hours_normal': fields.related('period_id','hours_work_normal',type='float',string='Normal'),
        'p_hour_ot': fields.related('period_id','hours_work_ot',type='float',string='OT'),
        
        'sign_in':fields.float('Sign In',group_operator='None'),
        'sign_out':fields.float('Sign Out',group_operator='None'),
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
        'state': fields.related('rpt_id','state',type='selection',selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('cancel', 'Cancel'),
        ], string = 'Status', readonly=True),        
    
    }
    #called by server action "action_server_hr_empday_line_pdf", to print the employee daily attendance
    def print_empday_line_group(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not ids:
            return False
        return self.pool.get('hr.rpt.attend.emp.day').print_empday_group(cr, uid, [], context=context, rpt_line_ids = ids)
    
hr_rpt_attend_emp_day_line()

from openerp.report import report_sxw
from openerp.addons.metro.rml import rml_parser_ext


class attend_empday_group_print(rml_parser_ext):
    def __init__(self, cr, uid, name, context):
        super(attend_empday_group_print, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'weekday': self.weekday,
        })
    def weekday(self, weekday):
        return int(weekday) + 1
    
report_sxw.report_sxw('report.hr.rpt.attend.emp.day', 'hr.rpt.attend.emp.day', 'addons/metro_hr/wizard/hr_rpt_attend_emp_day.rml', parser=rml_parser_ext, header='internal')
report_sxw.report_sxw('report.attend.empday.group','attend.empday.group','addons/metro_hr/wizard/hr_rpt_attend_emp_day_group.rml',parser=attend_empday_group_print, header='internal')            
'''
Geneate daily attendance wizard, called by button named "run_report_wizard" on the form view
'''
class hr_rpt_attend_emp_day_wizard(osv.osv_memory):
    _name = 'hr.rpt.attend.emp.day.wizard'
    _description = 'Generate daily attendances'
    _columns = {
        'emp_ids' : fields.many2many('hr.employee', string='Selected Employees', required=True),
    }
                        
    def default_get(self, cr, uid, fields, context=None):
        vals = super(hr_rpt_attend_emp_day_wizard, self).default_get(cr, uid, fields, context=context)
        if not vals:
            vals = {}
        #employees
        if context.get('active_model','') == 'hr.rpt.attend.emp.day' and context.get('active_id'):
            emp_ids = self.pool.get('hr.rpt.attend.emp.day').read(cr, uid, context.get('active_id'), ['emp_ids'])['emp_ids']
            vals['emp_ids'] = emp_ids
                                
        return vals
    
    def set_data(self, cr, uid, ids, context=None):
        emp_ids = self.read(cr, uid, ids[0], ['emp_ids'], context=context)['emp_ids']
        if not emp_ids:
            raise osv.except_osv(_('Error'), _('Please select employees!'))
        
        emp_day_obj = self.pool.get('hr.rpt.attend.emp.day')
        emp_day_id = context.get('active_id')
        #add new emp_ids
        old_emp_ids = emp_day_obj.read(cr, uid, emp_day_id, ['emp_ids'], context=context)['emp_ids']
        new_emp_ids = [(4,emp_id) for emp_id in emp_ids if emp_id not in old_emp_ids]
        if new_emp_ids:
            emp_day_obj.write(cr, uid, emp_day_id, {'emp_ids':new_emp_ids}, context=context)
        #generate data for  the selected employees        
        return emp_day_obj.run_report(cr, uid, [emp_day_id], context=context, emp_ids=emp_ids)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
