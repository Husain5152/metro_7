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
    'name': 'Metro Product',
    'version': '1.0',
    'category': 'Metro',
    'description': """
    
        Metro Product Extension:  
        
        Updates the Product module to create automatic part numbers, adds a Chinese name field and a details tab.
        
        (Ported to OpenERP v 7.0 by PY Solutions.
        
        """,
        
        
    'author': 'IntellectSeed Technologies, PY Solutions',
    'maintainer': 'PY Solutions',
    'website': 'http://www.intellectseed.com, http://www.pysolutions.com',
    'depends': ["metro", "product", "sale", "stock", "product_manufacturer", "purchase", "mrp","web_url"],
    'init_xml': [],
    'update_xml': [
        'product_view.xml',
        'product_uom_data.xml',
        'product_uom_view.xml',
        'security/ir.model.access.csv',
        'wizard/product_set_printflag.xml',
        'wizard/product_batch_query_view.xml',
        'wizard/products_approve.xml',
        'wizard/product_qty_location.xml',
        #'product_ir_cron_data.xml',
    ],
    'demo_xml': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
