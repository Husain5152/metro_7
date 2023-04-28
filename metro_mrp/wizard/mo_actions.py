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
from openerp import netsvc
from openerp import pooler
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _

class mo_actions(osv.osv_memory):
    _name = "mo.actions"
    _description = "Manufacture Order Actions"
    _columns = {
        'action': fields.selection([
                   ('confirm','Confirm Production'),
                   ('produce_consume_produce','Produce - Consume & Produce'), 
                   ('produce_consume','Produce - Consume Only')]), 
        }
        
    _defaults = {'action':'confirm'}
    
    def do_action(self, cr, uid, ids, context=None):
        mo_action = self.browse(cr, uid, ids[0], context=context)
        if mo_action.action == 'confirm':
            return self.action_confirm(cr, uid, context.get('active_ids'), context=context)
        if mo_action.action == 'produce_consume_produce':
            return self.action_produce(cr, uid, context.get('active_ids'), 'consume_produce', context=context)
        if mo_action.action == 'produce_consume':
            return self.action_produce(cr, uid, context.get('active_ids'), 'consume', context=context)
        return False
    
    def action_confirm(self, cr, uid, mo_ids, context=None):
        wf_service = netsvc.LocalService("workflow")
        for mo in self.pool.get('mrp.production').browse(cr, uid, mo_ids, context=context):
            if mo.state=='draft':
                wf_service.trg_validate(uid, 'mrp.production', mo.id, 'button_confirm', cr)
        return {'type': 'ir.actions.act_window_close'}
    
    def action_produce(self, cr, uid, mo_ids, mode, context=None):
        mo_obj = self.pool.get('mrp.production')
        for mo in mo_obj.browse(cr, uid, mo_ids, context=context):
            if mo.state in ('confirmed','ready','in_production'):
                mo_obj.action_produce(cr, uid, mo.id, mo.product_qty, mode, context=context)      
    
mo_actions()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
