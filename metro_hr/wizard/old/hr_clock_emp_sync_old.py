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
        'emp_pos':fields.selection([('server','On Servers'),('clock','On Clocks'),('tosync','To Sync')],string='Action'),
        'action':fields.selection([('update','Update'),('create','Create'),('delete','Delete'),('user_add','User Add')],string='Action'),
    }         

class hr_clock_emp_sync(osv.osv_memory):
    _name = 'hr.clock.emp.sync'
    _description = 'Sync Clock Employee'
    _columns = {
        'clock_id' : fields.many2one('hr.clock','Clock to Sync', required=True),
        'sync_direction' : fields.selection([('server2clock','Server to Clock'),('clock2server','Clock to Servr')],string='Sync Direction', required=True),
        'emp_ids_server' : fields.one2many('hr.clock.emp.sync.emp', 'order_id', 'Employees on Server', domain=[('emp_pos','=','server')]),
        'emp_ids_clock' : fields.one2many('hr.clock.emp.sync.emp', 'order_id', 'Clock Employees', domain=[('emp_pos','=','clock')]),
        'emp_ids_sync' : fields.one2many('hr.clock.emp.sync.emp', 'order_id', 'Employees to Sync', domain=[('emp_pos','=','tosync')]),
        'sync_opt_base' : fields.boolean('Base Info'),
        'sync_opt_fp' : fields.boolean('Finger Print'),
        'sync_opt_pwd' : fields.boolean('Password'),
    }
    _defaults = {'sync_opt_base':True}
    
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
        vals = {}
        emp_obj = self.pool.get('hr.employee')
        #server employee ids
        emp_ids_server = []
        emp_ids = []
        if context.get('active_model','') == 'hr.employee' and context.get('active_ids'):
            emp_ids = context.get('active_ids')
        else:
            emp_ids = self.pool.get('hr.employee').search(cr, uid, [], context=context)
        
        for emp in emp_obj.read(cr, uid, emp_ids, ['emp_code', 'name', 'emp_card_id', 'clock_role'], context=context):
            emp_add = {'emp_code':emp['emp_code'], 'emp_name':emp['name'], 
                                'emp_card_id':emp['emp_card_id'], 'clock_role':emp['clock_role'],
                                'emp_pos':'server'}
            emp_ids_server.append(emp_add)
            
        vals['emp_ids_server'] = emp_ids_server
        #clock id
        if context.get('active_model','') == 'hr.clock' and context.get('active_id'):
            clock_id = context.get('active_id')
            vals['clock_id'] = clock_id
        
        #set default values
        for item, value in context.items():
            if isinstance(item, type(u' ')) and item.startswith('default_'):
                fld_name = item[8:]
                if self._columns.get(fld_name):
                    vals[fld_name] = value
        
