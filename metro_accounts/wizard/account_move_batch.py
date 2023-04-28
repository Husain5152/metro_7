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

import time
from openerp.osv import osv
from openerp.tools.translate import _

class account_move_batch(osv.osv_memory):
    _name = "account.move.batch"
    _description = "Batch action on the account move"

    def review_account_move(self, cr, uid, ids, context=None):
        active_ids = context and context.get('active_ids', [])
        active_model = context and context.get('active_model', [])
        data =  self.browse(cr, uid, ids, context=context)[0]
        self.pool.get(active_model).review_account_move(cr, uid, active_ids, context=context)
        return {'type': 'ir.actions.act_window_close'}
    def validate_account_move(self, cr, uid, ids, context=None):
        active_ids = context and context.get('active_ids', [])
        active_model = context and context.get('active_model', [])
        data =  self.browse(cr, uid, ids, context=context)[0]
        self.pool.get(active_model).button_validate(cr, uid, active_ids, context=context)
        return {'type': 'ir.actions.act_window_close'}    
    def cancel_account_move(self, cr, uid, ids, context=None):
        active_ids = context and context.get('active_ids', [])
        active_model = context and context.get('active_model', [])
        data =  self.browse(cr, uid, ids, context=context)[0]
        self.pool.get(active_model).button_cancel(cr, uid, active_ids, context=context)
        return {'type': 'ir.actions.act_window_close'}    
account_move_batch()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
