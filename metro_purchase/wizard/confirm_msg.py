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
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _

class confirm_msg(osv.osv_memory):
    _name = "confirm.msg"
    _description = "Action Confirming Message"
    _columns = {
        'message': fields.text('Rejection reason'),
    }

    def confirm(self, cr, uid, ids, context=None):
        active_ids = context and context.get('active_ids', [])
        active_model = context and context.get('active_model', [])
        data =  self.browse(cr, uid, ids, context=context)[0]
        self.pool.get(active_model).action_reject(cr, uid, active_ids, data.message, context=context)
        return {'type': 'ir.actions.act_window_close'}
    def reject_changing(self, cr, uid, ids, context=None):
        active_ids = context and context.get('active_ids', [])
        active_model = context and context.get('active_model', [])
        data =  self.browse(cr, uid, ids, context=context)[0]
        self.pool.get(active_model).button_to_changing_rejected(cr, uid, active_ids, data.message, context=context)
        return {'type': 'ir.actions.act_window_close'}
confirm_msg()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
