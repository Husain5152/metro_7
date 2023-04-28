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
from openerp.tools.translate import _
class wo_material_request(osv.osv_memory):
    _name = "wo.material.request"
    _description = "Work Order Material Request"
    _columns = {
        'name': fields.many2one('mrp.production.workcenter.line','Work Order',readonly=True),
        'mr_dept_id': fields.many2one('hr.department', 'Department',required=True),
        'mr_emp_id': fields.many2one('hr.employee','Employee',required=True),
        'mr_lines': fields.many2many('material.request.line', 'wo_mr_wizard_move', 'wo_mr_id','move_id',string='Request Products'),
    }
    
    _defaults = {'name': lambda self, cr, uid, context: context.get('active_id')}
    
    def fields_get(self, cr, uid, allfields=None, context=None, write_access=True):
        resu = super(wo_material_request,self).fields_get(cr, uid, allfields,context,write_access)
        record_id = context and context.get('active_id', False) or False
        if record_id:
            #set  the 'mr_lines' domain dynamically
            record = self.pool.get('mrp.production.workcenter.line').browse(cr, uid, record_id, context=context)
            if record and record.stock_move_ids:     
                move_ids = [move.id for move in record.stock_move_ids if not move.picking_id]
                resu['mr_lines']['domain'] = [('id','in',move_ids)]
        return resu
           
    def action_done(self, cr, uid, ids, context=None): 
        if not context:
            context = {}
        data = self.browse(cr,uid,ids,context)[0]
        if not data.mr_lines:
            raise osv.except_osv(_('Error!'), _('Please select the produts to make material request!'))
        #create new materia request        
        new_mr_id = self.pool.get('material.request').create(cr, uid,{'mr_dept_id':data.mr_dept_id.id,'state':'draft','type':'mr'},context=context)
        #update the material request line picking info
        mr_line_obj = self.pool.get('material.request.line')
        mr_line_ids = [mr_line.id for mr_line in data.mr_lines]
        mr_line_obj.write(cr, uid, mr_line_ids, {'mr_emp_id':data.mr_emp_id.id,'picking_id':new_mr_id,'mr_notes':data.name.code})
        #return to the material request list page
        return {
            'domain': "[('id', '=', %s)]"%(new_mr_id,),
            'name': _('Work Order Material Request'),
            'view_type':'form',
            'view_mode':'tree,form',
            'res_model': 'material.request',
            'type':'ir.actions.act_window',
            'context':context,
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
