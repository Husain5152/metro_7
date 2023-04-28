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
    'name': 'Metro Project',
    'version': '1.0',
    'category': 'Metro',
    'description': """
    
        Metro Project Extension:  
        
        1.Enhance the issue management
        
        (Ported to OpenERP v 7.0 by Metro Tower Trucks.
        
        """,
        
        
    'author': 'Metro Tower Trucks',
    'website': 'http://www.metrotowtrucks.com',
    'depends': ["web_kanban_subgrp", "metro", "project_issue", "metro_attachment", "multi_image", "metro_sale", "metro_mrp", "project", "project_gtd", "project_timesheet", "metro_hr"],
    'data': [
        'security/project_security.xml', 
        'project_issue_view.xml',    
        'project_simple_view.xml',
        'project_engineer_view.xml',   
        'project_simple_data.xml', 
        'project_gtd_view.xml',
        'project_mfg_view.xml',
        'project_report.xml',
        'project_data.xml',
        'wizard/task_print.xml',
        'wizard/project_task_batchset_view.xml',
        'board_tasks_view.xml'
    ],
    'test': [],
    'demo': [],
    'css': [
        'static/src/css/project.css'
    ],
#    'js' : [
#        "static/src/js/metro_project.js",
#    ],
#    'qweb' : [
#        "static/src/xml/*.xml",
#    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
