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

from openerp.osv import osv,fields
from openerp.tools.translate import _
from openerp import netsvc
from openerp.addons.metro import utils

class hr_send_checklist(osv.osv_memory):
    _name = 'hr.send.checklist'
    _description = 'Send Employee Welcome Checklist'
    _columns = {
        'partner_ids': fields.many2many('res.partner', 'hr_send_checklist_res_partner_rel','wizard_id', 'partner_id', 'Contacts', required=True),
        'emp_ids' : fields.many2many('hr.employee', string='Employees', required=True),
    }
                        
    def default_get(self, cr, uid, fields, context=None):
        vals = super(hr_send_checklist, self).default_get(cr, uid, fields, context=context)
        if not vals:
            vals = {}
        #employees
        if context.get('active_model','') == 'hr.employee' and context.get('active_ids'):
            vals['emp_ids'] = context.get('active_ids')
                                
        return vals
    
    def send(self, cr, uid, ids, context=None):
        order = self.browse(cr, uid, ids[0], context=context)
        email_tos = [partner.email for partner in order.partner_ids if partner.email]
        emp_ids = order.emp_ids
        email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'],context=context)['email']
        if email_from and email_tos and emp_ids:
            subject = 'Employee Welcome Checklist'
            emp_names = ', '.join([emp.name for emp in emp_ids])
            body = '%s:%s'%(subject,emp_names)
            #generate the attachments by PDF report
            attachments = []
            report_name = 'Employee Welcome Checklist'
            report_service = netsvc.LocalService('report.hr.welcome.checklist')
            rpt_emp_ids = [emp.id for emp in emp_ids]            
            (result, format) = report_service.create(cr, uid, rpt_emp_ids, {'model': 'hr.employee'}, context)
            ext = "." + format
            if not report_name.endswith(ext):
                report_name += ext
            attachments.append((report_name, result))
            
            utils.email_send_group(cr, uid, email_from, email_tos, subject, body, context=context, attachments=attachments)
            
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
