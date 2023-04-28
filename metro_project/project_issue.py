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
from openerp.osv import fields,osv
from openerp.addons.base_status.base_stage import base_stage


class project_issue(base_stage, osv.osv):
    _inherit = "project.issue"
    _columns = {
        'create_by': fields.many2one('res.users', 'Created By'),
        'database':fields.selection([('metro_prod', 'Metro Production'),('metro_uat', 'Metro UAT'),],'Database'),
        'database_test':fields.selection([('metro_prod', 'Metro Production'),('metro_uat', 'Metro UAT'),],'Testing Database'),
        'type':fields.selection([('defect', 'Defect'),('change_request', 'Change Request'),('feature_request', 'Feature Request'),],'Type'),
        'multi_images': fields.text("Multi Images"),
        'attachment_lines': fields.one2many('ir.attachment', 'project_issue_id',
                                            'Attachment'),        
    }
    _defaults = {
        'database': 'metro_prod',
        'database_test': 'metro_uat',
        'create_by': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).id ,
    }
    def message_post(self, cr, uid, thread_id, body='', subject=None, type='notification',
                        subtype=None, parent_id=False, attachments=None, context=None,
                        content_subtype='html', **kwargs):
        """ 
            Add the the assigned and creator to the receipts
        """
        
        if isinstance(thread_id, (list, tuple)):
            thread_id = thread_id[0]
        if thread_id:
            user_ids = kwargs['partner_ids'] if kwargs.get('partner_ids') else []
            issue = self.browse(cr,uid,thread_id,context)
            if issue.user_id:
                user_ids.append(issue.user_id.partner_id.id)
            if issue.create_by:
                user_ids.append(issue.create_by.partner_id.id)
            kwargs['partner_ids'] = user_ids
        return super(project_issue, self).message_post(cr, uid, thread_id, body, subject, type,
                        subtype, parent_id, attachments, context,
                        content_subtype, **kwargs)    