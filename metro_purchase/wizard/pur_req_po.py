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

from openerp import netsvc
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp.osv import osv, fields
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP


class pur_req_po_line(osv.osv_memory):
    _name = "pur.req.po.line"
    _rec_name = 'product_id'

    _columns = {
        'wizard_id': fields.many2one('pur.req.po', string="Wizard"),
        'product_id': fields.many2one('product.product', 'Product', required=True),
        'supplier_id': fields.many2one('res.partner',string="Supplier",readonly=True),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),
                                    required=True),
        'product_qty_remain': fields.float('Quantity Remain',
                                           digits_compute=dp.get_precision('Product Unit of Measure'), required=True),
        'price_unit': fields.float('Unit Price', digits_compute=dp.get_precision('Product Price')),
        'product_uom_id': fields.many2one('product.uom', 'Product Unit of Measure', required=True),
        'date_required': fields.date('Date Required', required=True),
        # 'inv_qty': fields.float('Inventory'),
        'mfg_ids': fields.many2many('sale.product', string="MFG IDs"),
        'req_reason': fields.char('Reason and use', size=64),
        'req_line_id': fields.many2one('pur.req.line', 'Purchase Requisition'),
        'supplier_prod_id': fields.integer(string='Supplier Product ID', required=False),
        'supplier_prod_name': fields.char(string='Supplier Product Name', required=True),
        'supplier_prod_code': fields.char(string='Supplier Product Code', required=False),
        'supplier_delay': fields.integer(string='Supplier Lead Time', required=False),

        'uom_po_qty': fields.float('PO Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),
                                   required=True),
        'uom_po_qty_remain': fields.float('PO Quantity Remain',
                                          digits_compute=dp.get_precision('Product Unit of Measure'), required=True),
        'uom_po_price': fields.float('PO Unit Price', digits_compute=dp.get_precision('Product Price')),
        'uom_po_id': fields.many2one('product.uom', 'PO Unit of Measure', required=True, ),
        'uom_po_factor': fields.float('UOM Ratio', digits=(12, 4), )
    }
    _defaults = {
        'supplier_prod_name': ' ',
    }
    def _check_product_qty(self, cursor, user, ids, context=None):
        for line in self.browse(cursor, user, ids, context=context):
            #            if line.product_qty > line.product_qty_remain:
            #                raise osv.except_osv(_('Warning!'), _("Product '%s' max po quantity is %s, you can not purchae %s"%(line.product_id.default_code + '-' + line.product_id.name, line.product_qty_remain, line.product_qty)))
            if line.uom_po_qty > line.uom_po_qty_remain:
                raise osv.except_osv(_('Warning!'), _("Product '%s' max po quantity is %s, you can not purchae %s" % (
                line.product_id.default_code + '-' + line.product_id.name, line.uom_po_qty_remain, line.uom_po_qty)))
        return True

    _constraints = [(_check_product_qty, 'Product quantity exceeds the remaining quantity', ['product_qty'])]

    def onchange_lead(self, cr, uid, ids, change_type, changes_value, context=None):
        date_order = fields.date.context_today(self, cr, uid, context=context)
        res = {'value': {}}
        if change_type == 'date_required':
            supplier_delay = datetime.strptime(changes_value, DEFAULT_SERVER_DATE_FORMAT) - datetime.strptime(
                date_order, DEFAULT_SERVER_DATE_FORMAT)
            res['value'] = {'supplier_delay': supplier_delay.days}
        if change_type == 'supplier_delay':
            date_required = datetime.strptime(date_order, DEFAULT_SERVER_DATE_FORMAT) + relativedelta(
                days=changes_value)
            date_required = datetime.strftime(date_required, DEFAULT_SERVER_DATE_FORMAT)
            res['value'].update({'date_required': date_required})
        return res

        # write the product supplier information

    def _update_prod_supplier(self, cr, uid, ids, vals, context=None):
        if vals.has_key('supplier_prod_name') or vals.has_key('supplier_prod_code') or vals.has_key('supplier_delay'):
            prod_supp_obj = self.pool.get('product.supplierinfo')
            new_vals = {'min_qty': 0}
            if vals.has_key('supplier_prod_name'):
                new_vals.update({'product_name': vals['supplier_prod_name']})
            if vals.has_key('supplier_prod_code'):
                new_vals.update({'product_code': vals['supplier_prod_code']})
            if vals.has_key('supplier_delay'):
                new_vals.update({'delay': vals['supplier_delay']})
            # for the metro_currency module, set the currency
            user = self.pool.get("res.users").browse(cr, uid, uid, context=context)
            if ids:
                # from order line update
                for line in self.browse(cr, uid, ids, context=context):
                    new_vals.update(
                        {'name': line.wizard_id.partner_id.id, 'product_id': line.product_id.product_tmpl_id.id,
                         'currency': user.company_id.currency_id.id})
                    if line.supplier_prod_id:
                        # update the prodcut supplier info
                        prod_supp_obj.write(cr, uid, line.supplier_prod_id, new_vals, context=context)
                    else:
                        supplier_prod_id = prod_supp_obj.create(cr, uid, new_vals, context=context)
            else:
                # from order line create
                po = self.pool.get('pur.req.po').browse(cr, uid, vals['wizard_id'])
                product = self.pool.get('product.product').browse(cr, uid, vals['product_id'], context=context)
                new_vals.update({'name': po.partner_id.id, 'product_id': product.product_tmpl_id.id,
                                 'currency': user.company_id.currency_id.id})
                prod_supp_ids = prod_supp_obj.search(cr, uid, [('product_id', '=', new_vals['product_id']),
                                                               ('name', '=', new_vals['name'])])
                if prod_supp_ids and len(prod_supp_ids) > 0:
                    # update the prodcut supplier info
                    prod_supp_obj.write(cr, uid, prod_supp_ids[0], new_vals, context=context)
                else:
                    supplier_prod_id = prod_supp_obj.create(cr, uid, new_vals, context=context)

    def create(self, cr, user, vals, context=None):
        # check the product supplier info
        if not vals.has_key('supplier_prod_name') or vals['supplier_prod_name'] == '':
            product_name = \
            self.pool.get("product.product").read(cr, user, [vals['product_id']], ['name'], context=context)[0]['name']
            raise osv.except_osv(_('Error!'),
                                 _('The product supplier name is required to product .\n %s' % product_name))
        resu = super(pur_req_po_line, self).create(cr, user, vals, context=context)
        # update product supplier info
        self._update_prod_supplier(cr, user, [], vals, context)
        # if price_unit changed then update it to product_product.standard_price
        if vals.has_key('price_unit'):
            self.pool.get('product.product').write(cr, user, [vals['product_id']],
                                                   {'standard_price': vals['price_unit']}, context=context)
        return resu

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        # update product supplier info
        self._update_prod_supplier(cr, uid, ids, vals, context)
        # if price_unit changed then update it to product_product.standard_price
        if vals.has_key('price_unit'):
            self.pool.get('product.product').write(cr, uid, [pur_req_po_line.product_id.id],
                                                   {'standard_price': vals['price_unit']}, context=context)


