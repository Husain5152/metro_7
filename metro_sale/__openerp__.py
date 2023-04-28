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
    'name': 'Metro Sale',
    'version': '1.0',
    'category': 'Metro',
    'description': """
    
        Metro Sale Extension:  
        
        1.Add Sales Payment function
        
        (Ported to OpenERP v 7.0 by Metro Tower Trucks.
        
        """,
        
        
    'author': 'Metro Tower Trucks',
    'website': 'http://www.metrotowtrucks.com',
    'depends': ["metro", "sale", "sale_stock", "sale_quick_payment", "sale_exceptions","stock","mrp","metro_serial","metro_mto",'project'],
    'data': [
        'security/ir.model.access.csv',
        'sale_metro_view.xml',
        'sale_payment_view.xml',
        'sale_workflow.xml',
        'sale_report.xml',
        'sale_product_view.xml',
        'crm_view.xml',
        'sale_product_workflow.xml',
        'sale_product_sequence.xml',
        'sale_data.xml'
    ],
    'test': [],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
