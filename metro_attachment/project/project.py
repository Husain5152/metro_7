# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012-Today Acespritech Solutions Pvt Ltd
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


class project_project(osv.osv):
    _inherit = "project.project"
    _columns = {
        'attachment_lines': fields.one2many('ir.attachment', 'project_project_id',
                                            'Attachment'),
    }
project_project()

class project_task(osv.osv):
    _inherit = "project.task"
    _columns = {
        'attachment_lines': fields.one2many('ir.attachment', 'project_task_id',
                                            'Attachment'),
    }
project_project()
