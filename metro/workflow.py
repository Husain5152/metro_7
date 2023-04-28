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

from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp import netsvc

class wkf_instance(osv.osv):
    _inherit = "workflow.instance"
    def _get_res_name(self, cr, uid, ids, fld_name, args, context=None):
        res = dict.fromkeys(ids,False)
        for inst in self.browse(cr, uid, ids, context=context):
            res_obj = self.pool.get(inst.res_type)
            res_names = res_obj.name_get(cr, uid, [inst.res_id], context=context)
            if res_names:
                res[inst.id] = res_names[0][1]
#            res_obj = self.pool.get(inst.res_type)
#            res_names = res_obj.read(cr, uid, [inst.res_id], [res_obj._rec_name],context=context)
#            if res_names:
#                res[inst.id] = res_names[0][res_obj._rec_name]
        return res
    _columns = {
        'res_name': fields.function(_get_res_name,type='char',string='Res Name')
    }
    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
                    ids = [ids]
        reads = self.read(cr, uid, ids, ['res_type', 'res_name'], context=context)
        res = []
        for record in reads:
            name = record['res_type']
            if record['res_name']:
                name = name + '@' + record['res_name']
            res.append((record['id'], name))
        return res    

wkf_instance()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

