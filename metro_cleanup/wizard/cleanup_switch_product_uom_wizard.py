# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.pur_req import PR_AVAILABLE_QTY_RULE

class cleanup_switch_product_uom_wizard(osv.osv_memory):
    _name = 'cleanup.switch.product.uom.wizard'
    _description = 'Cleanup Switch Product UOM Wizard'
    _columns = {
        'old_uom_id': fields.many2one('product.uom', 'Old UOM', required=True),
        'categ_id': fields.many2one('product.uom.categ', 'UOM Category'),
        'new_uom_id': fields.many2one('product.uom', 'New UOM', required=True),
        'product_ids': fields.many2many('product.product',string='Products', help='Products to switch to new UOM'),
    }

    def onchange_old_uom_id(self, cr, uid, ids, uom_id, context=None):
        uom_obj = self.pool.get('product.uom')
        if uom_id:
            uom = uom_obj.browse(cr, uid, uom_id, context=context)
            if uom:
                return {'value': {'categ_id': uom.category_id.id,'product_ids': []}}
        return {'value': {}}

    def do_switch(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wizard = self.browse(cr, uid, ids, context)[0]
        product_obj = self.pool.get('product.product')
        if wizard.old_uom_id and wizard.product_ids and wizard.new_uom_id:
            if wizard.old_uom_id.category_id.id == wizard.new_uom_id.category_id.id:
                product_ids = [product.id for product in wizard.product_ids]
                product_obj.write(cr, uid, product_ids, {'uom_id': wizard.new_uom_id.id,
                                                         'uos_id': wizard.new_uom_id.id,
                                                         'uom_po_id': wizard.new_uom_id.id}, context=context)
        message = _("%s product uoms have been updated.") % len(wizard.product_ids)
        return  self.pool.get('warning').info(cr, uid, title='Information', message=message)




