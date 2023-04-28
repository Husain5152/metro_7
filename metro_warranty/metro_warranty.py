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
from openerp.addons.metro import utils


class warranty_cases(osv.osv):
    
    _name = "warranty.cases"
    _inherit = ['mail.thread']
    _description = 'Warranty Cases'
    _rec_name = 'case_number'
    _columns = {
        'case_number': fields.char('Case Number', size=64, required=True),
        'title': fields.char('Title', size=240, required=True),
        'state': fields.selection([('open', 'Open'),('close','Closed')], 'Status', readonly=True),
        'user_id': fields.many2one('res.users', 'Owner'),
        'date_created': fields.datetime('Case Start Date'),
        'date_closed': fields.datetime('Case End Date'),
        'serial_id': fields.many2one('mttl.serials','Serial Number'),
        'partner_id': fields.many2one('res.partner', 'Customer'),
        'contact_id': fields.many2one('res.partner', 'Contact'),
#        'child_ids': fields.related('partner_id', 'child_ids', type='one2many', relation='res.partner', string="Contacts"),
        'issue_ids': fields.one2many('warranty.issue','case_id','Issues'),
#        'issue': fields.text('Issue'),
#        'resolution': fields.text('Resolution'),
        'image': fields.text("Images"),
        'model_id': fields.many2one('mttl.models', 'Model', help="Metro Tow Trucks Model"),
        #+++ HoangTK - 04/15/2016 - Fix can not upload attachment
        #'attachment_id': fields.many2one('ir.attachment','Attachments'),
        'attachment_file_name': fields.char('Attachment File Name',size=128),
        #'attachment_id': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file, string="Attachment",
        #                            type="binary", multi="_get_file"),
        'attachment_id': fields.binary(string="Attachment"),
        #--- HoangTK - 04/15/2016 - Fix can not upload attachment
        'note': fields.text('Notes'),
        'active': fields.boolean('Active'),
    }
    
    _order = 'date_created desc'
    
    _defaults = {
        'active': 1,
        'state':'open',
        'date_created': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'case_number': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'warranty.cases'),
        'user_id': lambda obj, cr, uid, context: uid,
    }
    
    def next_state(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state' : 'close', 'date_closed':time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
    
    def previous_state(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state' : 'open'}, context=context) 
    
    def onchange_serial_id(self, cr, uid, ids, serial_id=False, partner_id=False):
        res = {'value': {'model_id':False, 'contact_id':False}}
        ch_ids = []
        if serial_id :
            serial = self.pool.get('mttl.serials').browse(cr, uid, serial_id)
            if serial.partner_id:
                ch_ids = [x.id for x in serial.partner_id.child_ids]
        res['value'].update({'partner_id':serial.partner_id.id or False,'model_id':serial.model.id or False,'contact_id':ch_ids and ch_ids[0] or False})
        res['domain'] = {'contact_id':[('id','in',ch_ids)]}
        if partner_id:
            self.onchange_partner_id(cr, uid, ids, partner_id)
        return res
        
    def onchange_partner_id(self, cr, uid, ids, partner_id):
        res = {'value': {'contact_id':False}}
        partner = self.pool.get('res.partner').browse(cr, uid, partner_id)
        partner_ids = [y.id for y in partner.child_ids]
        res['value'].update({'contact_id':partner_ids and partner_ids[0] or False})
        res['domain'] = {'contact_id':[('id','in',partner_ids)]}
        return res
    
warranty_cases()

class warranty_issue(osv.osv):
    _name = "warranty.issue"
    _description = 'Warranty Issue'
    _rec_name = 'resolution'
    _columns = {
        'case_id': fields.many2one('warranty.cases','Issue'),
        'issue_id' : fields.char('Issue', size=1000), 
        'resolution' : fields.char('Resolution', size=1000),
        'cause': fields.char('Cause',size=256),
    }
    
warranty_issue()

