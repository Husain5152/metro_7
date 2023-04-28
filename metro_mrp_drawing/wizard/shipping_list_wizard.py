# -*- coding: utf-8 -*-
import time
import os
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro import utils
from openerp.addons.metro_mrp_drawing.drawing_order import PART_TYPE_SELECTION
import xlrd
import StringIO

class shipping_list_wizard(osv.osv_memory):
    _name = 'shipping.list.wizard'
    _description = 'Shipping List Wizard'
    _columns = {
        'po_id': fields.many2one('purchase.order','Purchase Order',required=True,readonly=True),
        'break_do': fields.boolean('Break DO#?'),
        'break_id': fields.boolean('Break ID?'),
    }
    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(shipping_list_wizard, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        record_model = context and context.get('active_model', False) or False
        if record_model == 'purchase.order' and record_id:
            res.update({'po_id': record_id})
        return res

    def do_print_xls(self, cr, uid, ids, context=None):
        chinese = False
        if 'lang' in context:
            if context['lang'] == 'zh_CN':
                chinese = True
        wizard = self.browse(cr, uid, ids, context)[0]
        if wizard.po_id:
            po_obj = self.pool.get('purchase.order')
            return po_obj.print_shipping_list(cr, uid, [wizard.po_id.id], wizard.break_do, wizard.break_id, 'xls', chinese, context=context)
        return True

    def do_print_pdf(self, cr, uid, ids, context=None):
        chinese = False
        if 'lang' in context:
            if context['lang'] == 'zh_CN':
                chinese = True
        wizard = self.browse(cr, uid, ids, context)[0]
        if wizard.po_id:
            po_obj = self.pool.get('purchase.order')
            return po_obj.print_shipping_list(cr, uid, [wizard.po_id.id], wizard.break_do, wizard.break_id, 'pdf', chinese, context=context)
        return True

shipping_list_wizard()