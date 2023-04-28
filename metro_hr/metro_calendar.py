# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP S.A. <http://www.openerp.com>
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

from osv import fields, osv

class exhibit_calendar(osv.osv):
    _name = "exhibit.calendar"
    _description = "Exhibition Calendar"
    _columns  = {
        'name': fields.char('Exhibition Name', size=512, required=True),
        'date_start':fields.date('Start date', required=True),
        'date_stop':fields.date('Stop date', required=False),
        'exhibit_type_id': fields.many2one('exhibit.type','Exhibition Type'),
        }
class exhibit_type(osv.osv):
    _name = "exhibit.type"
    _description = "Exhibition Type"
    _columns = {
        'name': fields.char('Name', size=256),
    }