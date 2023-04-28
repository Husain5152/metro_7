# -*- encoding: utf-8 -*-

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

from openerp.osv import fields, osv
from openerp import netsvc
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools import float_compare

import logging

class procurement_order(osv.osv):
    _inherit = 'procurement.order'

    def make_pur_req(self, cr, uid, ids, context=None):
        res = super(procurement_order, self).make_pur_req(cr, uid, ids, context=context)
        pur_req_obj = self.pool.get('pur.req')
        req_ids = []
        req_line_ids = [req_line_id for req_line_id in res]
        req_line_obj = self.pool.get('pur.req.line')
        for req_line in req_line_obj.browse(cr, uid, req_line_ids):
            if not req_line.req_id.id in req_ids:
                req_ids.append(req_line.req_id.id)
        pur_req_obj.write(cr, uid, req_ids, {'pr_type':'procurement'})
        return res
procurement_order()