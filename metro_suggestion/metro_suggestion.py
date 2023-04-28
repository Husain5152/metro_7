# -*- coding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 OpenERP SA (<http://www.openerp.com>)
#    Copyright (C) 2011-2013 Serpent Consulting Services Pvt. Ltd. (<http://www.serpentcs.com>).

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
from osv import osv
from tools.translate import _
from openerp.tools.translate import _
from datetime import datetime
import time

class metro_suggestion(osv.osv):
    _inherit = ['mail.thread']
    _name = "metro.suggestion"
    _description = 'Suggestion'
    _rec_name = 'suggestion_number'
    _columns = {
        'title': fields.char('Title',size=128,required=True),
        'suggestion_number': fields.char('Suggestion Number', size=64, required=True),
        'date_created': fields.datetime('Suggestion Date'),
        'note': fields.text('Notes'),
        'description': fields.text('Description'),
        'user_id': fields.many2one('res.users', 'Owner'),
        'image': fields.text("Images"),
        'model_id': fields.many2one('mttl.models', 'Model', help="Metro Tow Trucks Model"),
        'attachment_file_name': fields.char('Attachment File Name', size=128),
        'attachment_id': fields.binary(string="Attachment"),
        'state': fields.selection([('open', 'Open'), ('close', 'Closed')], 'Status', readonly=True),
        }
    def close(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state' : 'close'}, context=context)

    def open(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state' : 'open'}, context=context)

    _defaults = {
        'suggestion_number': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'suggestion.sequence'),
        'state': 'open',
        }
metro_suggestion()

