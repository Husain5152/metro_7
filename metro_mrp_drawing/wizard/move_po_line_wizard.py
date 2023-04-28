# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools

class move_po_line_wizard(osv.osv_memory):
    _name = 'move.po.line.wizard'
    _description = 'Move PO Line Wizard'
    _columns = {
        'po_id': fields.many2one('purchase.order','Purchase Order',required=True),
        'po_line_ids': fields.many2many('purchase.order.line',string='Move Purchase Order Lines',readonly=True),
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(move_po_line_wizard, self).default_get(cr, uid, fields, context=context)
        record_ids = context and context.get('active_ids', False) or False
        record_model = context and context.get('active_model', False) or False
        if record_model == 'purchase.order.line' and record_ids:
            #Check if any line not in draft state ?
            po_line_obj = self.pool.get('purchase.order.line')
            for line in po_line_obj.browse(cr, uid, record_ids, context=context):
                if line.state != 'draft':
                    raise osv.except_osv(_('Error!'), _("Can not move a line not in draft state!"))
            res.update({'po_line_ids': [[6, False, record_ids]]})
        return res

    def do_move_line(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids, context=context)[0]
        po_line_obj = self.pool.get('purchase.order.line')
        if wizard.po_id and wizard.po_line_ids:
            if wizard.po_id.state != 'draft':
                raise osv.except_osv(_('Error!'), _("Can not move lines to a PO not in draft state!"))
            po_line_ids = []
            for line_id in wizard.po_line_ids:
                po_line_obj.copy(cr, uid, line_id.id, {'order_id': wizard.po_id.id},context=context)
                po_line_ids.append(line_id.id)
            po_line_obj.unlink(cr, uid, po_line_ids, context=context)
        return True

