# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP S.A. <http://www.openerp.com>
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

from osv import fields, osv
from datetime import datetime, time
import tools
from tools.translate import _
from openerp.addons.metro import mdb
from openerp.tools.misc import resolve_attr
from openerp.addons.metro import utils

import logging

_logger = logging.getLogger(__name__)


class hr_department(osv.osv):
    _description = "Department"
    _inherit = 'hr.department'
    _order = 'sequence,id'
    _columns = {
        # with the sequence field, then on the kanban view by department, user can change the sequence of departments.
        'sequence': fields.integer('Sequence'),
        # +++ HoangTK - 11/19/2015: Add hr code to department
        'code': fields.char('Code', size=10),
        # --- HoangTK - 11/19/2015
    }

    def name_get(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not ids:
            return []
        reads = self.read(cr, uid, ids, ['name', 'parent_id'], context=context)
        res = []
        for record in reads:
            name = record['name']
            res.append((record['id'], name))
        return res


class hr_medical_type(osv.osv):
    """ Known Medical Types """
    _name = "hr.medical.type"
    _description = "Known Medical Types"
    _columns = {
        'name': fields.char('Medical Name', size=64, required=True, translate=True),
    }


class hr_employee(osv.osv):
    _inherit = "hr.employee"
    _order = 'emp_code'

    def _get_leave_status(self, cr, uid, ids, name, args, context=None):
        holidays_obj = self.pool.get('hr.holidays')
        # fix the time interval query parameter issue
        ''' old code
        holidays_id = holidays_obj.search(cr, uid,
           [('employee_id', 'in', ids), ('date_from','<=',time.strftime('%Y-%m-%d %H:%M:%S')),
           ('date_to','>=',time.strftime('%Y-%m-%d 23:59:59')),('type','=','remove'),('state','not in',('cancel','refuse'))],
           context=context)
        '''
        now = datetime.utcnow()
        holidays_id = holidays_obj.search(cr, uid,
                                          [('employee_id', 'in', ids),
                                           ('date_from', '<=', now.strftime('%Y-%m-%d %H:%M:%S')),
                                           ('date_to', '>=', now.strftime('%Y-%m-%d %H:%M:%S')),
                                           ('type', '=', 'remove'), ('state', 'not in', ('cancel', 'refuse'))],
                                          context=context)
        result = {}
        for id in ids:
            result[id] = {
                'current_leave_state': False,
                'current_leave_id': False,
                'leave_date_from': False,
                'leave_date_to': False,
            }
        for holiday in self.pool.get('hr.holidays').browse(cr, uid, holidays_id, context=context):
            result[holiday.employee_id.id]['leave_date_from'] = holiday.date_from
            result[holiday.employee_id.id]['leave_date_to'] = holiday.date_to
            result[holiday.employee_id.id]['current_leave_state'] = holiday.state
            result[holiday.employee_id.id]['current_leave_id'] = holiday.holiday_status_id.id
        return result

    _columns = {
        'employment_start': fields.date('Employment Started'),
        'employment_resigned': fields.date('Employment Resigned'),
        'employment_finish': fields.date('Employment Finished'),
        'salaryhistory_ids': fields.one2many('hr.employee.salaryhistory', 'salary_id', 'Salary History'),
        # need to copy the below columns here since redefine the method _get_leave_status
        'current_leave_state': fields.function(_get_leave_status, multi="leave_status", string="Current Leave Status",
                                               type="selection",
                                               selection=[('draft', 'New'), ('confirm', 'Waiting Approval'),
                                                          ('refuse', 'Refused'),
                                                          ('validate1', 'Waiting Second Approval'),
                                                          ('validate', 'Approved'), ('cancel', 'Cancelled')]),
        'current_leave_id': fields.function(_get_leave_status, multi="leave_status", string="Current Leave Type",
                                            type='many2one', relation='hr.holidays.status'),
        'leave_date_from': fields.function(_get_leave_status, multi='leave_status', type='date', string='From Date'),
        'leave_date_to': fields.function(_get_leave_status, multi='leave_status', type='date', string='To Date'),
        'emp_code': fields.char('Employee Code', size=16),
        'emp_card_id': fields.char('Employee Card ID', size=16),
        'multi_images': fields.text("Multi Images"),
        'room_no': fields.char("Room#", size=16),
        'bunk_no': fields.char('Bunk#', size=16),
        'emergency_contacter': fields.char("Emergency Contacter", size=32),
        'emergency_phone': fields.char("Emergency Phone", size=32),
        'known_medical_cond': fields.text("Known Medical Conditions"),
        'known_medical_type': fields.many2many('hr.medical.type', string='Known Medical Types'),
        'known_allergies': fields.text("Known Allergies"),
        'recruit_source_id': fields.many2one('hr.recruitment.source', 'Recruitment Source'),
        'degree_id': fields.many2one('hr.recruitment.degree', 'Degree'),
        'major': fields.char('Major', size=16),
        'height': fields.char('Height(cm)', size=8),
        'weight': fields.char('Weight(kg)', size=8),
        # added per marc's request
        'date_orient_session': fields.date('Orientation Session Date'),
        'web_chat_no': fields.char('QQ#', size=16),
        'name_tag': fields.char('Name Tag', size=64),
        'tools_assigned': fields.char('Tools Assigned', size=128),
        'business_card': fields.char('Business Cards', size=128),
        'computer_id': fields.char('Computer ID', size=128),
    }
    _sql_constraints = [
        ('emp_code_uniq', 'unique(emp_code)', 'Employee Code must be unique!'),
    ]

    def default_get(self, cr, uid, fields_list, context=None):
        values = super(hr_employee, self).default_get(cr, uid, fields_list, context)
        cr.execute("SELECT max(id) from hr_employee")
        emp_id = cr.fetchone()
        emp_code = '%03d' % (emp_id[0] + 1,)
        values.update({'emp_code': emp_code})
        return values

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        for arg in args:
            # add the category improving
            if arg[0] == 'department_id' and arg[1] == '=' and isinstance(arg[2], (int, long)):
                idx = args.index(arg)
                args.remove(arg)
                args.insert(idx, [arg[0], 'child_of', arg[2]])

        # get the search result
        ids = super(hr_employee, self).search(cr, user, args, offset, limit, order, context, count)

        return ids

    def get_report_name(self, cr, uid, id, rpt_name, context=None):
        if rpt_name == 'hr.welcome.checklist':
            return "Employee Welcome Cheklist"
        else:
            return None

    # add the emp_code return in the name
    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        result = []
        for data in self.browse(cr, user, ids, context=context):
            if data.id <= 0:
                result.append((data.id, ''))
                continue
            result.append((data.id, '[%s]%s' % (data.emp_code, data.name)))

        return result

    # add the emp_code search in the searching
    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if name:
            if 'not' in operator:
                ids = self.search(cr, user, [('emp_code', operator, name), ('name', operator, name)] + args, limit=limit, context=context)
            else:
                ids = self.search(cr, user, [('emp_code', operator, name)] + args, limit=limit, context=context)
                if not ids:
                    ids = self.search(cr, user, [('name', operator, name)] + args, limit=limit, context=context)
                if not ids:
                    ids = set()
                    ids.update(self.search(cr, user, args + [('emp_code', operator, name)], limit=limit, context=context))
                    if not limit or len(ids) < limit:
                        # we may underrun the limit because of dupes in the results, that's fine
                        ids.update(self.search(cr, user, args + [('name', operator, name)],
                                               limit=(limit and (limit - len(ids)) or False), context=context))
                    ids = list(ids)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
        result = self.name_get(cr, user, ids, context=context)
        return result

    # update user related employee_id
    def update_user_emp(self, cr, uid, user_id, emp_id, context=None):
        if user_id and emp_id:
            # use sql to update, avoie the dead looping calling with res_user.update_emp_user()
            cr.execute('update res_users set employee_id = %s where id = %s', (emp_id, user_id))

    def write(self, cr, uid, ids, vals, context=None):
        resu = super(hr_employee, self).write(cr, uid, ids, vals, context=context)
        if 'user_id' in vals:
            self.update_user_emp(cr, uid, vals['user_id'], ids[0], context)
        return resu

    def create(self, cr, uid, vals, context=None):
        new_id = super(hr_employee, self).create(cr, uid, vals, context=context)
        if 'user_id' in vals:
            self.update_user_emp(cr, uid, vals['user_id'], new_id, context)
        return new_id

    def sync_clock(self, cr, uid, ids=None, context=None):
        _logger.info('begining sync_clock...')
        if not context:
            context = {}
        if not ids:
            ids = self.search(cr, uid, [('active', '=', True)], context=context)
        # get the clock data
        file_name = self.pool.get('ir.config_parameter').get_param(cr, uid, 'hr_clock_mdb_file', context=context)
        _logger.info('sync data to file:%s', file_name)
        conn = mdb.open_conn(file_name)
        sql = "select userid,badgenumber,name,gender,ssn,minzu,ophone,title,birthday,hiredday,cardno,pager,street from userinfo"
        emps_clock, fld_size = mdb.exec_query(conn, sql, 'ssn')
        if len(fld_size) == 0:
            fld_size = {'badgenumber': 24,
                        'name': 40,
                        'gender': 8,
                        'ssn': 20,
                        'minzu': 8,
                        'ophone': 20,
                        'title': 20,
                        'birthday': -1,
                        'hiredday': -1,
                        'cardno': 20,
                        'pager': 20,
                        'street': 80,
                        'badgenumber': 24,
                        'name': 40,
                        'gender': 8,
                        'ssn': 20,
                        'minzu': 8,
                        'ophone': 20,
                        'title': 20,
                        'birthday': -1,
                        'hiredday': -1,
                        'cardno': 20,
                        'pager': 20,
                        'street': 80,
                        }
        # compare the data, and push the chaning to clock
        check_attrs = {'badgenumber': 'emp_code',
                       'name': 'name',
                       'gender': 'gender',
                       'ssn': 'emp_code',
                       'minzu': '',
                       'ophone': 'work_phone',
                       'title': 'job_id.name',
                       'birthday': 'birthday',
                       'hiredday': 'employment_start',
                       'cardno': 'emp_card_id',
                       'pager': 'mobile_phone',
                       'street': 'address_home_id.name',
                       }
        for emp in self.browse(cr, uid, ids, context=context):
            if not emps_clock.has_key(emp.emp_code):
                # do insert
                cols = ''
                vals = ''
                for attr in check_attrs:
                    cols = cols + attr + ','
                    attr_val = ''
                    if check_attrs[attr] != '':
                        attr_val = resolve_attr(emp, check_attrs[attr]) or ''
                        if fld_size[attr] > 0:
                            attr_val = attr_val[:fld_size[attr]]
                    if attr == 'gender':
                        if attr_val == 'male':
                            attr_val = 'M'
                        if attr_val == 'female':
                            attr_val = 'F'
                    vals = vals + ('\'%s\',' % attr_val)
                import sys
                _logger.info('%s - %s' % (isinstance(vals, unicode), sys.getdefaultencoding()))
                vals = vals.encode('utf-8')
                sql = 'insert into userinfo (%s) values(%s)' % (cols[:-1], vals[:-1])
                mdb.exec_ddl(conn, sql)
            else:
                # do update
                emp_clock = emps_clock[emp.emp_code]
                upt_cols = ''
                for attr in check_attrs:
                    if check_attrs[attr] == '':
                        continue
                    attr_val = resolve_attr(emp, check_attrs[attr]) or ''
                    if fld_size[attr] > 0:
                        attr_val = attr_val[:fld_size[attr]]
                    attr_val_clock = emp_clock[attr]
                    if attr == 'gender':
                        if attr_val == 'male':
                            attr_val = 'M'
                        if attr_val == 'female':
                            attr_val = 'F'
                    if attr_val != attr_val_clock:
                        upt_cols = upt_cols + attr + '=\'' + attr_val + '\','
                if upt_cols != '':
                    upt_cols = upt_cols[:-1]
                    sql = 'update userinfo set ' + upt_cols + ' where userid = ' + str(emp_clock['userid'])
                    mdb.exec_ddl(conn, sql)
            _logger.info('Synchronized employee-%s...', emp.emp_code)
        mdb.close_conn(conn)
        _logger.info('end sync_clock')
        return True


hr_employee()


class salary_history(osv.osv):
    _name = "hr.employee.salaryhistory"
    _description = "Employee Salary History"
    _columns = {
        'date': fields.date('Date', required=True),
        'salary': fields.char('Amount (CNY)', size=64),
        'reason': fields.char('Reason for Change', size=64),
        'salary_id': fields.many2one('hr.employee', 'Test', ondelete='cascade'),
    }
    _order = 'date desc'


salary_history()


class hr_holiday_calendar(osv.osv):
    _name = "hr.employee.holidaycalendar"
    _description = "Holiday Calendar Dates"
    _columns = {
        'date_stop': fields.date('Stop date', required=False),
        'date_start': fields.date('Start date', required=True),
        'name': fields.char('Holiday Name', size=512, required=True),
        'holidaytype': fields.selection(
            [('chineseholiday', 'Chinese National Holiday'), ('longjuholiday', 'Dongguan Longju Holiday'),
             ('extraworkday', 'Extra Working Day')], 'Holiday Type'),
    }
    _defaults = {'holidaytype': 'chineseholiday',
                 }


hr_holiday_calendar()

'''
Add 'employee_id' to res_users, to manage the rules convention
--update by the employee's user setting
update res_users c
set employee_id = a.id
from hr_employee a,
resource_resource b 
where a.resource_id = b.id
and b.user_id = c.id

--Record rule on hr.holiday using the employee_id
[('employee_id','child_of', [user.employee_id.id])]
and below is also working
[('employee_id','in', user.employee_id and [emp.id for emp in user.employee_id.child_ids] or [])]

'''


class res_users(osv.osv):
    _name = 'res.users'
    _inherit = 'res.users'

    def _get_emp_image(self, cr, uid, ids, names, args, context=None):
        result = dict.fromkeys(ids, {'img_emp': False, 'img_emp_medium': False, 'img_emp_small': False})
        # get the images from employee
        for user in self.browse(cr, uid, ids, context=context):
            #			if user.employee_ids:
            #				result[user.id] = {'img_emp':user.employee_ids[0].image, 'img_emp_medium':user.employee_ids[0].image_medium, 'img_emp_small':user.employee_ids[0].image_small}
            if user.employee_id:
                result[user.id] = {'img_emp': user.employee_id.image,
                                   'img_emp_medium': user.employee_id.image_medium,
                                   'img_emp_small': user.employee_id.image_small}
        return result

    _columns = {
        'img_emp': fields.function(_get_emp_image, string="Image", type="binary", multi="_get_image", ),
        'img_emp_medium': fields.function(_get_emp_image, string="Medium-sized image", type="binary",
                                          multi="_get_image", ),
        'img_emp_small': fields.function(_get_emp_image, string="Small-sized image", type="binary",
                                         multi="_get_image", ),
        'employee_id': fields.many2one('hr.employee', 'Employee'),
    }

    def copy(self, cr, uid, id, default=None, context=None):
        default.update({'employee_ids': [], 'employee_id': None})
        return super(res_users, self).copy(cr, uid, id, default, context)

    # update employee related user_id
    def update_emp_user(self, cr, uid, user_id, emp_id, context=None):
        if user_id and emp_id:
            # use sql to update, avoie the dead looping calling with hr_employee.update_user_emp()
            resource_id = self.pool.get('hr.employee').browse(cr, uid, emp_id, context=context).resource_id.id
            cr.execute('update resource_resource set user_id = %s where id = %s', (user_id, resource_id))

    def write(self, cr, uid, ids, vals, context=None):
        resu = super(res_users, self).write(cr, uid, ids, vals, context=context)
        if 'employee_id' in vals:
            self.update_emp_user(cr, uid, ids[0], vals['employee_id'], context)
        return resu

    def create(self, cr, uid, vals, context=None):
        new_id = super(res_users, self).create(cr, uid, vals, context=context)
        if 'employee_id' in vals:
            self.update_emp_user(cr, uid, new_id, vals['employee_id'], context)
        return new_id
