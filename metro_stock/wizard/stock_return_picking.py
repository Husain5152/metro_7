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

from openerp import netsvc
import time

from openerp.osv import osv,fields
from openerp.tools.translate import _
from openerp import netsvc

class stock_return_picking(osv.osv_memory):
    _inherit = 'stock.return.picking'
    _columns = {
        'reason' : fields.text('Return Reason',required=True),
    }

    def default_get(self, cr, uid, fields, context=None):
        res = super(stock_return_picking, self).default_get(cr, uid, fields, context=context)
        if context is None:
            context = {}
        record_id = context and context.get('active_id', False) or False
        pick = self.pool.get('stock.picking').browse(cr, uid, record_id, context=context)
        if pick and 'invoice_state' in fields:
            #for the picking with invoice or to be invoiced, set the invoice state to to be invoiced
            if pick.invoice_state in ('2binvoiced', 'invoiced'):
                res.update({'invoice_state': '2binvoiced'})
            else:
                res.update({'invoice_state': 'none'})
        return res
    
    def create_returns(self, cr, uid, ids, context=None):
        resu = super(stock_return_picking, self).create_returns(cr, uid, ids, context)
        domain = eval(resu['domain'])
        pick_id = domain[0][2][0]
        data = self.read(cr, uid, ids[0], context=context)
        pick_obj = self.pool.get("stock.picking")
        pick = pick_obj.browse(cr,uid,pick_id,context=context)
        note = pick.note and pick.note != '' and (pick.note + ';' + data["reason"]) or data["reason"]
        pick_obj.write(cr, uid, [pick_id], {'note':note})
        '''
        since the parent class did the pick_obj.force_assign(cr, uid, [new_picking], context)
        So need trigger the workflow to run below transition, if no available quantity then picking will go the 'confirmed' state
        <record id="trans_confirmed_assigned_back" model="workflow.transition">
            <field name="act_from" ref="act_assigned"/>
            <field name="act_to" ref="act_confirmed"/>
            <field name="condition">not test_assigned()</field>
        </record>        
        '''
        #update state to 'assigned' then the test_assigned() method will return false
        move_ids = [move.id for move in pick.move_lines if move.state=='assigned']
        self.pool.get('stock.move').write(cr, uid, move_ids, {'state':'draft'},context=context)
        pick_obj.write(cr, uid, [pick_id], {'state':'draft'})
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_write(uid, 'stock.picking', pick_id, cr)
        return resu
    def get_return_history(self, cr, uid, pick_id, context=None):
        """ 
         Get  return_history.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param pick_id: Picking id
         @param context: A standard dictionary
         @return: A dictionary which of values.
        """
        pick_obj = self.pool.get('stock.picking')
        pick = pick_obj.browse(cr, uid, pick_id, context=context)
        return_history = {}
        for m  in pick.move_lines:
            #use the function field return_qty direct
            return_history[m.id] = m.return_qty
        return return_history    
#note        

stock_return_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
