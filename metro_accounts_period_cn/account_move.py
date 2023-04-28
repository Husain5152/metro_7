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

class account_move(osv.osv):
    _inherit = "account.move"
    
#    def _centralise(self, cr, uid, move, mode, context=None):
#        if move.journal_id.period_close or move.journal_id.year_close:
#            '''
#            for the centralise journal, the original _centralise() will generate move line to make the whole move is balance
#            But this logic need to add all move lines in one time, if use create() to add move line, then one new move line may be generated each time for the centralise journal if this move is unbalance
#            in account_period_close_entry, the move line was added one by one, so we need disable this feature under this case
#            '''            
#            return True
#        else:
#            return super(account_move,self)._centralise(cr, uid, move, mode, context=context)

    def _check_centralisation(self, cursor, user, ids, context=None):
        for move in self.browse(cursor, user, ids, context=context):
            #if move.journal_id.centralisation:
            #for the year/month close journal, only need this constraint
            if move.journal_id.centralisation or move.journal_id.period_close or move.journal_id.year_close:
                move_ids = self.search(cursor, user, [
                    ('period_id', '=', move.period_id.id),
                    ('journal_id', '=', move.journal_id.id),
                    ])
                if len(move_ids) > 1:
                    return False
        return True
    
    _constraints = [
        (_check_centralisation,
            'You cannot create more than one move per period on a centralized or period/year close journal.',
            ['journal_id']),
    ]
        
    def button_cancel(self, cr, uid, ids, context=None):
        for move in self.browse(cr, uid, ids, context=context):
            if move.period_id.state == 'done':
                raise osv.except_osv(_('Error!'), _('You cannot cancel a entry of closed period.'))
        return super(account_move, self).button_cancel(cr, uid, ids, context=context)
    
account_move()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
