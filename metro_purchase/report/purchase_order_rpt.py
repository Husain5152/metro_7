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
from openerp.osv import osv
from openerp import pooler
from openerp.addons.purchase.report.order import order as po_rpt
def po_repeatIn(self, lst, name,nodes_parent=False):
    ret_lst = super(po_rpt,self).repeatIn(lst, name,nodes_parent)
    i = 0
    for obj in ret_lst:
        i = i + 1
        obj.get(name).idx = i
    return ret_lst
po_rpt.repeatIn = po_repeatIn
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

