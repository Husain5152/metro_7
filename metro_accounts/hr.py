# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP S.A. <http://www.openerp.com>
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

from osv import fields, osv
import openerp.addons.decimal_precision as dp

import logging

_logger = logging.getLogger(__name__)


class hr_employee(osv.osv):
	_inherit = "hr.employee"

	def _money_borrow(self, cr, uid, ids, field_names, args, context=None):
		res = dict((id,dict((field_name,None) for field_name in field_names)) for id in ids)
		emp_borrow_obj = self.pool.get('emp.borrow')
		for emp_id in ids:
			money_borrowed = 0.0
			money_residual = 0.0
			money_borrow_mvln_ids = []
			borrow_ids = emp_borrow_obj.search(cr, uid, [('emp_id','=',emp_id),('state','=','done')],context=context)
			for borrow in emp_borrow_obj.browse(cr, uid, borrow_ids, context=context):			
				for mvln in borrow.move_lines:
					if mvln.account_id.type == 'receivable':
						money_borrowed += mvln.debit
						money_residual += mvln.amount_residual
						money_borrow_mvln_ids.append(mvln.id)
						#find the reconciled employee return money move lines
						reconcile_mvln_ids =  (mvln.reconcile_id and mvln.reconcile_id.line_id) or (mvln.reconcile_partial_id and mvln.reconcile_partial_id.line_partial_ids) or None
						if reconcile_mvln_ids:
							for reconcile_mvln in reconcile_mvln_ids:
								if reconcile_mvln.account_id.type == 'receivable' and reconcile_mvln.id != mvln.id:
									money_borrow_mvln_ids.append(reconcile_mvln.id)
							
				res[emp_id].update({'money_borrowed':money_borrowed, 
								'money_residual':money_residual, 
								'money_returned':money_borrowed-money_residual,
								'money_borrow_mvln_ids':money_borrow_mvln_ids, 
								})
		return res
	_columns = {
        'money_borrowed':fields.function(_money_borrow, string='Borrowed Money', type='float', digits_compute=dp.get_precision('Account'), multi="_money_borrow"),
        'money_returned':fields.function(_money_borrow, string='Returned Money', type='float',  digits_compute=dp.get_precision('Account'), multi="_money_borrow"),
        'money_residual':fields.function(_money_borrow, string='Borrowed residual', type='float',  digits_compute=dp.get_precision('Account'), multi="_money_borrow"),
        'money_borrow_mvln_ids':fields.function(_money_borrow, string='Borrowed move lines', type='many2many',  relation='account.move.line', multi="_money_borrow"),
	}
	
hr_employee()
