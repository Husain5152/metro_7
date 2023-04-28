# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from openerp.osv import fields, osv
from openerp.tools.translate import _
import logging
from openerp import SUPERUSER_ID

_logger = logging.getLogger(__name__)

class stock_change_inventory_date(osv.osv_memory):
    _name = "stock.change.inventory.date"
    _columns = {
        'inv_ids': fields.many2many('stock.inventory', string='Physical Inventories', readonly=True),
        'inventory_date': fields.datetime('Inventory Date',required=True)
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(stock_change_inventory_date, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        record_ids = context and context.get('active_ids', False) or False
        record_model = context and context.get('active_model', False) or False
        if record_model == 'stock.inventory':
            if record_ids:
                res.update({'inv_ids': [(6, False, record_ids)]})
            elif record_id:
                res.update({'inv_ids': [(6, False, [record_id])]})
        return res

    def change_date(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wizard = self.browse(cr, uid, ids, context)[0]
        move_ids = []
        for inv_id in wizard.inv_ids:
            if inv_id.state == 'confirm':
                move_ids.extend([move.id for move in inv_id.move_ids])
        if move_ids:
            self.pool.get('stock.move').write(cr, SUPERUSER_ID, move_ids, {'date': wizard.inventory_date}, context=context)
        return {'type': 'ir.actions.act_window_close'}

stock_change_inventory_date()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
