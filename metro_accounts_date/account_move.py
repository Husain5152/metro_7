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
import time

class account_move(osv.osv):
    _inherit = "account.move"

    def _check_date(self, cr, uid, ids, context=None):
        for l in self.browse(cr, uid, ids, context=context):
            if l.journal_id.allow_date:
                if not time.strptime(l.date[:10],'%Y-%m-%d') >= time.strptime(l.period_id.date_start, '%Y-%m-%d') or not time.strptime(l.date[:10], '%Y-%m-%d') <= time.strptime(l.period_id.date_stop, '%Y-%m-%d'):
                    return False
        return True    
    
    _constraints = [
                    (_check_date, 'The date of your Journal Entry is not in the defined period! You should change the date or remove this constraint from the journal.', ['date', 'period_id']),
                    ]
    
account_move()

class account_move_line(osv.osv):
    _inherit = "account.move.line"
    #do not write move line's move_id
    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        if 'move_id' in vals:
            exist_ids = self.search(cr, uid, [('move_id','=',vals['move_id']), ('id', 'in', ids)], context=context)
            if len(exist_ids) != len(ids):
                #the move_id will be change
                raise osv.except_osv(_('Error!'), _('Account move line can not be assigned to other entry once it is created!'))
        return super(account_move_line, self).write(cr, uid, ids, vals, context=context, check=check, update_check=update_check)
class account_journal(osv.osv):
    _inherit = "account.journal"
    _defaults={"allow_date":True}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
