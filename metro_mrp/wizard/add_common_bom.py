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
import openerp.addons.decimal_precision as dp

class add_common_bom_line(osv.osv_memory):
    _name = "add.common.bom.line"
    _description = "Add Common BOM Line"

    _columns = {
        'wizard_id': fields.many2one('add.common.bom','BOM', required=True),
        'common_bom_id': fields.many2one('mrp.bom','Common BOM',domain="[('is_common','=',True)]", required=True),
        'name': fields.char('Name', size=64),
        'code': fields.char('Reference', size=16),
        'product_qty': fields.float('Product Quantity', required=True, digits_compute=dp.get_precision('Product Unit of Measure')),
    }

    def onchange_common_bom_id(self, cr, uid, ids, common_bom_id, context=None):
        """ 
        Changes common bom, set the common bom's name, quantity, reference.
        """
        if common_bom_id:
            bom = self.pool.get('mrp.bom').browse(cr, uid, common_bom_id, context=context)
            return {'value': {'name': bom.name, 'code': bom.code, 'product_qty':bom.product_qty}}
        return {}
    
class add_common_bom(osv.osv_memory):
    _name = "add.common.bom"
    _description = "Add Common BOM"

    _columns = {
        'mrp_bom_id': fields.many2one('mrp.bom','BOM'),
        'lines': fields.one2many('add.common.bom.line', 'wizard_id', 'Lines')
    }
            
    _defaults = {
        'mrp_bom_id': lambda self,cr,uid,c: c and c.get('active_id', False) or False,
    }    

    def do_add(self, cr, uid, ids, context=None):
        """ To Import BOM according to the excel file
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: the ID or list of IDs if we want more than one
        @param context: A standard dictionary
        @return:
        """
        if context is None:
            context = {}
        data = self.browse(cr, uid, ids[0], context=context)
        bom_obj = self.pool.get('mrp.bom')
        ctx_clone = context.copy()
        ctx_clone.update({'add_common_bom':True})
        for line in data.lines:
            #clone the data
            clone_bom_id = bom_obj.copy(cr, uid, line.common_bom_id.id, context=ctx_clone)        
            upt_data = {'bom_id':data.mrp_bom_id.id, 'name':line.name,'code':line.code,'product_qty':line.product_qty}
            bom_obj.write(cr, uid, [clone_bom_id], upt_data, context=ctx_clone)
            
        return {'type': 'ir.actions.act_window_close'}   

class mrp_bom(osv.osv):
    _inherit = 'mrp.bom'
    def copy_data(self, cr, uid, id, default=None, context=None):
        res = super(mrp_bom,self).copy_data(cr, uid, id, default=default, context=context)
        if not res:
            return res
        if context and 'add_common_bom' in context:
            #set the is_common and common bom id when do add common bom
            res.update({'is_common':False,
                        'common_bom_id':id})
        else:
            res.update({'is_common':False,
                        'common_bom_id':False})
        return res
            
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
