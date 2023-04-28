# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.pur_req import PR_AVAILABLE_QTY_RULE

class calculate_pr_available_qty_wizard(osv.osv_memory):
    _name = 'calculate.pr.available.qty.wizard'
    _description = 'Calucate Available PR Quantity Wizard'
    _columns = {
        'pr_id': fields.many2one('pur.req','Purchase Requisition',readonly=True),
        'pr_line_ids': fields.many2many('pur.req.line',string='Purchase Requisition Lines', readonly=True),
        "available_qty_rule": fields.selection(PR_AVAILABLE_QTY_RULE, string='Remain Qty Rule'),
    }

    _defaults = {
        'available_qty_rule': 'REGARD_AVAILABLE_INCOMING'
    }
    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(calculate_pr_available_qty_wizard, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        record_ids = context and context.get('active_ids', False) or False
        record_model = context and context.get('active_model', False) or False
        if record_id and record_model == 'pur.req':
            res.update({'pr_id': record_id})
        elif record_model == 'pur.req.line':
            if record_ids:
                res.update({'pr_line_ids': [(6, False, record_ids)]})
            elif record_id:
                res.update({'pr_line_ids': [(6, False, [record_id])]})
        return res

    def do_calculate(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wizard = self.browse(cr, uid, ids, context)[0]
        req_pur_obj = self.pool.get('pur.req')
        pr_dict = {}
        if wizard.pr_id:
            if wizard.pr_id.state not in ['done','draft','reject','cancel']:
                pr_dict.update({wizard.pr_id.id : True})
        if wizard.pr_line_ids:
            for line in wizard.pr_line_ids:
                if line.order_state not in ['done','draft','reject','cancel']:
                    pr_dict.update({line.req_id.id: True})
        if pr_dict:
            req_pur_obj.write(cr, uid, pr_dict.keys(), {'available_qty_rule': wizard.available_qty_rule}, context=context)
        return {'type': 'ir.actions.act_window_close'}




