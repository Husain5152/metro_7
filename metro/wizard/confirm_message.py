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

class confirm_message(osv.osv_memory):
    _name = "confirm.message"
    _description = "Action Confirming Message"
    _columns = {
        'message': fields.text('Message'),
    }

    def confirm(self, cr, uid, ids, context=None):
        active_ids = context and context.get('active_ids', [])
        active_model = context and context.get('active_model', [])
        data =  self.browse(cr, uid, ids, context=context)[0]
        model_callback = context and context.get('model_callback', [])
        if model_callback:
            getattr(self.pool.get(active_model), model_callback)(cr, uid, active_ids, data.message, context=context)
        return {'type': 'ir.actions.act_window_close'}
    
    def open(self, cr, uid, ids, context):
        '''
        This function opens a window to show the reject message inputing window
        '''
        assert len(ids) == 1, 'This option should only be used for a single id at a time.'
        ir_model_data = self.pool.get('ir.model.data')
        try:
            msg_form_id = ir_model_data.get_object_reference(cr, uid, 'metro', 'view_confirm_message_form')[1]
        except ValueError:
            msg_form_id = False
        ctx = dict(context)
        return {
            'type': 'ir.actions.act_window',
            'name': context.get('confirm_title',False) or 'Confirm message',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'confirm.message',
            'src_model':  context.get('src_model',False),
            'views': [(msg_form_id, 'form')],
            'view_id': msg_form_id,
            'target': 'new',
            'context': ctx,
        }

confirm_message()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
