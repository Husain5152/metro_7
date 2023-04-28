# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools

class confirm_set_pr_line_supplier_wizard(osv.osv_memory):
    _name = 'confirm.set.pr.line.supplier.wizard'
    _description = 'Confirm Set Supplier'
    _columns = {
        'supplier_id': fields.many2one('res.partner', 'Supplier'),
        'pr_line_ids': fields.many2many('pur.req.line',string='Purchase Requisition Lines'),
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(confirm_set_pr_line_supplier_wizard, self).default_get(cr, uid, fields, context=context)
        pr_line_ids = context and context.get('pr_line_ids', False) or False
        supplier_id = context and context.get('supplier_id', False) or False
        active_model = context and context.get('active_model', False) or False
        if pr_line_ids and active_model == 'set.pr.line.supplier.wizard':
            res.update({'pr_line_ids': [(6, False, pr_line_ids)],
                        'supplier_id': supplier_id})
        return res

    def do_ok(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids, context)[0]
        pr_line_ids = [line_id.id for line_id in wizard.pr_line_ids]
        req_pur_line_obj = self.pool.get('pur.req.line')
        if pr_line_ids and wizard.supplier_id:
            req_pur_line_obj.write(cr, uid, pr_line_ids, {'supplier_id': wizard.supplier_id.id})
        return {'type': 'ir.actions.act_window_close'}




