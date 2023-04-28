# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST

class mo_select_do_wizard(osv.osv_memory):
    _name='mo.select.do.wizard'
    _description = 'MO Select DO Wizard'
    _columns = {
        'mo_id': fields.many2one('mrp.production','Manufacturer Order',readonly=True),
        'mo_big_subassembly_ids': fields.many2many('product.product', "mo_select_do_wizard_product","wz_id","product_id",string='MO Big Sub Assembly',readonly=True),
        'selected_big_subassembly_ids': fields.many2many('product.product',"mo_select_do_wizard_selected_product","wz_id","product_id",string='Selected Big Sub Assembly'),
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(mo_select_do_wizard, self).default_get(cr, uid, fields, context=context)
        mo_id = context and context.get('active_id', False) or False
        mo_obj = self.pool.get('mrp.production')
        mo = mo_obj.browse(cr, uid, mo_id, context=context)
        if mo:
            mo_big_subassembly_ids = []
            if mo.bom_id:
                for bom_line in mo.bom_id.bom_lines:
                    mo_big_subassembly_ids.append(bom_line.product_id.id)
            res.update({'mo_big_subassembly_ids': [[6, False, mo_big_subassembly_ids]],
                        'mo_id': mo_id,
                        })
        return res

    def do_generate(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids, context=context)[0]
        mo_obj = self.pool.get('mrp.production')
        if wizard:
            big_subassembly_ids = []
            for asm in wizard.selected_big_subassembly_ids:
                big_subassembly_ids.append(asm.id)
            mo_obj.generate_drawing_orders(cr, uid, wizard.mo_id.id, big_subassembly_ids)
        return {'type': 'ir.actions.act_window_close'}

mo_select_do_wizard()