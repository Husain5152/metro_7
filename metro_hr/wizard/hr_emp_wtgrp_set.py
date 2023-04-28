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

from openerp.osv import osv,fields
from openerp.tools.translate import _

class hr_emp_wtgrp_set(osv.osv_memory):
    _name = 'hr.emp.wtgrp.set'
    _description = 'Set Employee Working Time Group'
    _columns = {
        'wt_grp_id': fields.many2one('hr.wt.grp', 'Working time group'),  
        'emp_ids' : fields.many2many('hr.employee', string='Employees', required=True),
    }
                        
    def default_get(self, cr, uid, fields, context=None):
        vals = super(hr_emp_wtgrp_set, self).default_get(cr, uid, fields, context=context)
        if not vals:
            vals = {}
        #worktime group id
        if context.get('active_model','') == 'hr.wt.grp' and context.get('active_id'):
            vals['wt_grp_id'] = context.get('active_id')
        #employees
        if context.get('active_model','') == 'hr.employee' and context.get('active_ids'):
            vals['emp_ids'] = context.get('active_ids')
                                
        return vals
    
    def set_data(self, cr, uid, ids, context=None):
        order_data = self.read(cr, uid, ids[0], ['emp_ids','wt_grp_id'], context=context)
        self.pool.get('hr.employee').write(cr, uid, order_data['emp_ids'],{'wt_grp_id':order_data['wt_grp_id'][0]},context=context)
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
