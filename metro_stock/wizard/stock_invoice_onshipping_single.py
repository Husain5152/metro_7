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

from openerp.osv import fields, osv
from openerp import netsvc

from openerp.tools.translate import _
class stock_invoice_move(osv.osv_memory):
    _name = "stock.invoice.move"
    _columns = {
        'order_id': fields.many2one('stock.invoice.onshipping.single', string='Order',required=True,ondelete='cascade'),
        'move_id': fields.many2one('stock.move', string='Move Line',required=True),
        'product_id': fields.many2one('product.product', string='Product',readonly=True),
        'product_qty': fields.float('Quantity',type='float',readonly=True),
        'product_uom': fields.many2one('product.uom',string='Unit of Measure',readonly=True),
#        'price_unit': fields.many2one('stock.move', string='Picking Line',required=True),
        'price_unit': fields.float('Unit Price'),
    }    
    
class stock_invoice_onshipping_single(osv.osv_memory):

    def _get_journal(self, cr, uid, context=None):
        res = self._get_journal_id(cr, uid, context=context)
        if res:
            return res[0][0]
        return False

    def _get_journal_id(self, cr, uid, context=None):
        if context is None:
            context = {}

        model = context.get('active_model')
        if not model or 'stock.picking' not in model:
            return []

        model_pool = self.pool.get(model)
        journal_obj = self.pool.get('account.journal')
        res_ids = context and context.get('active_ids', [])
        vals = []
        browse_picking = model_pool.browse(cr, uid, res_ids, context=context)

        for pick in browse_picking:
            if not pick.move_lines:
                continue
            src_usage = pick.move_lines[0].location_id.usage
            dest_usage = pick.move_lines[0].location_dest_id.usage
            type = pick.type
            if type == 'out' and dest_usage == 'supplier':
                journal_type = 'purchase_refund'
            elif type == 'out' and dest_usage == 'customer':
                journal_type = 'sale'
            elif type == 'in' and src_usage == 'supplier':
                journal_type = 'purchase'
            elif type == 'in' and src_usage == 'customer':
                journal_type = 'sale_refund'
            else:
                journal_type = 'sale'

            value = journal_obj.search(cr, uid, [('type', '=',journal_type )])
            for jr_type in journal_obj.browse(cr, uid, value, context=context):
                t1 = jr_type.id,jr_type.name
                if t1 not in vals:
                    vals.append(t1)
        return vals

    _name = "stock.invoice.onshipping.single"
    _description = "Stock Invoice Onshipping"

    _columns = {
        'journal_id': fields.selection(_get_journal_id, 'Destination Journal',required=True),
        'group': fields.boolean("Group by partner"),
        'invoice_date': fields.date('Invoiced date'),
        'move_lines': fields.one2many('stock.invoice.move','order_id',string="Move Lines"),
        'journal_id': fields.selection(_get_journal_id, 'Destination Journal',required=True),
    }

    _defaults = {
        'journal_id' : _get_journal,
    }

    def view_init(self, cr, uid, fields_list, context=None):
        if context is None:
            context = {}
        res = super(stock_invoice_onshipping_single, self).view_init(cr, uid, fields_list, context=context)
        pick_obj = self.pool.get('stock.picking')
        count = 0
        active_ids = context.get('active_ids',[])
        for pick in pick_obj.browse(cr, uid, active_ids, context=context):
            if pick.invoice_state != '2binvoiced':
                count += 1
        if len(active_ids) == 1 and count:
            raise osv.except_osv(_('Warning!'), _('This picking list does not require invoicing.'))
        if len(active_ids) == count:
            raise osv.except_osv(_('Warning!'), _('None of these picking lists require invoicing.'))
        return res
    
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
        line_data = []
        if context is None:
            context = {}
        res = super(stock_invoice_onshipping_single, self).default_get(cr, uid, fields, context=context)
        active_id = context and context.get('active_id', False) or False
        active_obj = self.pool.get('stock.picking')
        active_data = active_obj.browse(cr, uid, active_id, context=context)
        if active_data:             
            for line in active_data.move_lines:
                line_data.append({'move_id': line.id, 'product_id':line.product_id.id, 'product_qty':line.product_qty,'product_uom':line.product_uom.id,
                                  'price_unit':line.purchase_line_id and line.purchase_line_id.price_unit or line.price_unit})
            res.update({'move_lines': line_data})
        return res
    
    
    def open_invoice_valid(self, cr, uid, ids, context=None):
        return self.exec_action(cr, uid, ids, True, False, context)
        
    def open_invoice_valid_pay(self, cr, uid, ids, context=None):
        return self.exec_action(cr, uid, ids, True, True, context)
    
    def open_invoice(self, cr, uid, ids, context=None):
        return self.exec_action(cr, uid, ids, False, False, context)
    
    def exec_action(self, cr, uid, ids, valid=False, pay=False, context=None):
        if context is None:
            context = {}
        invoice_ids = []
        #update the stock move unit price
        move_obj = self.pool.get('stock.move')
        for data in self.browse(cr, uid, ids, context=context):
            for move_line in data.move_lines:
                if move_line.move_id.price_unit != move_line.price_unit:
                    move_obj.write(cr, uid, move_line.move_id.id, {'price_unit':move_line.price_unit}, context=context)
        #create invoice            
        res = self.create_invoice(cr, uid, ids, context=context)
        invoice_ids += res.values()
        #auto validate the invoice
        if valid:
            wf_service = netsvc.LocalService("workflow")
            for invoice_id in invoice_ids:
                wf_service.trg_validate(uid, 'account.invoice', invoice_id, 'invoice_open', cr)
        if pay:
            return self.pool.get('account.invoice').invoice_pay_customer(cr, uid, invoice_ids, context=context)                        
        else:
            return self.view_invoice(cr, uid, invoice_ids, context=context)
            
    def create_invoice(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        picking_pool = self.pool.get('stock.picking')
        onshipdata_obj = self.read(cr, uid, ids, ['journal_id', 'group', 'invoice_date'])
        if context.get('new_picking', False):
            onshipdata_obj['id'] = onshipdata_obj.new_picking
            onshipdata_obj[ids] = onshipdata_obj.new_picking
        context['date_inv'] = onshipdata_obj[0]['invoice_date']
        active_ids = context.get('active_ids', [])
        active_picking = picking_pool.browse(cr, uid, context.get('active_id',False), context=context)
        inv_type = picking_pool._get_invoice_type(active_picking)
        context['inv_type'] = inv_type
        if isinstance(onshipdata_obj[0]['journal_id'], tuple):
            onshipdata_obj[0]['journal_id'] = onshipdata_obj[0]['journal_id'][0]
        res = picking_pool.action_invoice_create(cr, uid, active_ids,
              journal_id = onshipdata_obj[0]['journal_id'],
              group = onshipdata_obj[0]['group'],
              type = inv_type,
              context=context)
        return res
        
    def view_invoice(self, cr, uid, invoice_ids, context=None):
        action_model = False
        action = {}
        if not invoice_ids:
            raise osv.except_osv(_('Error!'), _('Please create Invoices.'))
        inv_type = context.get('inv_type', False)
        if not inv_type:
            inv_type = self.pool.get('account.invoice').read(cr, uid, invoice_ids[0], ['type'], context=context)['type']
        data_pool = self.pool.get('ir.model.data')
        if len(invoice_ids) == 1:
            invoice_id = invoice_ids[0]
            type_names = { 'out_invoice':'Customer Invoices',
                                'in_invoice':'Supplier Invoices',
                                'out_refund':'Customer Refunds',
                                'in_refund':'Supplier Refunds'}
            type_forms = { 'out_invoice':'invoice_form',
                                'in_invoice':'invoice_supplier_form',
                                'out_refund':'invoice_form',
                                'in_refund':'invoice_supplier_form'}
            #go to the invoice view page
            mod_obj = self.pool.get('ir.model.data')
            form_view = data_pool.get_object_reference(cr, uid, 'account', type_forms[inv_type])
            form_view_id = form_view and form_view[1] or False
            return {
                'name': _(type_names[inv_type]),
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [form_view_id],
                'res_model': 'account.invoice',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': invoice_id,
            }            
        else:
            if inv_type == "out_invoice":
                action_model,action_id = data_pool.get_object_reference(cr, uid, 'account', "action_invoice_tree1")
            elif inv_type == "in_invoice":
                action_model,action_id = data_pool.get_object_reference(cr, uid, 'account', "action_invoice_tree2")
            elif inv_type == "out_refund":
                action_model,action_id = data_pool.get_object_reference(cr, uid, 'account', "action_invoice_tree3")
            elif inv_type == "in_refund":
                action_model,action_id = data_pool.get_object_reference(cr, uid, 'account', "action_invoice_tree4")
            if action_model:
                action_pool = self.pool.get(action_model)
                action = action_pool.read(cr, uid, action_id, context=context)
                action['domain'] = "[('id','in', ["+','.join(map(str,invoice_ids))+"])]"
            return action

stock_invoice_onshipping_single()

class account_voucher(osv.osv):
    _inherit="account.voucher"
    def button_proforma_voucher(self, cr, uid, ids, context=None):
        resu = super(account_voucher,self).button_proforma_voucher(cr, uid, ids, context=context)
        if context.get('active_model',False) \
            and context.get('invoice_id',False) \
            and context['active_model'] == 'stock.invoice.onshipping.single':
            return self.pool.get('stock.invoice.onshipping.single').view_invoice(cr, uid, [context['invoice_id']],context=context)
        else:
            return resu
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
