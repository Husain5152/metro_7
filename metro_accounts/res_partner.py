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

from operator import itemgetter
import time

from openerp.osv import fields, osv


class res_partner(osv.osv):
    _inherit = 'res.partner'
    def _asset_difference_search(self, cr, uid, obj, name, type, args, context=None):
        if not args:
            return []
        having_values = tuple(map(itemgetter(2), args))
        where = ' AND '.join(
            map(lambda x: '(SUM(bal2) %(operator)s %%s)' % {
                                'operator':x[1]},args))
        query = self.pool.get('account.move.line')._query_get(cr, uid, context=context)
        cr.execute(('SELECT pid AS partner_id, SUM(bal2) FROM ' \
                    '(SELECT CASE WHEN bal IS NOT NULL THEN bal ' \
                    'ELSE 0.0 END AS bal2, p.id as pid FROM ' \
                    #fix the issues that payable and receivable use same value (debit-credit), 09/20/2014
#                    '(SELECT (debit-credit) AS bal, partner_id ' \
                    '(SELECT ' + ((type=='receivable') and '(debit-credit)' or '(credit-debit)') + ' AS bal, partner_id ' \
                    'FROM account_move_line l ' \
                    'WHERE account_id IN ' \
                            '(SELECT id FROM account_account '\
                            'WHERE type=%s AND active) ' \
                    'AND reconcile_id IS NULL ' \
                    'AND '+query+') AS l ' \
                    'RIGHT JOIN res_partner p ' \
                    'ON p.id = partner_id ) AS pl ' \
                    'GROUP BY pid HAVING ' + where), 
                    (type,) + having_values)
        res = cr.fetchall()
        if not res:
            return [('id','=','0')]
        return [('id','in',map(itemgetter(0), res))]


res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
