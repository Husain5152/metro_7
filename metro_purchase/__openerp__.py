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
    'name': 'Metro Purchase',
    'version': '1.0',
    'category': 'Metro',
    'description': """
    
        Metro Purchase Extension:  
        
        1.Add Purchase requisition function
        2.Add the manager approval state to purchase order
        
        (Ported to OpenERP v 7.0 by Metro Tower Trucks.
        
        """,
        
        
    'author': 'Metro Tower Trucks',
    'website': 'http://www.metrotowtrucks.com',
    'depends': ["metro", "purchase", "sale_payment_method", "account_prepayment", "procurement", "metro_sale", "metro_product"],
    'data': [
        'wizard/pur_req_po.xml',
        'wizard/confirm_msg.xml',
        'wizard/pur_history.xml',    
        'wizard/pay_po.xml',
        'wizard/pur_invoice.xml',
        'wizard/purchase_order_group.xml',
        'security/pur_req_security.xml',
        'security/ir.model.access.csv',
        'change_log_view.xml',
        'pur_req_workflow.xml',
        'pur_req_sequence.xml',
        'pur_req_report.xml',
        'purchase_workflow.xml',
        'purchase_view.xml',
        'purchase_data.xml',
        'purchase_email_template.xml',
        'purchase_report.xml',
        'pur_req_view.xml',
        'purchase_payment.xml',
        'procurement_workflow.xml',
        'procurement_view.xml',
    ],
    'test': [],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
