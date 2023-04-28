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

class validate_account_move(osv.osv_memory):
    _inherit = "validate.account.move"
    #make the journal_id is not required, then we can post all of entries of a period one time
    _columns = {
        'journal_id': fields.many2one('account.journal', 'Journal', required=False),
    }

    def validate_move(self, cr, uid, ids, context=None):
        obj_move = self.pool.get('account.move')
        if context is None:
            context = {}
        data = self.browse(cr, uid, ids, context=context)[0]
        #johnw, improve the search domain
        #ids_move = obj_move.search(cr, uid, [('state','=','draft'),('journal_id','=',data.journal_id.id),('period_id','=',data.period_id.id)])
        domain = [('state','=','draft'),('period_id','=',data.period_id.id)]
        if data.journal_id:
            domain.append(('journal_id','=',data.journal_id.id))
        ids_move = obj_move.search(cr, uid, domain)
        if not ids_move:
            raise osv.except_osv(_('Warning!'), _('Specified journal does not have any account move entries in draft state for this period.'))
        obj_move.button_validate(cr, uid, ids_move, context=context)
        return {'type': 'ir.actions.act_window_close'}

validate_account_move()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

