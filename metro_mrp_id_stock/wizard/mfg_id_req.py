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

from openerp.osv import fields, osv

class mfg_id_req(osv.osv_memory):
    _name = "mfg.id.req"
    _columns={  
                'location_id': fields.many2one("stock.location", string="Location", required=True),
              }
    def do_save(self, cr, uid, ids, context=None):
        mfg_ids = context.get('active_ids',[])
        location_id = self.browse(cr, uid, ids[0], context=context).location_id.id
        return self.pool.get('sale.product').reserve_and_req(cr, uid, mfg_ids, location_id, context=context)
        
mfg_id_req()# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
