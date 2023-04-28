# -*- coding: utf-8 -*-
##############################################################################
#
#    sale_quick_payment for OpenERP
#    Copyright (C) 2011 Akretion Sébastien BEAU <sebastien.beau@akretion.com>
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

from openerp.osv import orm, fields
import openerp.addons.decimal_precision as dp

class pay_po(orm.TransientModel):
    _name = 'pay.po'
    _description = 'Wizard to generate a payment from the purchase order'

    _columns = {
        'journal_id': fields.many2one('account.journal', 'Payment Method', required=True),
        'amount': fields.float('Amount', digits_compute=dp.get_precision('Sale Price'), required=True),
        'amount_max': fields.float('Max Amount'),
        'date': fields.datetime('Payment Date'),
        'description': fields.char('Description', size=64, required=True),
    }
    
    def _get_amount(self, cr, uid, context=None):
        if context is None:
            context = {}
        if context.get('active_id'):
            po_obj = self.pool.get('purchase.order')
            order = po_obj.browse(cr, uid, context['active_id'],
                                    context=context)
            return order.residual
        return False

    _defaults = {
        'amount': 0,
        'amount_max':_get_amount,
        'date': fields.datetime.now,
    }

    def _check_amount(self, cr, uid, ids, context=None):
        for pay in self.browse(cr, uid, ids, context=context):
            if pay.amount <= 0 or pay.amount > pay.amount_max:
                return False
        return True
    
    _constraints = [(_check_amount, 'Pay amount only can be between zero and the balance.', ['amount'])]    

    def pay_po(self, cr, uid, ids, context=None):
        """ Pay the purchase order """
        wizard = self.browse(cr, uid, ids[0], context=context)
        po_obj = self.pool.get('purchase.order')
        po_obj.add_payment(cr, uid,
                             context['active_id'],
                             wizard.journal_id.id,
                             wizard.amount,
                             wizard.date,
                             description=wizard.description,
                             context=context)
        return {'type': 'ir.actions.act_window_close'}
