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
class mto_design_print(rml_parser_ext):
    def __init__(self, cr, uid, name, context):
        super(mto_design_print, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_attr': self.get_attr,
            'attr_value': self.attr_value,
        })
    def get_attr(self,data,attr_name,attr_type=None):
        attr_val = getattr(data,attr_name)
        if attr_val and attr_type == 'multiselect':
            opt_ids = [opt.id for opt in attr_val]
            attr_val = opt_ids
        print '%s=%s'%(attr_name,attr_val)
        return attr_val
    def attr_value(self,data,attr):
        attr_value = getattr(data,attr.name)
        if attr_value and attr.attribute_type == 'select':
            attr_value = attr_value.name
        if attr_value and attr.attribute_type == 'multiselect':
            attr_value = ','.join([opt.name for opt in attr_value])
        return attr_value
report_sxw.report_sxw('report.mto.design.print', 'mto.design','addons/metro_mto/report/mto_design.rml',parser=mto_design_print)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

