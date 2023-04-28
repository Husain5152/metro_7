# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.pur_req import PR_AVAILABLE_QTY_RULE

class do_link_cnc_workorder_wizard(osv.osv_memory):
    _name = 'do.link.cnc.workorder.wizard'
    _description = 'Drawing Order Link CNC Work Order Wizard'
    _columns = {
        'cnc_workorder_id': fields.many2one('work.order.cnc','CNC Work Order', required=True),
        'drawing_order_id': fields.many2one('drawing.order', 'Drawing Order', readonly=True),
        'infor': fields.text('Information', readonly=True),
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(do_link_cnc_workorder_wizard, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        if not record_id:
            record_ids = context and context.get('active_ids', False) or False
            if record_ids:
                record_id = record_ids[0]
        record_model = context and context.get('active_model', False) or False
        if record_model == 'drawing.order':
            if record_id:
                order = self.pool.get('drawing.order').browse(cr, uid, record_id, context=context)
                res.update({'drawing_order_id': record_id,
                            'cnc_workorder_id': order.cnc_workorder_id and order.cnc_workorder_id.id or False})
        return res

    def onchange_cnc_workorder(self, cr, uid, ids, drawing_order_id, cnc_workorder_id, context=None):
        vals = {}
        if cnc_workorder_id:
            cnc_order = self.pool.get('work.order.cnc').browse(cr, uid, cnc_workorder_id, context=context)
            if cnc_order.drawing_order_id:
                if cnc_order.drawing_order_id.id != drawing_order_id:
                    vals.update({'infor': _('Warning: This CNC already linked with different DO!')})
        return {'value': vals}


    def do_link(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wizard = self.browse(cr, uid, ids, context)[0]
        if wizard.cnc_workorder_id:
            cnc_workorder_obj = self.pool.get('work.order.cnc')
            cnc_workorder_obj.write(cr, uid, [wizard.cnc_workorder_id.id], {'drawing_order_id': wizard.drawing_order_id.id})
        return {'type': 'ir.actions.act_window_close'}




