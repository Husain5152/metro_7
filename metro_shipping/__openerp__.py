# -*- coding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 OpenERP SA (<http://www.openerp.com>)
#    Copyright (C) 2011-2013 Serpent Consulting Services Pvt. Ltd. (<http://www.serpentcs.com>).

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
    'name': 'Metro Shipping',
    'version': '1.0',
    'category': 'Metro',
    'description': """
    The point of this module is to track our shipments.  We ship from China and Canada at this time. 
    We will sometimes ship containers (like 40HC or 20GP) and other times we ship using

   normal couriors like DHL, UPS, FedEx etc...  I would like to leverage the new functionality in 
   OpenERP 7 which can customize a screen based on data that was entered earlier.
""",
    'author': 'Serpent Counsulting Services',
    'website': 'www.serpentcs.com',
    'depends': ['stock','multi_image', 'metro'],
    'data': [
        "security/metro_security.xml",
        "metro_shipping_view.xml",
        "security/ir.model.access.csv",
        "metro_workflow.xml",
        "wizard/future_shipment_req_view.xml",
        "future_shipping.xml",
        "ship_data.xml",
        "future_shipment_report.xml",
        
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: