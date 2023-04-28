# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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
import datetime
from openerp.osv import fields,osv
from openerp.tools.translate import _


class material_request_barcode(osv.osv):
    _inherit = "material.request"
    _columns = {
        'mr_emp_code' : fields.char('Employee Code', size=64),
        'mr_emp_id': fields.many2one('hr.employee', 'Employee'),
        'mr_sale_prod_id': fields.many2one('sale.product','Sale Product ID'),
        'show_barcode_info': fields.boolean('Show?'),    
    }
    def onchange_mr_emp_code(self, cr, uid, ids, mr_emp_code, context=None):
        """ On change of product barcode.
        @param bc_product_code: Changed Product code
        @return: Dictionary of values
        """
        
        if not mr_emp_code:
            return {}
        emp_obj = self.pool.get('hr.employee')
        emp_ids = emp_obj.search(cr, uid, [('emp_code','=',mr_emp_code)],context)
        if not emp_ids or len(emp_ids) == 0:
            return {}
        dept_id = emp_obj.browse(cr, uid, emp_ids, context)[0].department_id.id
        result = {'mr_emp_id':emp_ids[0],'mr_dept_id':dept_id}
        return {'value': result}
    
    def onchange_mr_emp_id(self, cr, uid, ids, mr_emp_id, context=None):
        """ On change of product barcode.
        @param bc_product_code: Changed Product code
        @return: Dictionary of values
        """
        
        if not mr_emp_id:
            return {}
        emp_obj = self.pool.get('hr.employee')
        emp = emp_obj.browse(cr, uid, mr_emp_id,context)
        result = {'mr_dept_id':emp.department_id.id,'mr_emp_code':emp.emp_code}
        return {'value': result}
    
    def create(self, cr, user, vals, context=None):
        vals.update({'show_barcode_info':False})
        return super(material_request_barcode,self).create(cr, user, vals, context)
    
    def write(self, cr, user, ids, vals, context=None):
        vals.update({'show_barcode_info':False})
        return super(material_request_barcode,self).write(cr, user, ids, vals, context)
    
    _defaults={'show_barcode_info':False}
    
class material_request_line_barcode(osv.osv):
    _inherit = "material.request.line"
    _columns = {
        'bc_product_code' : fields.char('Product Code', size=64),
    }
    def onchange_bc_product_code(self, cr, uid, ids, bc_product_code, mr_emp_id, mr_sale_prod_id, product_id, context=None):
        """ On change of product barcode.
        @param bc_product_code: Changed Product code
        @return: Dictionary of values
        """
        
        if not bc_product_code:
            return {}
        prod_obj = self.pool.get('product.product')
        prod_ids = prod_obj.search(cr, uid, [('default_code','ilike',bc_product_code)],context)
        if not prod_ids or len(prod_ids) == 0:
            return {}
        prod_id = prod_ids[0]
        bc_product_name = prod_obj.name_get(cr, uid, [prod_id], context)[0][1]
        result = {'product_id':prod_id,'product_qty':1,'mr_emp_id':mr_emp_id,'mr_sale_prod_id':mr_sale_prod_id}
        if product_id and product_id == prod_id:
           id_change_resu = self.onchange_product_id(cr, uid, ids, product_id)
           result.update(id_change_resu['value'])
        return {'value': result}
    def default_get(self, cr, uid, fields_list, context=None):
        resu = super(material_request_line_barcode,self).default_get(cr, uid, fields_list, context)
        #material_request.type: mr or mrr
        if context.get('set_emp_id'):
            resu.update({'mr_emp_id':context.get('set_emp_id')})
        if context.get('set_sale_prod_id'):
            resu.update({'mr_sale_prod_id':context.get('set_sale_prod_id')})
        return resu    
