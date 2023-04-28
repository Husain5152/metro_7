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

class warranty_defect(osv.osv):
    
    _name = "warranty.defect"
    _inherit = "warranty.cases"
    _description = 'Warranty Defect'
    _rec_name = 'case_number'
    _columns = {
        'issue_ids': fields.one2many('defect.issue','case_id','Issues')
        }
        
    _defaults = {
    
        'case_number': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'warranty.defect')
        }
warranty_defect()

class defect_issue(osv.osv):
    
    _name = "defect.issue"
    _inherit = "warranty.issue"
    _description = 'Defect Issue'
    _rec_name = 'resolution'
    _columns = {
        'case_id': fields.many2one('warranty.defect','Issue'),
        'complete': fields.boolean('Completed'),
        'defect_date': fields.date('Defect Date'),
        'resolved_user_id': fields.many2one('res.users', 'Resolved By')
        }
        
    _defaults = {
        
        'defect_date': lambda *a: time.strftime('%Y-%m-%d'),
        'resolved_user_id': lambda obj, cr, uid, context: uid
        }
defect_issue()

