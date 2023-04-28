# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools

class reserved_list_wizard(osv.osv_memory):
    _name = 'reserved.list.wizard'
    _description = 'Reserved List Wizard'
    _columns = {
        'product_id': fields.many2one('product.product','Product',readonly=True),
        'pr_reserved_ids': fields.many2many('pur.req.reserve',
                                          string='PR Reserved', readonly=True),
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(reserved_list_wizard, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        record_model = context and context.get('active_model', False) or False
        except_pr_ids = context and context.get('except_pr_ids', []) or []
        if record_id and record_model == 'product.product':
            pr_reserved_obj = self.pool.get('pur.req.reserve')
            if not except_pr_ids:
                reserved_ids = pr_reserved_obj.search(cr, uid, [('product_id','=',record_id)], context=context)
            else:
                reserved_ids = pr_reserved_obj.search(cr, uid, [('product_id', '=', record_id),
                                                                ('req_id','not in',except_pr_ids)], context=context)
            res.update({'product_id': record_id,
                        'pr_reserved_ids': [[6,0,reserved_ids]]})
        return res




