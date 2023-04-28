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

from openerp.osv import fields, osv
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
        
class hr_clock(osv.osv):
    _name = 'hr.clock'
    _inherit = ['mail.thread']
    _description="HR Attendance Clock"
    _columns = {
        'name': fields.char('Name', size=32,required=True),
        'ip': fields.char('IP Address',required=True),
        'port': fields.integer('Port', size=8,required=True),
        'date_conn_last': fields.datetime('Last date connected', readonly=True),
        'clock_info' : fields.text('Clock Information', readonly=True),
        'datetime_set' : fields.datetime('Set Datetime'),
        'active' : fields.boolean('Active'),
    }
    _defaults={'port':4370, 'active':True}
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Clock name must be unique!'),
    ]
    
    def _attend_create(self, cr, uid, md5_src, data, context=False):
        emp_obj = self.pool.get('hr.employee')
        attendence_obj = self.pool.get('hr.attendance')
        #use the md5 value to check do we need download the data to database
        md5=hashlib.md5(md5_src.encode('utf-8')).hexdigest()
        if not attendence_obj.search(cr, uid, [('clock_log_id','=',md5)],context=context):
            emp_code = emp_obj.search(cr, uid, [('emp_code','=',data['emp_code'])], context=context)
            if not emp_code:
                return False
            emp_id = emp_code[0]
            employee = emp_obj.browse(cr, uid, emp_id, context=context)
            #decide the sign in or out
            action = 'action'
            '''
            #move to download_log() to calculate all new attendance together, to improve the performance.
            '''
            #convert to UTC time
            data['time'] = utils.utc_timestamp(cr, uid, data['time'], context)            
            calendar_id = emp_obj.get_wt(cr, uid, emp_id, data['time'], context=context)
            vals = {'name':data['time'],
                    'employee_id': emp_id,
                    'action': action,  
                    'clock_log_id':md5, 
                    'notes':data['notes'],
                    'clock_id':data['clock_id'],
                    'calendar_id': calendar_id and calendar_id.id or None}
            return attendence_obj.create(cr, uid, vals, context=context)
        else:
            return 0
        
    def _clock_download_log(self, cr, uid, clock_id, clock, emp_codes = False, context=False):  
        _logger = logging.getLogger(__name__)
        devid = 1
        log_cnt = 0
        new_attend_ids = []
        verify_modes = {0:'Password',1:'Finger',2:'IC Card'}
        inout_modes = {0:'Check-In',1:'Check-Out',2:'Break-Out',3:'Break-In',4:'OT-In',5:'OT-Out'}
        serial_no = clock.GetSerialNumber(devid,None)  
        if serial_no[0]:  
            serial_no = serial_no[1]
        else:
            serial_no = '1'
        if clock.ReadGeneralLogData(devid):
            _logger.info('#########download clock log begin at %s##########'%(datetime.now()))
            while True:  
                s= clock.SSR_GetGeneralLogData(devid)  
                if s[0]:  
                    #(True, u'118', 1, 0, 2014, 7, 15, 12, 1, 51, 0)
                    emp_code = '%03d'%(long(s[1]),)
                    if emp_codes and emp_code not in emp_codes:
                        continue
                    v_mode = verify_modes[s[2]]
                    io_mode = inout_modes[s[3]]
                    log_date = datetime.strptime('%s-%s-%s %s:%s:%s'%s[4:10], '%Y-%m-%d %H:%M:%S')
