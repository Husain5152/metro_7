# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp.osv import osv,fields
from openerp.tools.translate import _
import openerp.tools as tools
import openerp.addons.decimal_precision as dp
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP

class pur_invoice_line(osv.osv_memory):
    _name = "pur.invoice.line"
    _rec_name = 'product_id'

    _columns = {
        'wizard_id' : fields.many2one('pur.invoice', string="Wizard"),
        'po_line_id': fields.many2one('purchase.order.line','PO Order Line ID' ,required=True,readonly=True),
        'product_id': fields.many2one('product.product', 'Product' ,required=True,readonly=True),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),required=True),
        'product_max_qty': fields.float('Max Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),required=True,readonly=True),
        'price_unit': fields.float('Unit Price', digits_compute= dp.get_precision('Product Price'),readonly=True),
        'product_uom_id': fields.many2one('product.uom', 'Product Unit of Measure',required=True,readonly=True),     
    }
    def create(self, cr, user, vals, context=None):
        if vals['product_qty'] > vals['product_max_qty']:
#            prod_name = tools.ustr(self.pool.get('product.product').name_get(cr,user,vals['product_id'],context)[0])
            prod_name = self.pool.get('product.product').read(cr,user,vals['product_id'],['name'],context)['name']
            raise osv.except_osv(_('Error!'), _('Invoice quantity(%s) can not bigger than the max quantity(%s)!\n%s') % (vals['product_qty'],vals['product_max_qty'],prod_name,))
        resu = super(pur_invoice_line,self).create(cr, user, vals, context=context)      
        return resu                         
    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        line = self.browse(cr, uid, ids[0], context)
        if vals['product_qty'] and vals['product_qty'] > line.product_max_qty:
            raise osv.except_osv(_('Error!'), _('Invoice quantity can not bigger than the max quantity!\n%s') % (line.product_id.name,))
        return super(pur_invoice_line,self).write(cr, uid, ids, vals, context)

