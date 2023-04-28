# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools

class set_pr_line_supplier_wizard(osv.osv_memory):
    _name = 'set.pr.line.supplier.wizard'
    _description = 'Set PR Line Supplier Wizard'
    _columns = {
        'pr_id': fields.many2one('pur.req','Purchase Requisition',readonly=True),
        'pr_line_ids': fields.many2many('pur.req.line',string='Purchase Requisition Lines', readonly=True),
        'supplier_id': fields.many2one('res.partner', 'Supplier', required=True),
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(set_pr_line_supplier_wizard, self).default_get(cr, uid, fields, context=context)
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

    def do_set(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wizard = self.browse(cr, uid, ids, context)[0]
        req_pur_line_obj = self.pool.get('pur.req.line')
        line_state_flag = False
        pr_line_ids = []
        line_supplier_flag = False
        if wizard.supplier_id and wizard.pr_id:
            for line in wizard.pr_id.line_ids:
                if line.order_state not in ['done','cancel']:
                    pr_line_ids.append(line.id)
                    if line.supplier_id:
                        line_supplier_flag = True
                else:
                    line_state_flag = True
        if wizard.supplier_id and wizard.pr_line_ids:
            for line in wizard.pr_line_ids:
                if line.order_state not in ['done', 'cancel']:
                    pr_line_ids.append(line.id)
                    if line.supplier_id:
                        line_supplier_flag = True
                else:
                    line_state_flag = True
        if pr_line_ids:
            if line_supplier_flag:
                return {
                    'name': 'Confirm Set Supplier',
                    'res_model': 'confirm.set.pr.line.supplier.wizard',
                    'type': 'ir.actions.act_window',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {'pr_line_ids': pr_line_ids,'supplier_id': wizard.supplier_id.id},
                }
            req_pur_line_obj.write(cr, uid, pr_line_ids, {'supplier_id': wizard.supplier_id.id})
            if line_state_flag:
                return self.pool.get('warning').info(cr, uid, title='Warning', message=_(
                    "Only PR lines not in done or cancel state changed supplier!"))
        return {'type': 'ir.actions.act_window_close'}




