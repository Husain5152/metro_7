# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp import netsvc

class link_po_to_pr_wizard(osv.osv_memory):
    _name = 'link.po.to.pr.wizard'
    _description = 'Link PO TO PR Wizard'
    _columns = {
        'po_id': fields.many2one('purchase.order','Purchase Order',readonly=True),
        'pr_id': fields.many2one('pur.req', 'Purchase requisition',required=True),
    }
    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(link_po_to_pr_wizard, self).default_get(cr, uid, fields, context=context)
        active_model = context and context.get('active_model', False) or False
        active_id = context and context.get('active_id', False) or False
        if active_model == 'purchase.order' and active_id:
            res.update({'po_id': active_id})
        return res

    def do_link(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids, context)[0]
        if wizard.po_id and wizard.pr_id:
            po_id = wizard.po_id
            pr_id = wizard.pr_id
            if po_id.state != 'draft':
                raise osv.except_osv(_('Invalid Action!'), _('Only draft order can link to PR.'))
            #TODO : Check if PO can link to PR, if OK do the link
            pr_supplier_ids_dict = {}
            for line in pr_id.line_ids:
                if line.supplier_id:
                    pr_supplier_ids_dict.update({line.supplier_id.id: True})
            pr_supplier_ids = pr_supplier_ids_dict.keys()
            same_supplier = False
            if po_id.partner_id:
                if po_id.partner_id.id in pr_supplier_ids:
                    same_supplier = True
            if not same_supplier:
                raise osv.except_osv(_('Invalid Action!'), _('Supplier not exist in PR.'))
            partner_id = po_id.partner_id.id
            po_products = {}
            pr_products = {}
            same_product_line = True
            for line in pr_id.line_ids:
                if line.supplier_id:
                    if line.supplier_id.id == partner_id:
                        pr_products.update({
                            line.product_id.id : {'line_id': line.id, 'qty': line.product_qty_remain}
                        })
            for line in po_id.order_line:
                po_products.update({
                    line.product_id.id : {'line_id': line.id, 'qty': line.product_qty},
                })
                if line.product_id.id not in pr_products:
                    same_product_line = False
                    break
            if not same_product_line:
                raise osv.except_osv(_('Invalid Action!'), _('Some PO products not exist in PR.'))
            # DO Link
            # Update PO with PR data
            po_obj = self.pool.get('purchase.order')
            po_line_obj = self.pool.get('purchase.order.line')
            pr_obj = self.pool.get('pur.req')
            po_obj.write(cr, uid, [po_id.id],{
                    'origin': pr_id.name,
                   'req_id': pr_id.id,
                   'notes': po_id.notes and po_id.notes + '\n' + pr_id.remark or pr_id.remark,
            })
            # Update each PO lines
            for product_id in po_products:
                po_line_obj.write(cr, uid, [po_products[product_id]['line_id']],{
                    'req_line_id': pr_products[product_id]['line_id']
                })
            # set req status to in_purchase
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'pur.req', pr_id.id, 'pur_req_purchase', cr)
        return True




