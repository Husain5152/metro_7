# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2010 OpenERP s.a. (<http://openerp.com>).
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
{
    'name': 'Metro HR',
    'version': '1.0',
    'category': 'Metro',
    'description': """
    
        Metro HR Extension:  
        
        """,
        
        
    'author': 'Metro Trucks.',
    'website': 'http://www.metrotowertrucks.com/',
    'depends': ["metro", "hr", "hr_holidays", "product", "metro_attachment", "hr_timesheet", "multi_image", "hr_recruitment", "hr_contract", "hr_payroll", "hr_payroll_account", "metro_accounts"],
    'init_xml': [],
    'update_xml': [
        'wizard/hr_send_checklist.xml',
        'hr_emp_menu.xml',
        'hr_view.xml',
        'hr_timesheet_view.xml',
        'hr_contract_view.xml',
        'metro_calendar_view.xml',
        'wizard/hr_clock_emp_sync_view.xml',
        'wizard/hr_emp_wtgrp_set_view.xml',
        'wizard/hr_attend_calc_action_view.xml',
        'wizard/hr_rpt_attend_emp_day_view.xml',
        'wizard/hr_rpt_attend_month_view.xml',
        'wizard/hr_rpt_attend_month_workflow.xml',
        'wizard/hr_contract_change_si_view.xml',
        'hr_attendance_view.xml',
        'hr_clock_view.xml',
        'hr_holidays.xml',
        'hr_data.xml',
        'emppay/hr_emppay_sequence.xml',
        'emppay/hr_emppay_view_setup.xml',
        'emppay/hr_emppay_view_main.xml',
        'emppay/ir.model.access.csv',
        'emppay/hr_contact_emppay_batchset_view.xml',
        'emppay/hr_emppay_report.xml',
        'emppay/hr_emppay_currency_view.xml',
        'security/ir.model.access.csv',
        'hr_report.xml',
        'dimission/hr_dimission_view.xml',
        'dimission/ir.model.access.csv',
    ],
    'demo_xml': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'active': False,
	'sequence': 150,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
