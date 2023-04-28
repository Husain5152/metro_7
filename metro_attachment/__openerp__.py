# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012-Today Acespritech Solutions Pvt Ltd
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
    'name': 'Metro Attachment',
    'version': '1.0',
    'category': 'Metro',
    'sequence': 500,
    'description': """
    Add default products to sales order
    """,
    'author': 'Acespritech Solutions Pvt Ltd',
    'website': 'http://www.acespritech.com',
    'depends': ['base', 'sale', 'hr', 'document', 'metro_shipping', 'metro_product', 'metro_mto'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'base/ir_attachment_view.xml',
        'product/product_view.xml',
        'hr/hr_view.xml',
        'sale/sale_view.xml',
        'ship/shipment_view.xml',
        'mto/mto_design_view.xml',
        'project/project_view.xml',
        'account/account_view.xml',
    ],
    'installable': True,
    'active': False,
    'application': True,
}
