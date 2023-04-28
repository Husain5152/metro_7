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

from openerp.osv import fields
from openerp.osv import osv
from openerp.tools.translate import _

class hr_employee(osv.osv):
    _inherit = "hr.employee"
    _columns = {
        'hourly_rate': fields.float('Hourly Rate'),
    }

    def _getEmployeeProduct(self, cr, uid, context=None):
        md = self.pool.get('ir.model.data')
        try:
            result = md.get_object_reference(cr, uid, 'metro_hr', 'product_employee_cost')
            return result[1]
        except ValueError:
            pass
        return False

    _defaults = {
        'product_id': _getEmployeeProduct
    }
hr_employee()

class hr_analytic_timesheet(osv.osv):
    _inherit = "hr.analytic.timesheet"
    _columns = {
        'employee_id': fields.many2one('hr.employee', 'Employee', ondelete='cascade'),
    }
    def on_change_unit_amount(self, cr, uid, id, prod_id, unit_amount, company_id, unit=False, journal_id=False, context=None):
        res = super(hr_analytic_timesheet,self).on_change_unit_amount(cr, uid, id, prod_id, unit_amount, company_id, unit, journal_id, context=context)
        if context.get('employee_id'):
            emp_data = self.pool.get('hr.employee').read(cr, uid, context.get('employee_id'), ['hourly_rate'])
            if emp_data.get('hourly_rate'):
                res['value'].update({'amount': emp_data['hourly_rate']*unit_amount})
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
