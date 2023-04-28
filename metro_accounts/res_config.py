# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (C) 2004-2012 OpenERP S.A. (<http://openerp.com>).
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

import logging

from openerp.osv import fields, osv
from openerp import pooler
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)

class account_config_settings(osv.osv_memory):
    _inherit = 'account.config.settings'
    _columns = {
        'report_bscn_id': fields.related('company_id', 'report_bscn_id', type='many2one', relation='account.financial.report', required=True,
            domain="[('parent_id','=',False)]", string='Balance Sheet'),
        'report_plcn_id': fields.related('company_id', 'report_plcn_id', type='many2one', relation='account.financial.report', required=True,
            domain="[('parent_id','=',False)]", string='Profit and Loss'),
        'report_cfcn_id': fields.related('company_id', 'report_cfcn_id', type='many2one', relation='account.financial.report', required=True,
            domain="[('parent_id','=',False)]", string='Cash Flow'),         
    }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
