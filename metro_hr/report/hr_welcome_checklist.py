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

from openerp.report import report_sxw
from openerp.addons.metro.rml import rml_parser_ext  
#class hr_welcome_checklist(rml_parser_ext):
#    def __init__(self, cr, uid, name, context=None):
#        super(sale_agreement, self).__init__(cr, uid, name, context=context)
#        self.localcontext.update({
#            'time': time, 
#            'show_discount':self._show_discount,
#            'attr_value': self.attr_value,
#        })
#
#    def _show_discount(self, uid, context=None):
#        cr = self.cr
#        try: 
#            group_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sale', 'group_discount_per_so_line')[1]
#        except:
#            return False
#        return group_id in [x.id for x in self.pool.get('res.users').browse(cr, uid, uid, context=context).groups_id]
#    
#    def attr_value(self,data,attr):
#        attr_value = getattr(data,attr.name)
#        if attr_value and attr.attribute_type == 'select':
#            attr_value = attr_value.name
#        if attr_value and attr.attribute_type == 'multiselect':
#            attr_value = ','.join([opt.name for opt in attr_value])
#        return attr_value
    
report_sxw.report_sxw('report.hr.welcome.checklist', 'hr.employee', 'addons/metro_hr/report/hr_welcome_checklist.rml', parser=rml_parser_ext, header="internal")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

