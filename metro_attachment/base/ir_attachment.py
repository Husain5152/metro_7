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
from openerp.osv import fields, osv


class ir_attachment_type(osv.osv):
    _name = "ir.attachment.type"
    _columns = {
        'name': fields.char('Name', size=256),
    }
ir_attachment_type()


class ir_attachment(osv.osv):
    _inherit = "ir.attachment"
    _columns = {
        'product_id': fields.many2one('product.product', 'Product'),
        'employee_id': fields.many2one('hr.employee', 'Employee'),
        'sale_order_id': fields.many2one('sale.order', 'Sale Order'),
        'project_issue_id': fields.many2one('project.issue', 'Project Issue'),
        'shipment_id': fields.many2one('shipment.shipment', 'Shipment'),
        'mto_design_id': fields.many2one('mto.design', 'Product Configuration'),
        'project_project_id': fields.many2one('project.project', 'Project'),
        'project_task_id': fields.many2one('project.task', 'Project'),
        'account_move_id': fields.many2one('account.move', 'Account Entry'),
        'attach_type_id': fields.many2one('ir.attachment.type',
                                          'Attachment Type'),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form',
                        context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}
        if view_type == 'form' and context.get('o2m_attach'):
            view_id = self.pool.get('ir.ui.view').search(cr, uid,
                                    [('name', '=', 'acespritech.ir.attachment.form')])
            if view_id and isinstance(view_id, (list, tuple)):
                view_id = view_id[0]
        return super(ir_attachment, self).fields_view_get(cr, uid, view_id,
                                        view_type, context, toolbar=toolbar,
                                        submenu=submenu)

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if vals.get('product_id'):
            vals['res_id'] = vals['product_id']
            vals['res_model'] = 'product.product'
        if vals.get('employee_id'):
            vals['res_id'] = vals['employee_id']
            vals['res_model'] = 'hr.employee'
        if vals.get('sale_order_id'):
            vals['res_id'] = vals['sale_order_id']
            vals['res_model'] = 'sale.order'   
        if vals.get('project_issue_id'):
            vals['res_id'] = vals['project_issue_id']
            vals['res_model'] = 'project.issue'  
        if vals.get('shipment_id'):
            vals['res_id'] = vals['shipment_id']
            vals['res_model'] = 'shipment.shipment'  
        if vals.get('mto_design_id'):
            vals['res_id'] = vals['mto_design_id']
            vals['res_model'] = 'mto.design'
        if vals.get('project_project_id'):
            vals['res_id'] = vals['project_project_id']
            vals['res_model'] = 'project.project'
        if vals.get('project_task_id'):
            vals['res_id'] = vals['project_task_id']
            vals['res_model'] = 'project.task'       
        if vals.get('account_move_id'):
            vals['res_id'] = vals['account_move_id']
            vals['res_model'] = 'account.move'                
            
        return super(ir_attachment, self).create(cr, uid, vals, context)

ir_attachment()
