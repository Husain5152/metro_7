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

#
# Please note that these reports are not multi-currency !!!
#

from openerp.osv import fields,osv
from openerp import tools
import openerp.addons.decimal_precision as dp

class hr_emppay_rpt_emp_year(osv.osv):
    _name = "hr.emppay.rpt.emp.year"
    _description = "Payslip Report by employee and year"
    _auto = False
    _rec_name = 'employee_id'
    _columns = {
        'employee_id': fields.many2one('hr.employee', 'Employee', required=True, readonly=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal Year', required=True),

        'wage':fields.float('Contract Wage', digits_compute=dp.get_precision('Payroll')),
        'wage2':fields.float('Basic Wage', digits_compute=dp.get_precision('Payroll')),      
        
        #attendance
        'days_work': fields.float('Work Days', readonly=True),
        'days_attend': fields.float('Attended Days', readonly=True),
        'hours_ot': fields.float('OT Hours', readonly=True),
        'hours_ot_we': fields.float('Weekend OT Hours', readonly=True),#0
        'hours_ot_holiday': fields.float('Holiday OT Hours', readonly=True), #0
        
        'days_work2': fields.float('Work Days by five days', readonly=True),
        'days_attend2_real': fields.float('Attended Days by five days', readonly=True),
        'days_attend2': fields.float('Attended Days by 21.75', readonly=True),
        'hours_ot2': fields.float('Non Weekend OT Hours', readonly=True),
        'hours_ot_we2': fields.float('Weekend OT Hours', readonly=True),
        'hours_ot_holiday2': fields.float('Holiday OT Hours', readonly=True), #0
        
        #wage
        'wage_attend':fields.float('Wage of attendance', digits_compute=dp.get_precision('Payroll')), 
        'wage_ot':fields.float('Wage of OT', digits_compute=dp.get_precision('Payroll')),
        'wage_ot_we':fields.float('Wage of Weekend OT', digits_compute=dp.get_precision('Payroll')),
        'wage_ot_holiday':fields.float('Wage of Holiday OT', digits_compute=dp.get_precision('Payroll')),                        
        'wage_ot_total':fields.float('Total Wage of OT', digits_compute=dp.get_precision('Payroll')),
        'wage_work':fields.float('Work Wage', digits_compute=dp.get_precision('Payroll')),
        'alw_total':fields.float('Allowance', digits_compute=dp.get_precision('Payroll')),                
                
        'wage_total':fields.float('Total Wage', digits_compute=dp.get_precision('Payroll')),
        'ded_total':fields.float('Deduction', digits_compute=dp.get_precision('Payroll')),
        'si_total_personal':fields.float('SI(Personal)', digits_compute=dp.get_precision('Payroll')),
        'si_total_company':fields.float('SI(Company)', digits_compute=dp.get_precision('Payroll')),
        'wage_pay':fields.float('Wage should Pay', digits_compute=dp.get_precision('Payroll')),
        'wage_tax':fields.float('Wage for Tax', digits_compute=dp.get_precision('Payroll')),
        'pit':fields.float('PIT', digits_compute=dp.get_precision('Payroll')),
        'wage_net':fields.float('Net Wage', digits_compute=dp.get_precision('Payroll')),
        
        #wages for 2
        'wage_attend2':fields.float('Wage of Attendance by five days', digits_compute=dp.get_precision('Payroll')),
        'wage_ot2':fields.float('Wage of OT', digits_compute=dp.get_precision('Payroll')),
        'wage_ot_we2':fields.float('Wage of Weekend OT', digits_compute=dp.get_precision('Payroll')),
        'wage_ot_holiday2':fields.float('Net Wage', digits_compute=dp.get_precision('Payroll')),
        'wage_ot_total2':fields.float('Total Wage of OT by five days', digits_compute=dp.get_precision('Payroll')),
        'alw_inwage_total':fields.float('Allowage In Wage', digits_compute=dp.get_precision('Payroll')),
        'wage_bonus2':fields.float('Bonus', digits_compute=dp.get_precision('Payroll')),
        'wage_work2':fields.float('Work Wage by five days', digits_compute=dp.get_precision('Payroll')),

    }
    
    _order = 'employee_id,fiscalyear_id'
    
    def init(self, cr):
        tools.sql.drop_view_if_exists(cr, 'hr_emppay_rpt_emp_year')
        cr.execute("""
            create or replace view hr_emppay_rpt_emp_year as (
                select a.employee_id, d.fiscalyear_id,
                min(a.id) as id,
                sum(b.days_work) days_work,
                sum(b.days_attend) days_attend,
                sum(b.hours_ot) hours_ot,
                sum(a.hours_ot_we) hours_ot_we,
                sum(a.hours_ot_holiday) hours_ot_holiday,
                
                sum(b.days_work2) days_work2,
                sum(b.days_attend2_real) days_attend2_real,
                sum(b.days_attend2) days_attend2,
                sum(b.hours_ot2_nonwe) hours_ot2,
                sum(b.hours_ot2_we) hours_ot_we2,
                sum(a.hours_ot_holiday2) hours_ot_holiday2,
                        
                sum(a.wage) as wage,
                sum(a.wage_attend) as wage_attend,
                sum(a.wage_ot) as wage_ot,
                sum(a.wage_ot_we) as wage_ot_we,
                sum(a.wage_ot_holiday) as wage_ot_holiday,
                sum(a.wage_ot_total) as wage_ot_total,
                sum(a.wage_work) as wage_work,
                sum(a.alw_total) as alw_total,
                sum(a.wage_total) as wage_total,
                sum(a.ded_total) as ded_total,
                sum(a.si_total_personal) as si_total_personal,
                
                sum(a.si_total_company) as si_total_company,
                sum(a.wage_pay) as wage_pay,
                sum(a.wage_tax) as wage_tax,
                
                sum(a.pit) as pit,
                sum(a.wage_net) as wage_net,
                
                sum(a.wage2) as wage2,
                sum(a.wage_attend2) as wage_attend2,
                sum(a.wage_ot2) as wage_ot2,
                sum(a.wage_ot_we2) as wage_ot_we2,
                sum(a.wage_ot_holiday2) as wage_ot_holiday2,
                sum(a.wage_ot_total2) as wage_ot_total2,
                sum(a.alw_inwage_total) as alw_inwage_total,
                sum(a.wage_bonus2) as wage_bonus2,
                sum(a.wage_work2) as wage_work2
                                
                from hr_emppay a
                left join hr_rpt_attend_month_line b on a.attend_id = b.id
                join hr_emppay_sheet c on a.emppay_sheet_id = c.id
                join account_period d on c.account_period_id = d.id
                group by a.employee_id, d.fiscalyear_id
            )
        """)
hr_emppay_rpt_emp_year()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
