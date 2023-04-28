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
import time
import datetime
from openerp.osv import fields,osv
from openerp.tools.translate import _
from lxml import etree

class ir_ui_view(osv.osv):
    _inherit = "ir.ui.view"
    def _type_field(self, cr, uid, ids, name, args, context=None):
        result = {}
        for record in self.browse(cr, uid, ids, context):
            # Get the type from the inherited view if any.
            if record.inherit_id:
                result[record.id] = record.inherit_id.type
            else:
                result[record.id] = etree.fromstring(record.arch.encode('utf8')).tag
        return result    
    _columns = {
        'type': fields.function(_type_field, type='selection', selection=[
            ('tree','Tree'),
            ('form','Form'),
            ('mdx','mdx'),
            ('graph', 'Graph'),
            ('calendar', 'Calendar'),
            ('diagram','Diagram'),
            ('gantt', 'Gantt'),
            ('kanban', 'Kanban'),
            ('kanban_subgrp', 'Kanban Subgroup'),
            ('search','Search')], string='View Type', required=True, select=True, store=True), 
    }

VIEW_TYPES = [
    ('tree', 'Tree'),
    ('form', 'Form'),
    ('graph', 'Graph'),
    ('calendar', 'Calendar'),
    ('gantt', 'Gantt'),
    ('kanban', 'Kanban'),
    ('kanban_subgrp', 'Kanban Subgroup'),]

class act_window_view(osv.osv):
    _inherit = 'ir.actions.act_window.view'
    _columns = {
        'view_mode': fields.selection(VIEW_TYPES, string='View Type', required=True),
    }