#        emp_ids_clock = self.clock_emps_get(cr, uid, vals.get('clock_id'))
#        if emp_ids_clock:
#            vals.update({'emp_ids_clock':emp_ids_clock})
#            
#        emp_ids_sync = self.sync_emps_get(cr, uid, vals.get('sync_direction'), emp_ids, emp_ids_clock, context=context)
#        if emp_ids_sync:
#            vals.update({'emp_ids_clock':emp_ids_sync})
            
        return vals
    
    def sync_emps_get(self, cr, uid, sync_direction, emp_ids_server, emp_ids_clock, context=None):
        if not sync_direction or not emp_ids_server or not emp_ids_clock:
            return []
        emp_ids_sync = []
        emps_server = {}
        emps_clock = {}
        for emp in emp_ids_server:
            emps_server[emp.emp_code] = [emp.emp_name, emp.emp_card_id, emp.clock_role]
        for emp in emp_ids_clock:
            emps_clock[emp.emp_code] = [emp.emp_name, emp.emp_card_id, emp.clock_role]
            
        if sync_direction == 'server2clock':
            for emp_server_code, emp_server_vals in emps_server:
                emp_clock = emps_clock.get(emp_server_code)
                if not emp_clock:
                    #Not existing on clock, then can create
                    emp_ids_sync.append({'emp_code':emp_server_code, 'emp_name':emp_server_vals[0],
                                                    'emp_card_id':emp_server_vals[1], 'clock_role':emp_server_vals[2],
                                                    'action':'create'})
                elif emp_clock['emp_name'] != emp_server_vals[0] \
                    or emp_clock['emp_card_id'] != emp_server_vals[1] \
                    or emp_clock['clock_role'] != emp_server_vals[2]:
                    #Base info different then can do update
                    emp_ids_sync.append({'emp_code':emp_server_code, 'emp_name':emp_server_vals[0],
                                                    'emp_card_id':emp_server_vals[1], 'clock_role':emp_server_vals[2],
                                                    'action':'update'})
        if sync_direction == 'clock2server':
            for emp_clock_code, emp_clock_vals in emps_clock:
                emp_server = emps_server.get(emp_clock_code)
                if not emp_server:
                    #Not existing on clock, then can create
                    emp_ids_sync.append({'emp_code':emp_server_code, 'emp_name':emp_server_vals[0],
                                                    'emp_card_id':emp_server_vals[1], 'clock_role':emp_server_vals[2],
                                                    'action':'create'})
                elif emp_clock['emp_name'] != emp_server_vals[0] \
                    or emp_clock['emp_card_id'] != emp_server_vals[1] \
                    or emp_clock['clock_role'] != emp_server_vals[2]:
                    #Base info different then can do update
                    emp_ids_sync.append({'emp_code':emp_server_code, 'emp_name':emp_server_vals[0],
                                                    'emp_card_id':emp_server_vals[1], 'clock_role':emp_server_vals[2],
                                                    'action':'update'})                    
#        sync_emps = []
#        emp_obj = self.pool.get('hr.employee')
#        if sync_direction and emp_ids_server and emp_ids_clock:
#            for emp_clock in emp_ids_clock:
#                emp_code = 
#                
#        return sync_emps
        return emp_ids_clock
            
        
    def clock_emps_get(self, cr, uid, clock_id, context=None):
        if not clock_id:
            return []
                
        clock = clock_util.clock_obj()
        clock_data = self.pool.get('hr.clock').read(cr, uid, clock_id, ['ip','port'], context=context)
        clock_util.clock_connect(clock, clock_data['ip'], clock_data['port'])
        
        #get all employees on clock
        clock_emps = clock_util.clock_user_get_all(clock)
        return clock_emps
        
    def clock_emps_query(self, cr, uid, ids, context=None):
        vals = {}
        order = self.browse(cr, uid, ids[0], context=context)
        #emps on clock
        emp_ids_clock =  self.clock_emps_get(cr, uid, order.clock_id.id, context=None)
        if emp_ids_clock:
            set_clock_emps = []
            for clock_emp in emp_ids_clock:
                clock_emp['emp_pos'] = 'clock'
                set_clock_emps.append((0,0,clock_emp))
                if clock_emp.get('clock_role','') != '':
                    print clock_emp
            vals.update({'emp_ids_clock':set_clock_emps})
        #update emps
        self.write(cr, uid, ids[0], vals, context=context)
        #also asuto get the emps to sync
        self.clock_emps_sync(cr, uid, ids, context=context)      
        return True
    
    def clock_emps_sync(self, cr, uid, ids, context=None):
        vals = {}
        order = self.browse(cr, uid, ids[0], context=context)
        #emps to sync
        sync_emps = self.sync_emps_get(cr, uid, order.sync_direction, order.emp_ids_server, order.emp_ids_clock)
        if sync_emps:
            set_sync_emps = []
            for sync_emp in sync_emps:
                sync_emp['emp_pos'] = 'sync'
                set_sync_emps.append(sync_emp)
            vals.update({'emp_ids_sync':set_sync_emps})
        #update emps
        self.write(cr, uid, ids[0], vals, context=context)    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
