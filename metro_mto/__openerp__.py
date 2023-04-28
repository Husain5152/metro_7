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
    'name': 'Metro MTO',
    'version': '1.0',
    'category': 'Metro',
    'description': """
    
        Metro Make to Order Extension
        
        """,
        
        
    'author': 'Metro Tower Trucks',
    'website': 'http://www.metrotowtrucks.com',
    'depends': ["base_custom_attributes","base","product","multi_image"],
    'data': [
        'mto_sequence.xml',
        'security/ir.model.access.csv',
        'mto_attribute_view.xml',
        'mto_design_view.xml',
        'wizard/mto_design_wiz_view.xml',
        'mto_design_report.xml',
    ],
    'test': [],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
