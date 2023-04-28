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
    'name': 'Metro Stock',
    'version': '1.0',
    'category': 'Metro',
    'description': """
    
        Metro Stock Extension:  
        
        1.Add Material Request function
        
        (Ported to OpenERP v 7.0 by Metro Tower Trucks.
        
        """,
        
        
    'author': 'Metro Tower Trucks',
    'website': 'http://www.metrotowtrucks.com',
    'depends': ["metro", "metro_purchase","metro_sale","stock","product_fifo_lifo","stock_cancel"],
    'data': [
        'security/ir.model.access.csv',
        'wizard/stock_import_inventory_view.xml',
        'wizard/stock_move_inventory_view.xml',
        'wizard/stock_change_product_qty_view.xml',    
        'wizard/stock_return_picking_view.xml', 
        'wizard/stock_partial_picking_view.xml', 
        'wizard/stock_invoice_onshipping_single_view.xml',
        'wizard/stock_change_inventory_date_view.xml',
        'stock_view.xml',
        'stock_sequence.xml',
        'stock_wh_loc.xml',     
        'stock_barcode_view.xml',
        'stock_raw_material_view.xml',
        'stock_mt_rpt_view.xml',
    ],
    'test': [],
    'demo': [],
#    "js": ["static/src/js/metro_stock.js"],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
