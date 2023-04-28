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
from openerp.tools.translate import _


class res_users(osv.osv):
    _inherit = "res.users"
    _description = "Users"

    def update_lang(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        to_lang = context.get('to_lang', False)
        if to_lang:
            self.write(cr, uid, ids, {'lang':to_lang}, context)
        return self.preference_save(cr, uid, ids, context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
