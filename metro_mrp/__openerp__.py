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
    'name': 'Metro MRP',
    'version': '1.0',
    'category': 'Metro',
    'description': """
    
        Metro MRP Extension:  
        
        1.Add CNC Work Order
        
        (Ported to OpenERP v 7.0 by Metro Tower Trucks.
        
        """,
        
        
    'author': 'Metro Tower Trucks',
    'website': 'http://www.metrotowtrucks.com',
    'depends': ["metro", "sale", "metro_stock", "product_manufacturer", "document", "mrp_operations", "procurement", "mrp","project"],
    'data': [
        'security/ir.model.access.csv',
        'security/mrp_security.xml',
        'res_config_view.xml',
        'wizard/work_order_cnc_line_done_view.xml',
        'wizard/wo_material_request_view.xml',
        'wizard/mo_actions_view.xml',
        'work_order_cnc_view.xml',
        'mrp_view.xml',
        'mrp_sequence.xml',
        'wizard/add_common_bom_view.xml',
        'wizard/bom_import_view.xml',
        'mrp_workflow.xml',
        'pdm.xml',
        'procurement_view.xml'
        
    ],
    'test': [],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
