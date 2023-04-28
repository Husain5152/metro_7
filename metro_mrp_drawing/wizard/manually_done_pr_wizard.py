# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.pur_req import PR_AVAILABLE_QTY_RULE

class manually_done_pr_wizard(osv.osv_memory):
    _name = 'manually.done.pr.wizard'
    _description = 'PR Manually Done'
    _columns = {
        'pr_ids': fields.many2many('pur.req',string='Purchase Requisition', readonly=True),
        'pr_note': fields.text('PR Notes',readonly=True),
        'force_done': fields.boolean('Force Done?'),
        'keep_reserve': fields.boolean('Keep Reserve?'),
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(manually_done_pr_wizard, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        record_ids = context and context.get('active_ids', False) or False
        record_model = context and context.get('active_model', False) or False
        if record_model == 'pur.req':
            pr_ids = []
            if record_ids:
                pr_ids = record_ids
            elif record_id:
                pr_ids = [record_id]
            erp_not_generated = []
            pr_obj = self.pool.get('pur.req')
            for pr in pr_obj.browse(cr, uid, pr_ids, context=context):
                for line in pr.line_ids:
                    if line.product_qty_remain > 0.0 and line.product_generated_qty == 0.0:
                        erp_not_generated.append(line.erp_no)
            note = 'All PR items have been generated PO, Please choose options below:'
            if len(erp_not_generated) > 0:
                note = 'Attention! There is still these %s items (%s) that require PO to be \
generated, are you sure want to close this PR?'% (len(erp_not_generated), ','.join(erp_not_generated))
            res.update({'pr_ids': [(6, False, pr_ids)],
                        'pr_note': note})

        return res

    def do_manually_done(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wizard = self.browse(cr, uid, ids, context)[0]
        pr_obj = self.pool.get('pur.req')
        if wizard.pr_ids:
            done_ids = [pr_id.id for pr_id in wizard.pr_ids]
            # if wizard.force_done:
            pr_obj.action_force_done(cr, uid, done_ids, context=context)
            # if not wizard.keep_reserve:
            # pr_obj.action_unreserved_products(cr, uid, done_ids, context=context)
        return {'type': 'ir.actions.act_window_close'}




