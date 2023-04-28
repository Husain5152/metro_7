# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP SA (<http://openerp.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time
from lxml import etree
from openerp.osv import fields, osv
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.float_utils import float_compare
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


class stock_partial_picking(osv.osv_memory):
    _inherit = "stock.partial.picking"

    _columns = {
            'deliver_ticket_no': fields.char('Deliver Ticket#', size=50),
            'mr_ticket_no': fields.char('Ticket#', size=16),
            'pick_type': fields.selection([('out', 'Sending Goods'), 
                                                     ('in', 'Getting Goods'), 
                                                     ('internal', 'Internal'), 
                                                     ('mr', 'Material Request'), 
                                                     ('mrr', 'Material Return')],
                                        "Pick Type",size=16)
     }
    def default_get(self, cr, uid, fields, context=None):
        if context is None: context = {}
        res = super(stock_partial_picking, self).default_get(cr, uid, fields, context=context)
        picking = self.pool.get('stock.picking').read(cr, uid, context.get('active_id', []), ['type'],context=context)
        res.update({'pick_type':picking['type']})
        return res
    def do_partial(self, cr, uid, ids, context=None):
        if context == None:
            context = {}
        data = self.browse(cr, uid, ids[0], context=context)
        context.update({'deliver_ticket_no':data.deliver_ticket_no, 'mr_ticket_no':data.mr_ticket_no})
        return super(stock_partial_picking,self).do_partial(cr, uid, ids, context=context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
