# -*- coding: utf-8 -*-
import time

from openerp.osv import fields, osv
from openerp import netsvc
from openerp import pooler
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _

class pur_req_group(osv.osv_memory):
    _name = 'pur.req.group'

    def merge_orders(self, cr, uid, ids, context=None):
        req_obj = self.pool.get('pur.req')
        mod_obj = self.pool.get('ir.model.data')
        if context is None:
            context = {}
        filter_view_id = mod_obj._get_id(cr, uid, 'metro_purchase', 'view_pur_req_filter')
        filter_view = mod_obj.read(cr, uid, filter_view_id, ['res_id'])
        allorders = req_obj.do_merge(cr, uid, context.get('active_ids', []), context)
        return {
            'domain': "[('id','in', [" + ','.join(map(str, allorders.keys())) + "])]",
            'name': _('Purchase Requisition - All'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'pur.req',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'search_view_id': filter_view['res_id'],
        }
pur_req_group()
