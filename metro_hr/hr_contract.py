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
class hr_contract(osv.osv):
    _inherit = 'hr.contract'
    _columns = {'multi_images': fields.text("Multi Images"),
                'house_rent_fund': fields.float('Individual Housing Fund'),
                'company_house_rent_fund': fields.float('Company Housing Fund'),
                }
    def onchange_employee_id(self, cr, uid, ids, employee_id,context):
        if not employee_id:
            return {}
        job_id = self.pool.get('hr.employee').read(cr, uid, employee_id, context=context)['job_id']
        return {'value':{'job_id': job_id}}
hr_contract()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
