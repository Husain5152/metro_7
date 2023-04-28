# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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
from datetime import datetime
import time

from openerp.osv import fields,osv

class change_log_po_line(osv.osv):  
    _name = "change.log.po.line"
    _columns = {
        'po_line_id': fields.many2one('purchase.order.line','PO Line'),
        'po_id': fields.many2one('purchase.order','PO'),
        'product_id': fields.many2one('product.product','Product'),
        'field_name':  fields.char('Field Name', size=30, readonly=True),
        'value_old': fields.char('Old Value', readonly=True),
        'value_new': fields.char('New Value', readonly=True),
        'create_uid': fields.many2one('res.users', 'User', readonly=True),
        'create_date':  fields.datetime('Time', readonly=True),
    }
    _order = 'create_date desc'
change_log_po_line()    