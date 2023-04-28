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
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _

class mrp_product_produce(osv.osv_memory):
    _inherit = "mrp.product.produce"

    def _get_product_qty(self, cr, uid, context=None):
        """ To obtain product quantity
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param context: A standard dictionary
        @return: Quantity
        """
        if context is None:
            context = {}
        prod = self.pool.get('mrp.production').browse(cr, uid,
                                context['active_id'], context=context)
        done = 0.0
        for move in prod.move_created_ids2:
            if move.product_id == prod.product_id:
                if not move.scrapped:
                    done += move.product_qty
#        return (prod.product_qty - done) or prod.product_qty
        #by johnw, 08/02/2014, fix the issue: when the remain qty is zero it will return the prod.product_qty, it is wrong
        return prod.product_qty - done

    _defaults = {
         'product_qty': _get_product_qty,
    }

    def do_produce(self, cr, uid, ids, context=None):
        production_id = context.get('active_id', False)
        assert production_id, "Production Id should be specified in context as a Active ID."
        data = self.browse(cr, uid, ids[0], context=context)
        #johnw, 08/02/2014, add the quantity checking
        avail_qty = self._get_product_qty(cr,uid,context)
        if data.product_qty > avail_qty:
            raise osv.except_osv(_('Warning!'), _("The produce quantity can not be larger then the available quantity %s!"%(avail_qty,)))
        #end
        self.pool.get('mrp.production').action_produce(cr, uid, production_id,
                            data.product_qty, data.mode, context=context)
        return {}

mrp_product_produce()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
