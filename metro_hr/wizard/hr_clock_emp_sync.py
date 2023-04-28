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

from openerp import netsvc
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp.osv import osv,fields
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP

from openerp.addons.metro_hr  import hr_clock_util as clock_util
#below does not work
#import openerp.addons.metro_hr.hr_clock_util as clock_util

class hr_clock_emp_sync_emp(osv.osv_memory):
    _name = "hr.clock.emp.sync.emp"
    _columns = {
        'order_id' : fields.many2one('hr.clock.emp.sync', string="Sync Order"),
        'emp_code': fields.char('Code', size=16),
        'emp_name' : fields.char("Name", size=64, required=True),
        'emp_card_id': fields.char('Employee Card ID', size=16),
        'clock_role':fields.selection([('0','User'),('1','Operator'),('3','Manager')],string='Clock Role'),
        'emp_pos':fields.selection([('server','On Servers'),('clock','On Clocks'),('sync','To Sync'),('clock_all','Clock All')],string='Action'),
        'target_state':fields.selection([('exist','Exist'),('miss','Missing'),('diff','Exist with Difference'),('to_delete','to delete')],string='Data state of Base Info on target'),
    }       

class hr_clock_emp_sync(osv.osv_memory):
    _name = 'hr.clock.emp.sync'
    _description = 'Sync Clock Employee'
    _columns = {
        'clock_id' : fields.many2one('hr.clock','Clock to Sync', required=True),
        'sync_direction' : fields.selection([('server2clock','Server to Clock'),('clock2server','Clock to Servr'),('user2delete','Delete Users')],string='Sync Direction', required=True),
        'emp_ids_server' : fields.many2many('hr.employee', string='Employees on Server', ),
#        'emp_ids_clock' : fields.one2many('hr.clock.emp.sync.emp', 'order_id', 'Clock Employees', domain=[('emp_pos','=','clock')]),
        'emp_ids_clock' : fields.many2many('hr.clock.emp.sync.emp', string='Clock Employees', ),
        'emp_ids_sync' : fields.one2many('hr.clock.emp.sync.emp', 'order_id', 'Employees to Sync', domain=[('emp_pos','=','sync')]),
        'sync_opt_base' : fields.boolean('Base Info'),
        'sync_opt_fp' : fields.boolean('Finger Print'),
        'sync_opt_pwd' : fields.boolean('Password'),
        'step_no' : fields.selection([('clock','Select Clock'),('employee','Select Employee'),('sync','Do Sync')],string='Wizard Step'),
    }
    
    _defaults = {'sync_opt_base':True, 'step_no':'clock'}       
    
    def default_get(self, cr, uid, fields, context=None):
        """
         To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary with default values for all field in ``fields``
        """
        vals = super(hr_clock_emp_sync, self).default_get(cr, uid, fields, context=context)
        if not vals:
            vals = {}
        #from clock id
        if context.get('active_model','') == 'hr.clock' and context.get('active_id'):
            clock_id = context.get('active_id')
            vals['clock_id'] = clock_id        #clock id
        #from employees selection
        if context.get('active_model','') == 'hr.employee' and context.get('active_ids'):
            vals['emp_ids_server'] = context.get('active_ids')
        return vals
    
    def do_exec(self, cr, uid, ids, context=None):
        order_data = self.browse(cr, uid, ids[0], context=context)
        #no emps need to sync or no data options selected, will return direct
        if not order_data.emp_ids_sync \
            or (not order_data.sync_opt_base and not order_data.sync_opt_fp and not order_data.sync_opt_pwd) :
            return True
        if order_data.sync_direction == 'server2clock':
            self.clock_emps_set(cr, uid, order_data, context)
        if order_data.sync_direction == 'clock2server':
            self.server_emps_set(cr, uid, order_data, context)
        if order_data.sync_direction == 'user2delete':
            self.clock_emps_delete(cr, uid, order_data, context)
        
    def clock_emps_set(self, cr, uid, order_data, context=None):
        if not order_data:
            return False
        #store the password and finger print to update
        emps_fp_pwd = {}
        if order_data.sync_opt_pwd or order_data.sync_opt_fp:
            emp_codes = [emp.emp_code for emp in  order_data.emp_ids_sync]
            emp_obj = self.pool.get('hr.employee')
            emp_ids = emp_obj.search(cr, uid, [('emp_code','in',emp_codes)],context=context)
            read_flds = ['emp_code']
            if order_data.sync_opt_pwd:
                read_flds += ['clock_pwd']
            if order_data.sync_opt_fp:
                read_flds += ['clock_fp1','clock_fp2','clock_fp3','clock_fp4','clock_fp5','clock_fp6','clock_fp7','clock_fp8','clock_fp9','clock_fp10',]
            emps = emp_obj.read(cr, uid, emp_ids, read_flds, context=context)
            for emp in emps:
                emps_fp_pwd[emp['emp_code']] = emp
        #update data to clock
        clock = clock_util.clock_obj()
        clock_util.clock_connect(clock, order_data.clock_id.ip, order_data.clock_id.port)
        for emp_sync in order_data.emp_ids_sync:
            new_clock_pwd = False
            new_clock_fps = []
            if order_data.sync_opt_pwd or order_data.sync_opt_fp:
                fp_pwd = emps_fp_pwd[emp_sync.emp_code]
                if order_data.sync_opt_pwd:
                    new_clock_pwd += fp_pwd['clock_pwd']
                if order_data.sync_opt_fp:
                    for i in range(1,11):
                        new_clock_fps.append(fp_pwd['clock_fp%s'%(i,)])
            #set clock user data
            clock_util.clock_user_set(clock, emp_sync, order_data.sync_opt_pwd, new_clock_pwd, order_data.sync_opt_fp, new_clock_fps)
        #disconnect clock
        clock.RefreshData(1)
        clock_util.clock_disconnect(clock)
                
        return True
        
    def clock_emps_delete(self, cr, uid, order_data, context=None):
        if not order_data:
            return False
        self.clock_emps_delete_exec(cr, uid, [order_data.clock_id], order_data.emp_ids_sync, context=context)
        return True
        
    def clock_emps_delete_exec(self, cr, uid, clock_ids, emp_ids, context=None):
        '''
        Accept the clock_ids and emp_ids parameter to delete on hr clock machine
        @param clock_ids: the list that contains the clock id of int/long or browse_record
        @param emp_ids: the list that contains employee id of int/long or browse_record that will be delte, the   
        '''
        if not clock_ids or not emp_ids:
            return False
        for clock_id in clock_ids:
            if isinstance(clock_id, (int,long)):
                clock_id = self.pool.get('hr.clock').browse(cr, uid, clock_id, context=context)
            #update data to clock
            clock = clock_util.clock_obj()
            clock_util.clock_connect(clock, clock_id.ip, clock_id.port)
            for emp_id in emp_ids:
                if isinstance(emp_id,(int,long)):
                    emp_id = self.pool.get('hr.employee').browse(cr, uid, emp_id, context=context)
                #delete all clock user data, including base info, finger print, password
                clock_util.clock_user_delete(clock, emp_id.emp_code)
            #disconnect clock
            clock.RefreshData(1)
            clock_util.clock_disconnect(clock)
        return True
            
    def server_emps_set(self, cr, uid, order_data, context=None):
        if not order_data:
            return False
        if context is None:
            context = {}
        #store the password and finger print to update
        emps_fp_pwd = []
        if order_data.sync_opt_pwd or order_data.sync_opt_fp:
            emp_codes = [emp.emp_code for emp in  order_data.emp_ids_sync]
            emps_fp_pwd = self.clock_emps_get(cr, uid, order_data.clock_id.id, emp_codes, 
                                              ret_dict = True, 
                                              pwd = order_data.sync_opt_pwd, 
                                              finger_print = order_data.sync_opt_fp, 
                                              context=context)

        emp_obj = self.pool.get('hr.employee')        
        #get the emp id and code dict
        emp_codes = [emp.emp_code for emp in order_data.emp_ids_sync]
        ctx_emp = context.copy()
        ctx_emp['active_test'] = False
        emp_ids = emp_obj.search(cr, uid, [('emp_code','in',emp_codes)],context=ctx_emp)
        emps = emp_obj.read(cr, uid, emp_ids, ['emp_code'], context=context)
        emp_code_ids = {}
        for emp in emps:
            emp_code_ids[emp['emp_code']] = emp['id']
            
        #update data to server   
        emp_ids = []         
        for emp_sync in order_data.emp_ids_sync:
            emp_vals = {}
            if order_data.sync_opt_base:
                emp_vals.update({'name':emp_sync.emp_name, 
                            'emp_card_id':emp_sync.emp_card_id,
                            'clock_role':emp_sync.clock_role})
            if order_data.sync_opt_pwd:
                clock_pwd = emps_fp_pwd[emp_sync.emp_code]['clock_pwd']
                emp_vals['clock_pwd'] = clock_pwd
            if order_data.sync_opt_fp:
                for i in range(1, 11):
                    fld_name = 'clock_fp%s'%(i,)
                    clock_fp = emps_fp_pwd[emp_sync.emp_code].get(fld_name)
                    if clock_fp:
                        emp_vals[fld_name] = clock_fp
            emp_id = emp_code_ids.get(emp_sync.emp_code)
            if emp_id:
                emp_obj.write(cr, uid, emp_id, emp_vals, context=context)
            else:
                if not order_data.sync_opt_base:
                    emp_vals.update({'name':emp_sync.emp_name, 
                                'emp_card_id':emp_sync.emp_card_id,
                                'clock_role':emp_sync.clock_role})
                emp_vals['emp_code'] = emp_sync.emp_code
                emp_id = emp_obj.create(cr, uid, emp_vals, context=context)
            emp_ids.append(emp_id)
                
        return True
        
    def step_prev(self, cr, uid, ids, action, context=None):
        return self.step_change(cr, uid, ids, 'prev', context)
    def step_next(self, cr, uid, ids, action, context=None):
        return self.step_change(cr, uid, ids, 'next', context)            
    def step_change(self, cr, uid, ids, action, context=None):
        if context is None:
            context = {}
        order_data = self.browse(cr, uid, ids[0], context=context)
        new_vals = {}
        #steps definition
        steps = ('clock','employee','sync')
        step_begin_idx = 0
        step_end_idx = len(steps)-1
        #step current
        step_cur = order_data.step_no
        step_cur_idx = 0
        try:
            step_cur_idx = steps.index(step_cur)
        except Exception:
            pass
        #valid current step data:
        if step_cur == 'employee' \
            and order_data.sync_direction == 'server2clock' \
            and not order_data.emp_ids_server:
            raise osv.except_osv(_('Error!'), _('Please select the employees to sync.'))
        if step_cur == 'employee' \
            and order_data.sync_direction == 'clock2server' \
            and not order_data.emp_ids_clock:
            raise osv.except_osv(_('Error!'), _('Please select the employees to sync.'))
        #get the changed step index
        if action == 'next':
            step_new_idx = (step_cur_idx+1) > step_end_idx and step_end_idx or (step_cur_idx+1)
        elif action == 'prev':
            step_new_idx = (step_cur_idx-1) < step_begin_idx and step_begin_idx or (step_cur_idx-1)
        step_new = steps[step_new_idx]
        new_vals['step_no'] = step_new
        #do data operation by next step
        if step_new == 'sync' and order_data.sync_direction == 'server2clock':
            #get employees from clock
            emp_codes = [emp.emp_code for emp in  order_data.emp_ids_server]
            emps_clock = self.clock_emps_get(cr, uid, order_data.clock_id.id, emp_codes, context=context)
            #the server emps parameter
            emps_server = [{'emp_code':emp.emp_code,'emp_name':emp.name,
                            'emp_card_id':emp.emp_card_id,'clock_role':emp.clock_role} \
                           for emp in  order_data.emp_ids_server]
            #do sync calculation, set the employees sync action
            emps_sync = self.sync_emps_get(cr, uid, order_data.sync_direction, emps_server, emps_clock, context)
            #convert to the format that can be write to database
            clock_emp_obj = self.pool.get('hr.clock.emp.sync.emp')
            add_clock_emp_ids = []
            for emp in emps_clock:
                emp['emp_pos'] = 'clock_all'
                emp['order_id'] = order_data.id
                #create new clock id
                sel_clock_emp_id = clock_emp_obj.create(cr, uid, emp, context=context)
                add_clock_emp_ids.append(sel_clock_emp_id)
                #connect the many2many to the new created clock emp
            emp_ids_clock = [(6,False,add_clock_emp_ids)]
            
            emp_ids_sync = []
            for emp in emps_sync:
                emp['emp_pos'] = 'sync'
                emp_ids_sync.append((0,0,emp))        
            #delete the old sync data, for the users's previous case
            del_sync_ids = clock_emp_obj.search(cr, uid, [('order_id','=',order_data.id),('emp_pos','=','sync')], context=context)
            clock_emp_obj.unlink(cr, uid, del_sync_ids)
            
            new_vals['emp_ids_clock'] = emp_ids_clock
            new_vals['emp_ids_sync'] = emp_ids_sync
                            
        if step_new == 'employee' and order_data.sync_direction in('clock2server','user2delete'):
            #query the employees on clock, and insert into hr.clock.emp.sync.emp, prepare for the clock employee selection on next step
            clock_emp_obj = self.pool.get('hr.clock.emp.sync.emp')
            exist_clock_emp_ids = clock_emp_obj.search(cr, uid, [('order_id','=',order_data.id),('emp_pos','=','clock_all')],context=context)
            if not exist_clock_emp_ids:
                #query all employees from clock
                emps_clock = self.clock_emps_get_all(cr, uid, order_data.clock_id.id,context=context)
                for emp in emps_clock:
                    emp['emp_pos'] = 'clock_all'
                    emp['order_id'] = order_data.id
                    #write to database
                    new_id = clock_emp_obj.create(cr, uid, emp, context=context)
                    exist_clock_emp_ids.append(new_id)
            #johnw, 01/02/2015, set the clock employee ids by user selected employees on GUI
            #setted in default_get() when user do sync from employee screen
            if order_data.emp_ids_server:
                clock_emp_codes = clock_emp_obj.read(cr, uid, exist_clock_emp_ids, ['emp_code'], context=context)                
                erp_emp_codes = [emp.emp_code for emp in order_data.emp_ids_server]
                sel_clock_emp_ids = []
                for clock_emp_code in clock_emp_codes:
                    if clock_emp_code['emp_code'] in erp_emp_codes:
                        sel_clock_emp_ids.append(clock_emp_code['id'])
                if sel_clock_emp_ids:
                    self.write(cr, uid, order_data.id, {'emp_ids_clock':[(6,False,sel_clock_emp_ids)]}, context=context)            
                                            
        if step_new == 'sync' and order_data.sync_direction == 'clock2server':
            #get employees from server
            emp_codes = [emp.emp_code for emp in  order_data.emp_ids_clock]
            emp_obj = self.pool.get('hr.employee')
            ctx_emp = context.copy()
            ctx_emp['active_test'] = False
            emp_ids = emp_obj.search(cr, uid, [('emp_code','in',emp_codes)],context=ctx_emp)
            emps = emp_obj.browse(cr, uid, emp_ids, context=context)
            emps_server = [{'emp_code':emp.emp_code,'emp_name':emp.name,'emp_card_id':emp.emp_card_id,'clock_role':emp.clock_role} \
                           for emp in  emps]
            #the clock emps parameter
            emps_clock = [{'emp_code':emp.emp_code,'emp_name':emp.emp_name,'emp_card_id':emp.emp_card_id,'clock_role':emp.clock_role} \
                           for emp in  order_data.emp_ids_clock]
            #do sync calculation, set the employees sync action
            emps_sync = self.sync_emps_get(cr, uid, order_data.sync_direction, emps_server, emps_clock, context)
            #convert to the format that can be write to database
            emp_ids_server = [(6,False,emp_ids)]
            emp_ids_sync = []
            for emp in emps_sync:
                emp['emp_pos'] = 'sync'
                emp_ids_sync.append((0,0,emp))
            #delete the old sync data, for the users's previous case
            clock_emp_obj = self.pool.get('hr.clock.emp.sync.emp')
            del_sync_ids = clock_emp_obj.search(cr, uid, [('order_id','=',order_data.id),('emp_pos','=','sync')], context=context)
            clock_emp_obj.unlink(cr, uid, del_sync_ids)
            
            new_vals['emp_ids_server'] = emp_ids_server
            new_vals['emp_ids_sync'] = emp_ids_sync
            
        if step_new == 'sync' and order_data.sync_direction == 'user2delete':
            #the to delete users are same as the selected clock emps
            emps_sync = [{'emp_code':emp.emp_code,'emp_name':emp.emp_name,\
                          'emp_card_id':emp.emp_card_id,'clock_role':emp.clock_role,'emp_pos':'sync','target_state':'to_delete'} \
                           for emp in  order_data.emp_ids_clock]
            #convert to the format that can be write to database
            emp_ids_sync = [(0,0,emp) for emp in emps_sync]
            #delete the old sync data, for the users's previous case
            clock_emp_obj = self.pool.get('hr.clock.emp.sync.emp')
            del_sync_ids = clock_emp_obj.search(cr, uid, [('order_id','=',order_data.id),('emp_pos','=','sync')], context=context)
            clock_emp_obj.unlink(cr, uid, del_sync_ids)
            
            new_vals['emp_ids_sync'] = emp_ids_sync
                        
        #write data
        self.write(cr, uid, ids[0], new_vals,context=context)
        #return action
        model, res_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_hr', 'action_hr_clock_emp_sync')
        action = self.pool.get(model).read(cr, uid, res_id, context=context)
        action['res_id'] = ids[0]
        return action
        
    def sync_emps_get(self, cr, uid, sync_direction, emp_ids_server, emp_ids_clock, context=None):
        if not sync_direction \
            or (sync_direction == 'server2clock' and not emp_ids_server) \
            or (sync_direction == 'clock2server' and not emp_ids_clock):
            return []
        emp_ids_sync = []
        emps_server = {}
        emps_clock = {}
        for emp in emp_ids_server:
            emps_server[emp['emp_code']] = emp
        for emp in emp_ids_clock:
            emps_clock[emp['emp_code']] = emp
            
        if sync_direction == 'server2clock':
            for emp_server_code, emp_server in emps_server.items():
                emp_server.update({'target_state':'exist','emp_pos':'sync'})
                emp_clock = emps_clock.get(emp_server_code)
                if not emp_clock:
                    #Not existing on clock, then can create
                    emp_server.update({'target_state':'miss'})
                elif emp_clock['emp_name'] != emp_server['emp_name'] \
                        or emp_clock['emp_card_id'] != emp_server['emp_card_id'] \
                        or emp_clock['clock_role'] != emp_server['clock_role']:
                    #Base info different then can do update
                    emp_server.update({'target_state':'diff'})
                #add to the emp_ids
                emp_ids_sync.append(emp_server)
                    
        if sync_direction == 'clock2server':
            for emp_clock_code, emp_clock in emps_clock.items():
                emp_clock.update({'target_state':'exist','emp_pos':'sync'})
                emp_server = emps_server.get(emp_clock_code)
                if not emp_server:
                    #Not existing on clock, then can create
                    emp_clock.update({'target_state':'miss'})
                elif emp_clock['emp_name'] != emp_server['emp_name'] \
                        or emp_clock['emp_card_id'] != emp_server['emp_card_id'] \
                        or emp_clock['clock_role'] != emp_server['clock_role']:
                    #Base info different then can do update
                    emp_clock.update({'target_state':'diff'})
                #add to the emp_ids
                
                emp_ids_sync.append(emp_clock)
                
        return emp_ids_sync
    
    def clock_emps_get(self, cr, uid, clock_id, emp_codes, ret_dict = False, pwd = False, finger_print = False, context=None):
        if not clock_id:
            return []
                
        clock = clock_util.clock_obj()
        clock_data = self.pool.get('hr.clock').read(cr, uid, clock_id, ['ip','port'], context=context)
        clock_util.clock_connect(clock, clock_data['ip'], clock_data['port'])
        
        #get all employees on clock
        emps_clock = []
        if ret_dict:
            emps_clock = {}
        for emp_code in emp_codes:
            emp_clock = clock_util.clock_user_get(clock, emp_code, pwd=pwd, finger_print=finger_print)
            if emp_clock:
                if ret_dict:
                    emps_clock[emp_code] = emp_clock                    
                else:
                    emps_clock.append(emp_clock)
                
        clock_util.clock_disconnect(clock)
        
        return emps_clock
    
    def clock_emps_get_all(self, cr, uid, clock_id, ret_dict = False, pwd = False, finger_print = False, context=None):
        if not clock_id:
            return []
                
        clock = clock_util.clock_obj()
        clock_data = self.pool.get('hr.clock').read(cr, uid, clock_id, ['ip','port'], context=context)
        clock_util.clock_connect(clock, clock_data['ip'], clock_data['port'])
        
        #get all employees on clock
        clock_emps = clock_util.clock_user_get_all(clock, ret_dict = ret_dict, pwd=pwd, finger_print=finger_print)
        
        clock_util.clock_disconnect(clock)
        
        return clock_emps
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
