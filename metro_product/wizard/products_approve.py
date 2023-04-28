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

class products_approve(osv.osv_memory):
    _name = "products.approve"
    _description = "Approve products by batch"
    _columns={'sale_ok':fields.boolean('Can be sold'),
              'purchase_ok':fields.boolean('Can be purchased'),                            
              }
    def approve(self, cr, uid, ids, context=None):
        active_ids = context and context.get('active_ids', [])
        vals = {'state':'sellable','active':1}
        data = self.browse(cr, uid, ids, context=context)[0]
        vals.update({'purchase_ok':data.purchase_ok,'sale_ok':data.sale_ok,})
        #get the draft products to approve
        prod_obj = self.pool.get('product.product')
        prod_ids = prod_obj.search(cr, uid, [('id','in',active_ids),('state','=','draft')],context=context)
        if prod_ids:
            prod_obj.write(cr, uid, prod_ids, vals, context=context)
        return {'type': 'ir.actions.act_window_close'}
products_approve()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
