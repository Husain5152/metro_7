# -*- coding: utf-8 -*-
'''
Created on 2014-1-8

@author: john.wang
'''
from osv import fields, osv
from tools.translate import _
import openerp.tools as tools

class email_template(osv.Model):
    _inherit = 'email.template'
    _sql_constraints = [
        ('name', 'unique (name)', _('Email Template Name must be unique!'))
    ]     
    def send_mail(self, cr, uid, template_id, res_id, force_send=False, context=None):
        """Generates a new mail message for the given template and record,
           and schedules it for delivery through the ``mail`` module's scheduler.

           :param int template_id: id of the template to render
           :param int res_id: id of the record to render the template with
                              (model is taken from the template)
           :param bool force_send: if True, the generated mail.message is
                immediately sent after being created, as if the scheduler
                was executed for this message only.
           :returns: id of the mail.message that was created
        """
        if context is None:
            context = {}
        mail_mail = self.pool.get('mail.mail')
        ir_attachment = self.pool.get('ir.attachment')

        # create a mail_mail based on values, without attachments
        values = self.generate_email(cr, uid, template_id, res_id, context=context)
        #johnw, 07/29/2014, improve the email_from checking, auto set it to system email_from if it is missing
        if not values.get('email_from'):
            values['email_from'] = tools.config.get('email_from')
        #print(values)
        assert values.get('email_from'), 'email_from is missing or empty after template rendering, send_mail() cannot proceed'            
        del values['email_recipients']  # TODO Properly use them.
        attachment_ids = values.pop('attachment_ids', [])
        attachments = values.pop('attachments', [])
        msg_id = mail_mail.create(cr, uid, values, context=context)
        # manage attachments
        for attachment in attachments:
            attachment_data = {
                    'name': attachment[0],
                    'datas_fname': attachment[0],
                    'datas': attachment[1],
                    'res_model': 'mail.message',
                    'res_id': msg_id,
            }
            context.pop('default_type', None)
            attachment_ids.append(ir_attachment.create(cr, uid, attachment_data, context=context))
        if attachment_ids:
            values['attachment_ids'] = [(6, 0, attachment_ids)]
            mail_mail.write(cr, uid, msg_id, {'attachment_ids': [(6, 0, attachment_ids)]}, context=context)

        if force_send:
            mail_mail.send(cr, uid, [msg_id], context=context)
        return msg_id    