class pur_invoice(osv.osv_memory):
    _name = 'pur.invoice'
    _description = 'Purchase Order''s Invoice Creation'
    _columns = {
        'po_id': fields.many2one('purchase.order','PO Order ID' ,required=True,readonly=True),
        'line_ids' : fields.one2many('pur.invoice.line', 'wizard_id', 'Prodcuts'),
    }

    def default_get(self, cr, uid, fields, context=None):
        """
         To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary with default values for all field in ``fields``
        """
        if context is None:
            context = {}
        res = super(pur_invoice, self).default_get(cr, uid, fields, context=context)
        order_id = context and context.get('active_id', False) or False
        if order_id:   
            res.update({'po_id':order_id})
            order_obj = self.pool.get('purchase.order')
            order = order_obj.browse(cr, uid, order_id, context=context)
            line_data = []
            for line in order.order_line:
                #check if this line have quantity to generate invoice, by johnw
                if line.product_qty <= line.invoice_qty:
                    continue
                to_inv_qty = line.product_qty - line.invoice_qty
                line_data.append({'product_id': line.product_id.id, 'product_qty': to_inv_qty, 'product_max_qty': to_inv_qty, 
                                  'price_unit':line.price_unit, 'product_uom_id':line.product_uom.id, 'po_line_id': line.id})
            res.update({'line_ids': line_data})
                        
        return res

    def view_init(self, cr, uid, fields_list, context=None):
        """
         Creates view dynamically and adding fields at runtime.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param context: A standard dictionary
         @return: New arch of view with new columns.
        """
        if context is None:
            context = {}
        res = super(pur_invoice, self).view_init(cr, uid, fields_list, context=context)
        order_id = context and context.get('active_id', False) or False
        if order_id:   
            order_obj = self.pool.get('purchase.order')
            order = order_obj.browse(cr, uid, order_id, context=context)
            if order.state != 'approved':
                raise osv.except_osv(_('Warning!'), _("You may only create invoices based on approved purchase orders!"))
            

            line_data = []
            for line in order.order_line:
                #check if this line have quantity to generate invoice, by johnw
                if line.product_qty <= line.invoice_qty:
                    continue
                line_data.append(line.id)
            if len(line_data) == 0:
                raise osv.except_osv(_('Warning!'), _("No available products need to generate invoice!"))
        return res  
        
    def _create_invoice(self, cr, uid, ids, context=None):
        """Generates invoice for given ids of purchase orders and links that invoice ID to purchase order.
        :param ids: list of ids of purchase orders.
        :return: ID of created invoice.
        :rtype: int
        """
        res = False

        journal_obj = self.pool.get('account.journal')
        inv_obj = self.pool.get('account.invoice')
        inv_line_obj = self.pool.get('account.invoice.line')
        fiscal_obj = self.pool.get('account.fiscal.position')
        po_obj = self.pool.get('purchase.order')
        for pur_invoice in self.browse(cr, uid, ids, context=context):
            order = pur_invoice.po_id
            #use a new method to get the account_id
            pay_acc_id = po_obj._get_inv_pay_acc_id(cr,uid,order)                
            journal_ids = journal_obj.search(cr, uid, [('type', '=','purchase'),('company_id', '=', order.company_id.id)], limit=1)
            if not journal_ids:
                raise osv.except_osv(_('Error!'),
                    _('Define purchase journal for this company: "%s" (id:%d).') % (order.company_id.name, order.company_id.id))

            # generate invoice line correspond to PO line and link that to created invoice (inv_id) and PO line
            inv_lines = []
            for pur_invoice_line in pur_invoice.line_ids:
                po_line = pur_invoice_line.po_line_id
                #use a new method to get the account_id, by johnw          
                acc_id = po_obj._get_inv_line_exp_acc_id(cr,uid,order,po_line)
                fpos = order.fiscal_position or False
                acc_id = fiscal_obj.map_account(cr, uid, fpos, acc_id)

                inv_line_data = po_obj._prepare_inv_line(cr, uid, acc_id, po_line, context=context)
                #update the quantity to the quantity, by johnw
                inv_line_data.update({'quantity':(pur_invoice_line.product_qty)})
                inv_line_id = inv_line_obj.create(cr, uid, inv_line_data, context=context)
                inv_lines.append(inv_line_id)

                po_line.write({'invoiced':True, 'invoice_lines': [(4, inv_line_id)]}, context=context)
            
            #if no lines then return direct, by johnw
            if len(inv_lines) == 0:
                continue
            
            # get invoice data and create invoice
            inv_data = {
                'name': order.partner_ref or order.name,
                'reference': order.partner_ref or order.name,
                'account_id': pay_acc_id,
                'type': 'in_invoice',
                'partner_id': order.partner_id.id,
                'currency_id': order.pricelist_id.currency_id.id,
                'journal_id': len(journal_ids) and journal_ids[0] or False,
                'invoice_line': [(6, 0, inv_lines)],
                'origin': order.name,
                'fiscal_position': order.fiscal_position.id or False,
                'payment_term': order.payment_term_id.id or False,
                'company_id': order.company_id.id,
                'comment': order.notes,
            }
            inv_id = inv_obj.create(cr, uid, inv_data, context=context)

            # compute the invoice
            inv_obj.button_compute(cr, uid, [inv_id], context=context, set_total=True)

            # Link this new invoice to related purchase order
            order.write({'invoice_ids': [(4, inv_id)]}, context=context)
            res = inv_id
        return res    

    def create_view_invoice(self, cr, uid, ids, context=None): 
        record_id = context and context.get('active_id', False) or False
        inv_id = self._create_invoice(cr,uid,ids,context=context) 
        #go to the invoice view page
        mod_obj = self.pool.get('ir.model.data')
        res = mod_obj.get_object_reference(cr, uid, 'account', 'invoice_supplier_form')
        res_id = res and res[1] or False
        return {
            'name': _('Supplier Invoices'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'res_model': 'account.invoice',
            'context': "{'type':'in_invoice', 'journal_type': 'purchase'}",
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': inv_id,
        }
    def create_invoice(self, cr, uid, ids, context=None): 
        self._create_invoice(cr,uid,ids,context=context) 
        return {'type': 'ir.actions.act_window_close'}  

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