pur_req_po_line()


class pur_req_po(osv.osv_memory):
    _name = 'pur.req.po'
    _description = 'Requisition\'s Purchase Order'
    _columns = {
        'pur_req_id': fields.many2one('pur.req',string='Purchase Requisition'),
        'line_ids': fields.one2many('pur.req.po.line', 'wizard_id', 'Products'),
        'partner_id': fields.many2one('res.partner', 'Supplier', required=True, domain=[('supplier', '=', True)]),
        'supplier_ids': fields.many2many("res.partner","pur_req_po_partner_rel","pur_req_po_id","partner_id",string='Suppliers'),
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
        line_data = []
        if context is None:
            context = {}
        res = super(pur_req_po, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        req_obj = self.pool.get('pur.req')
        req = req_obj.browse(cr, uid, record_id, context=context)
        partner_id = None
        if req:
            uom_obj = self.pool.get('product.uom')
            supplier_ids = []
            for line in req.line_ids:
                # if not line.generated_po and line.product_qty_remain > 0:
                #     uom_po_qty = uom_obj._compute_qty_obj(cr, uid, line.product_uom_id, line.product_qty_remain,
                #                                           line.product_id.uom_po_id, context=context)
                #     uom_po_factor = line.product_id.uom_po_factor / line.product_uom_id.factor_display
                #     mfg_ids = line.mfg_ids and [mfg_id.id for mfg_id in line.mfg_ids] or []
                #     mfg_ids = [[6, False, mfg_ids]]
                #     line_data.append({'product_id': line.product_id.id,
                #                       'supplier_id': line.supplier_id.id,
                #                       'product_qty_remain': line.product_qty_remain,
                #                       'product_qty': line.product_qty_remain,
                #                       'product_uom_id': line.product_uom_id.id,
                #                       'price_unit': line.product_id.standard_price,
                #
                #                       'uom_po_qty_remain': uom_po_qty,
                #                       'uom_po_qty': uom_po_qty,
                #                       'uom_po_id': line.product_id.uom_po_id.id,
                #                       'uom_po_price': line.product_id.uom_po_price,
                #                       'uom_po_factor': uom_po_factor,
                #
                #                       'inv_qty': line.product_id.qty_available,
                #                       'date_required': line.date_required,
                #                       'req_line_id': line.id,
                #                       'req_reason': line.req_reason,
                #                       'mfg_ids': mfg_ids
                #                       })
                if line.supplier_id:
                    if line.supplier_id.id not in supplier_ids and line.product_qty_remain > 0:
                        supplier_ids.append(line.supplier_id.id)
                    #if partner_id == None and line.product_id.seller_id.active:
                    #    partner_id = line.product_id.seller_id.id

            res.update({'pur_req_id': req.id,'line_ids': line_data, 'partner_id': partner_id,
                        'supplier_ids': [[6,False,supplier_ids]]})
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
        res = super(pur_req_po, self).view_init(cr, uid, fields_list, context=context)
        record_id = context and context.get('active_id', False)
        if record_id:
            req_obj = self.pool.get('pur.req')
            req = req_obj.browse(cr, uid, record_id, context=context)
            if req.state == 'draft':
                raise osv.except_osv(_('Warning!'),
                                     _("You may only generate purchase orders based on confirmed requisitions!"))
            valid_lines = 0
            for line in req.line_ids:
                if line.product_qty_remain > 0.0:
                    valid_lines += 1
            if not valid_lines:
                raise osv.except_osv(_('Warning!'), _("No available products need to generate purchase order!"))
        return res

    #HoangTK - this function is override in metro_mrp_drawing to add pr information
    def _create_po(self, cr, uid, ids, context=None):
        record_id = context and context.get('active_id', False) or False
        data = self.browse(cr, uid, ids, context=context)[0]
        req = self.pool.get('pur.req').browse(cr, uid, record_id, context=None);
        po_data = {'origin': req.name, 'req_id': record_id, 'partner_id': data.partner_id.id,
                   'warehouse_id': req.warehouse_id.id, 'notes': req.remark, 'company_id': req.company_id.id,
                   'lines': []}
        po_lines = []
        for line in data.line_ids:
            po_line = {'product_id': line.product_id.id, 'product_qty': line.uom_po_qty,
                       'product_uom': line.uom_po_id.id,
                       'req_line_id': line.req_line_id.id, 'date_planned': line.date_required,
                       'price_unit': line.uom_po_price,
                       'name': (line.req_reason or ''),
                       'supplier_prod_id': line.supplier_prod_id, 'supplier_prod_name': line.supplier_prod_name,
                       'supplier_prod_code': line.supplier_prod_code, 'supplier_delay': line.supplier_delay}
            # update mfg_ids
            mfg_ids = line.mfg_ids and [mfg_id.id for mfg_id in line.mfg_ids] or []
            procurement_id = line.req_line_id.procurement_ids and line.req_line_id.procurement_ids[0] or False
            if procurement_id:
                if procurement_id.move_id:
                    # add the move_dest_id for the po_line
                    po_line.update({'move_dest_id': procurement_id.move_id.id})
                if procurement_id.mfg_ids and len(procurement_id.mfg_ids) > 0:
                    mfg_ids.extend([mfg_id.id for mfg_id in procurement_id.mfg_ids])
            if mfg_ids:
                po_line.update({'mfg_ids': [[6, False, mfg_ids]]})
            po_lines.append(po_line)
        if not po_lines:
            raise osv.except_osv(_('Error!'), _("Nothing to generate PO!"))
        po_data['lines'] = po_lines
        # call purchase.oder to generate order
        ret_po = self.pool.get('purchase.order').new_po(cr, uid, [po_data], context=context)
        # set req status to in_purchase
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'pur.req', record_id, 'pur_req_purchase', cr)
        # the 'po_id','po_line_id' should be pushed in the purchase.order.make_po() method
        return po_data['new_po_id']

    def create_view_po(self, cr, uid, ids, context=None):
        record_id = context and context.get('active_id', False) or False
        self._create_po(cr, uid, ids, context=context)
        return {
            'domain': "[('req_id', 'in', [" + str(record_id) + "])]",
            'name': _('Purchase Order'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'purchase.order',
            'type': 'ir.actions.act_window',
            'context': context,
        }

    def create_po(self, cr, uid, ids, context=None):
        self._create_po(cr, uid, ids, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def onchange_partner(self, cr, uid, ids, pur_req_id, partner_id, context):
        #prod_supp_obj = self.pool.get('product.supplierinfo')
        line_data = []
        if pur_req_id and partner_id:
            req_obj = self.pool.get('pur.req')
            req = req_obj.browse(cr, uid, pur_req_id, context=context)
            if req:
                uom_obj = self.pool.get('product.uom')
                supplier_ids = []
                for line in req.line_ids:
                    if line.supplier_id:
                        if not line.generated_po and line.product_qty_remain > 0 and line.supplier_id.id == partner_id:
                            uom_po_qty = uom_obj._compute_qty_obj(cr, uid, line.product_uom_id, line.product_qty_remain,
                                                                  line.product_id.uom_po_id, context=context)
                            uom_po_factor = line.product_id.uom_po_factor / line.product_uom_id.factor_display
                            #mfg_ids = line.mfg_ids and [mfg_id.id for mfg_id in line.mfg_ids] or []
                            #mfg_ids = [[6, False, mfg_ids]]
                            line_data.append({'product_id': line.product_id.id,
                                              'supplier_id': line.supplier_id.id,
                                              'product_qty_remain': line.product_qty_remain,
                                              'product_qty': line.product_qty_remain,
                                              'product_uom_id': line.product_uom_id.id,
                                              'price_unit': line.product_id.standard_price,

                                              'uom_po_qty_remain': uom_po_qty,
                                              'uom_po_qty': uom_po_qty,
                                              'uom_po_id': line.product_id.uom_po_id.id,
                                              'uom_po_price': line.product_id.uom_po_price,
                                              'uom_po_factor': uom_po_factor,

                                              #'inv_qty': line.product_id.qty_available,
                                              'date_required': line.date_required,
                                              'req_line_id': line.id,
                                              'req_reason': line.req_reason,
                                              #'mfg_ids': mfg_ids
                                              })
        #for line in lines:
        #    if not line[2]:
        #        continue
        #    line_dict = line[2]
            # update the product supplier info
            #prod_supp_ids = prod_supp_obj.search(cr, uid, [('product_id', '=', line_dict['product_id']),
            #                                               ('name', '=', partner_id)])
            #if prod_supp_ids and len(prod_supp_ids) > 0:
            #    prod_supp = prod_supp_obj.browse(cr, uid, prod_supp_ids[0], context=context)
            #    line_dict.update({'supplier_prod_id': prod_supp.id,
            #                      'supplier_prod_name': prod_supp.product_name,
            #                      'supplier_prod_code': prod_supp.product_code,
            #                      'supplier_delay': prod_supp.delay})
            #else:
            #if line_dict['supplier_id'] != partner_id:
                #line_dict.update({'supplier_prod_id': False,
                #                  'supplier_prod_name': '',
                #                  'supplier_prod_code': '',
                #                  'supplier_delay': 1})
                #line_rets.append(line_dict)
        return {'value': {'line_ids': line_data}}


pur_req_po()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