#                    print 'Emp Code:%s  VerifyMode:%s InOutMode:%s DateTime:%s WorkCode:%s' %(emp_code, v_mode, io_mode, log_date, s[10])
                    #the md5 source to gen md5
                    md5_src = '%s%s%s%s%s%s%s%s%s%s'%s[1:]
                    attend_data = {'emp_code':emp_code, 'notes':'%s by %s'%(io_mode,v_mode), 'time':log_date, 'clock_id':clock_id}                    
                    new_id = self._attend_create(cr, uid, md5_src, attend_data, context=context)
                    if new_id > 0:
                        new_attend_ids.append(new_id)
                    log_cnt += 1
                else:  
                    break  
            _logger.info('#########download clock log end at %s, log count:%s##########'%(datetime.now(), log_cnt))
        return log_cnt, new_attend_ids
            
    def download_log(self, cr, uid, ids = False, context=False, emp_ids=False):
        if not context:
            context = {}
        if not ids:
            ids = self.search(cr, uid, [], context=context)
        emp_codes = []
        #get the emps by ids
        if emp_ids:
            emps = self.pool.get('hr.employee').read(cr, uid, emp_ids, ['emp_code'], context=context)
            emp_codes = [emp['emp_code'] for emp in emps]
            if not emp_codes:
                return False
            
        clock = clock_util.clock_obj()
        run_log = ''
        for clock_data in self.browse(cr, uid, ids, context=context):
            try:     
                #connect clock
                clock_util.clock_connect(clock, clock_data.ip,clock_data.port)
                #download data
                log_cnt, attend_ids = self._clock_download_log(cr, uid, clock_data.id, clock, emp_codes = emp_codes, context=context)
                #do the attendance action calculation
                if attend_ids:
                    self.pool.get('hr.attendance').calc_action(cr, uid, attend_ids, context=context)
                #if download the whole clock data, then log the message
                if not emp_codes:
                    #calling from cron or the clock GUI
                    msg = u'download clock[%s] log end at %s, log count:%s, new log count:%s'%(clock_data.name,datetime.now(), log_cnt, len(attend_ids))
                    run_log += msg + "\n"
                    self.message_post(cr, uid, clock_data.id, 
                                      type='comment', subtype='mail.mt_comment', 
                                      subject='download log data', 
                                      body=msg,
                                      content_subtype="plaintext",
                                      context=context)
                #disconnect clock
                clock_util.clock_disconnect(clock)
            except Exception,e:
                traceback.print_exc() 
                formatted_info = "".join(traceback.format_exception(*(sys.exc_info())))
                msg = 'download clock[%s] with exception at %s'%(clock_data.name, datetime.now()) + "\n" + formatted_info
                run_log += msg + "\n"
                self.message_post(cr, uid, clock_data.id, 
                                  type='comment', subtype='mail.mt_comment', 
                                  subject='download log data', 
                                  body=msg,
                                  content_subtype="plaintext",
                                  context=context)
        return run_log
    
    
    def refresh_clock_info(self, cr, uid, ids, context=None):  
        clock = clock_util.clock_obj()
        for clock_data in self.browse(cr, uid, ids, context=context):
            #connect clock
            clock_util.clock_connect(clock, clock_data.ip,clock_data.port)
            #download data
            clock_info = clock_util.clock_status(clock)
            #disconnect clock
            clock_util.clock_disconnect(clock)
            #update data
            self.write(cr, uid, clock_data.id, {'clock_info':clock_info},context=context)
            
        return True
    
    def set_clock_time(self, cr, uid, ids, clock_time = None, context=None):  
        clock = clock_util.clock_obj()
        for clock_data in self.browse(cr, uid, ids, context=context):
            #connect clock
            clock_util.clock_connect(clock, clock_data.ip,clock_data.port)
            #set clock time
            if not clock_time:
                clock_time = fields.datetime.context_timestamp(cr, uid, datetime.utcnow(), context)
            clock_util.clock_time_set(clock,clock_time)
            #refresh data including time
            clock_info = clock_util.clock_status(clock)
            #disconnect clock
            clock_util.clock_disconnect(clock)
            #update data
            self.write(cr, uid, clock_data.id, {'clock_info':clock_info},context=context)
        return True
    
    def write(self, cr, uid, ids, vals, context=None):
        resu = super(hr_clock,self).write(cr, uid, ids ,vals, context=context)
        if 'datetime_set' in vals:
            #the 'datetime_set' in vals is UTC time, so convert it to user's time zone time.
            clock_time = fields.datetime.context_timestamp(cr, uid, datetime.strptime(vals['datetime_set'],DEFAULT_SERVER_DATETIME_FORMAT), context)
            self.set_clock_time(cr, uid, ids, clock_time, context)
        return resu
    
class hr_employee(osv.osv):
    _inherit = "hr.employee"

    _columns = {
        #普通/登记员/管理员, 后两者可以进入考勤机的管理界面
        'clock_role':fields.selection([('0','User'),('1','Operator'),('3','Manager')],string='Clock Role'),
        #clock passwor max size is 8
        'clock_pwd':fields.char('Clock Password',size=8),
        'clock_fp1':fields.text('Finger Print1', readonly=False),
        'clock_fp2':fields.text('Finger Print2', readonly=False),
        'clock_fp3':fields.text('Finger Print3', readonly=False),
        'clock_fp4':fields.text('Finger Print4', readonly=False),
        'clock_fp5':fields.text('Finger Print5', readonly=False),
        
        'clock_fp6':fields.text('Finger Print6', readonly=False),        
        'clock_fp7':fields.text('Finger Print7', readonly=False),
        'clock_fp8':fields.text('Finger Print8', readonly=False),
        'clock_fp9':fields.text('Finger Print9', readonly=False),
        'clock_fp10':fields.text('Finger Print10', readonly=False),
    } 
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
