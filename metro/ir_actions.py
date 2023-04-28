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
import logging

from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from socket import gethostname
from openerp import tools, SUPERUSER_ID
from openerp import netsvc
from openerp.osv import fields,osv
from openerp.tools.safe_eval import safe_eval as eval
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

from openerp.tools.config import config

_logger = logging.getLogger(__name__)

class mail_notification(osv.Model):
    _name = 'mail.notification'
    _inherit = 'mail.notification'

    def _notify(self, cr, uid, msg_id, partners_to_notify=None, context=None):
        """ Send by email the notification depending on the user preferences

            :param list partners_to_notify: optional list of partner ids restricting
                the notifications to process
        """
        if context is None:
            context = {}
        mail_message_obj = self.pool.get('mail.message')

        # optional list of partners to notify: subscribe them if not already done or update the notification
        if partners_to_notify:
            notifications_to_update = []
            notified_partners = []
            notif_ids = self.search(cr, SUPERUSER_ID,
                                    [('message_id', '=', msg_id), ('partner_id', 'in', partners_to_notify)],
                                    context=context)
            for notification in self.browse(cr, SUPERUSER_ID, notif_ids, context=context):
                notified_partners.append(notification.partner_id.id)
                notifications_to_update.append(notification.id)
            partners_to_notify = filter(lambda item: item not in notified_partners, partners_to_notify)
            if notifications_to_update:
                self.write(cr, SUPERUSER_ID, notifications_to_update, {'read': False}, context=context)
            mail_message_obj.write(cr, uid, msg_id, {'notified_partner_ids': [(4, id) for id in partners_to_notify]},
                                   context=context)

        # mail_notify_noemail (do not send email) or no partner_ids: do not send, return
        if context.get('mail_notify_noemail'):
            return True
        # browse as SUPERUSER_ID because of access to res_partner not necessarily allowed
        msg = self.pool.get('mail.message').browse(cr, SUPERUSER_ID, msg_id, context=context)
        notify_partner_ids = self.get_partners_to_notify(cr, uid, msg, partners_to_notify=partners_to_notify,
                                                         context=context)
        if not notify_partner_ids:
            return True

        # add the context in the email
        # TDE FIXME: commented, to be improved in a future branch
        # quote_context = self.pool.get('mail.message').message_quote_context(cr, uid, msg_id, context=context)

        mail_mail = self.pool.get('mail.mail')
        # add signature
        body_html = msg.body
        # if quote_context:
        # body_html = tools.append_content_to_html(body_html, quote_context, plaintext=False)
        signature = msg.author_id and msg.author_id.user_ids and msg.author_id.user_ids[0].signature or ''
        if signature:
            body_html = tools.append_content_to_html(body_html, signature, plaintext=True, container_tag='div')

        # HoangTK - Use email from in message and use user email in reply-to
        # email_from: partner-user alias or partner email or mail.message email_from
        # if msg.author_id and msg.author_id.user_ids and msg.author_id.user_ids[0].alias_domain and \
        #         msg.author_id.user_ids[0].alias_name:
        #     email_from = '%s <%s@%s>' % (
        #     msg.author_id.name, msg.author_id.user_ids[0].alias_name, msg.author_id.user_ids[0].alias_domain)
        # elif msg.author_id:
        #     email_from = '%s <%s>' % (msg.author_id.name, msg.author_id.email)
        # else:
        #     email_from = msg.email_from
        email_from = config['email_from']

        if msg.email_from:
            email_from = msg.email_from
        elif msg.author_id and msg.author_id.user_ids and msg.author_id.user_ids[0].alias_domain and \
                msg.author_id.user_ids[0].alias_name:
            email_from = '%s <%s@%s>' % (
            msg.author_id.name, msg.author_id.user_ids[0].alias_name, msg.author_id.user_ids[0].alias_domain)
        elif msg.author_id:
            email_from = '%s <%s>' % (msg.author_id.name, msg.author_id.email)
        reply_to = False
        if msg.author_id and msg.author_id.user_ids and msg.author_id.user_ids[0].alias_domain and \
                msg.author_id.user_ids[0].alias_name:
            reply_to = '%s <%s@%s>' % (
                msg.author_id.name, msg.author_id.user_ids[0].alias_name, msg.author_id.user_ids[0].alias_domain)
        elif msg.author_id:
            reply_to = '%s <%s>' % (msg.author_id.name, msg.author_id.email)

        references = False
        if msg.parent_id:
            references = msg.parent_id.message_id

        mail_values = {
            'mail_message_id': msg.id,
            'auto_delete': False,
            'body_html': body_html,
            'email_from': email_from,
            'reply_to': reply_to,
            'references': references,
        }
        email_notif_id = mail_mail.create(cr, uid, mail_values, context=context)
        try:
            return mail_mail.send(cr, uid, [email_notif_id], recipient_ids=notify_partner_ids, context=context)
        except Exception:
            return False

class actions_server(osv.osv):  
    _name="ir.actions.server"
    _inherit = "ir.actions.server"
    _columns = {
        'email_cc': fields.char('CC Address', size=512),
        'email_bcc': fields.char('BCC Address', size=512, help="Expression that returns the email address to bcc. Can be based on the same values as for the condition field.\n"
                                                             "Example: object.invoice_address_id.email, or 'me@example.com'"),
        'email_reply_to': fields.char('Reply To Address', size=512, help="Expression that returns the email address to reply to. Can be based on the same values as for the condition field.\n"
                                                             "Example: object.invoice_address_id.email, or 'me@example.com'"),
        'email_subtype': fields.selection([('plain','Plain'),('html','Html')], 'Content Type', help="The contenct type of the email", select=True),                
    }
    def _action_email(self,cr,uid,user,action,cxt,context=None):
        email_from = config['email_from']
        if not email_from:
            _logger.debug('--email-from command line option is not specified, using a fallback value instead.')
            if user.email:
                email_from = user.email
            else:
                email_from = "%s@%s" % (user.login, gethostname())

        try:
            address = eval(str(action.email), cxt)
        except Exception:
            address = str(action.email)
            
        try:
            address_cc = eval(str(action.email_cc), cxt)
        except Exception:
            address_cc = str(action.email_cc)
            
        try:
            address_bcc = eval(str(action.email_bcc), cxt)
        except Exception:
            address_bcc = str(action.email_bcc)
            
        try:
            address_reply_to = eval(str(action.email_reply_to), cxt)
        except Exception:
            address_reply_to = str(action.email_reply_to)

        if not address:
            _logger.info('No to email address specified, not sending any email.')
            return

        # handle single and multiple recipient addresses
        addresses = address if isinstance(address, (tuple, list)) else [address]
        address_cces = None
        if address_cc:
            address_cces = address_cc if isinstance(address_cc, (tuple, list)) else [address_cc]
        addresses_bcces = None
        if address_bcc:
            address_bcc if isinstance(address_bcc, (tuple, list)) else [address_bcc]
        address_reply_toes = None
        if address_reply_to:
            address_reply_toes = address_reply_to if address_reply_to else None

        email_subtype = action.email_subtype or 'plain';
                
        subject = self.merge_message(cr, uid, action.subject, action, context)
        body = self.merge_message(cr, uid, action.message, action, context)

        ir_mail_server = self.pool.get('ir.mail_server')
        msg = ir_mail_server.build_email(email_from, addresses, subject, body,
                                         email_cc = address_cces, email_bcc = addresses_bcces, reply_to = address_reply_toes,
                                         subtype = email_subtype)
               
        res_email = ir_mail_server.send_email(cr, uid, msg)
        if res_email:
            _logger.info('Email successfully sent to: %s', addresses)
        else:
            _logger.warning('Failed to send email to: %s', addresses)        
    # Context should contains:
    #   ids : original ids
    #   id  : current id of the object
    # OUT:
    #   False : Finished correctly
    #   ACTION_ID : Action to launch

    # FIXME: refactor all the eval() calls in run()!
    def run(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        user = self.pool.get('res.users').browse(cr, uid, uid)
        for action in self.browse(cr, uid, ids, context):
            obj = None
            obj_pool = self.pool.get(action.model_id.model)
            if context.get('active_model') == action.model_id.model and context.get('active_id'):
                obj = obj_pool.browse(cr, uid, context['active_id'], context=context)
            cxt = {
                'self': obj_pool,
                'object': obj,
                'obj': obj,
                'pool': self.pool,
                'time': time,
                'cr': cr,
                'context': dict(context), # copy context to prevent side-effects of eval
                'uid': uid,
                'user': user
            }
            expr = eval(str(action.condition), cxt)
            if not expr:
                continue

            if action.state=='client_action':
                if not action.action_id:
                    raise osv.except_osv(_('Error'), _("Please specify an action to launch !"))
                return self.pool.get(action.action_id.type)\
                    .read(cr, uid, action.action_id.id, context=context)

            if action.state=='code':
                eval(action.code.strip(), cxt, mode="exec", nocopy=True) # nocopy allows to return 'action'
                if 'action' in cxt:
                    return cxt['action']

            if action.state == 'email':
                #comment by johnw@2013/12/18 use the _action_email() method to replace
                '''
                email_from = config['email_from']
                if not email_from:
                    _logger.debug('--email-from command line option is not specified, using a fallback value instead.')
                    if user.email:
                        email_from = user.email
                    else:
                        email_from = "%s@%s" % (user.login, gethostname())

                try:
                    address = eval(str(action.email), cxt)
                except Exception:
                    address = str(action.email)

                if not address:
                    _logger.info('No partner email address specified, not sending any email.')
                    continue

                # handle single and multiple recipient addresses
                addresses = address if isinstance(address, (tuple, list)) else [address]
                subject = self.merge_message(cr, uid, action.subject, action, context)
                body = self.merge_message(cr, uid, action.message, action, context)

                ir_mail_server = self.pool.get('ir.mail_server')
                msg = ir_mail_server.build_email(email_from, addresses, subject, body)
                res_email = ir_mail_server.send_email(cr, uid, msg)
                if res_email:
                    _logger.info('Email successfully sent to: %s', addresses)
                else:
                    _logger.warning('Failed to send email to: %s', addresses)
                '''
                self._action_email(cr,uid,user,action,cxt,context=context)

            if action.state == 'trigger':
                wf_service = netsvc.LocalService("workflow")
                model = action.wkf_model_id.model
                m2o_field_name = action.trigger_obj_id.name
                target_id = obj_pool.read(cr, uid, context.get('active_id'), [m2o_field_name])[m2o_field_name]
                target_id = target_id[0] if isinstance(target_id,tuple) else target_id
                wf_service.trg_validate(uid, model, int(target_id), action.trigger_name, cr)

            if action.state == 'sms':
                #TODO: set the user and password from the system
                # for the sms gateway user / password
                # USE smsclient module from extra-addons
                _logger.warning('SMS Facility has not been implemented yet. Use smsclient module!')

            if action.state == 'other':
                res = []
                for act in action.child_ids:
                    context['active_id'] = context['active_ids'][0]
                    result = self.run(cr, uid, [act.id], context)
                    if result:
                        res.append(result)
                return res

            if action.state == 'loop':
                expr = eval(str(action.expression), cxt)
                context['object'] = obj
                for i in expr:
                    context['active_id'] = i.id
                    self.run(cr, uid, [action.loop_action.id], context)

            if action.state == 'object_write':
                res = {}
                for exp in action.fields_lines:
                    euq = exp.value
                    if exp.type == 'equation':
                        expr = eval(euq, cxt)
                    else:
                        expr = exp.value
                    res[exp.col1.name] = expr

                if not action.write_id:
                    if not action.srcmodel_id:
                        obj_pool = self.pool.get(action.model_id.model)
                        obj_pool.write(cr, uid, [context.get('active_id')], res)
                    else:
                        write_id = context.get('active_id')
                        obj_pool = self.pool.get(action.srcmodel_id.model)
                        obj_pool.write(cr, uid, [write_id], res)

                elif action.write_id:
                    obj_pool = self.pool.get(action.srcmodel_id.model)
                    rec = self.pool.get(action.model_id.model).browse(cr, uid, context.get('active_id'))
                    id = eval(action.write_id, {'object': rec})
                    try:
                        id = int(id)
                    except:
                        raise osv.except_osv(_('Error'), _("Problem in configuration `Record Id` in Server Action!"))

                    if type(id) != type(1):
                        raise osv.except_osv(_('Error'), _("Problem in configuration `Record Id` in Server Action!"))
                    write_id = id
                    obj_pool.write(cr, uid, [write_id], res)

            if action.state == 'object_create':
                res = {}
                for exp in action.fields_lines:
                    euq = exp.value
                    if exp.type == 'equation':
                        expr = eval(euq, cxt)
                    else:
                        expr = exp.value
                    res[exp.col1.name] = expr

                obj_pool = self.pool.get(action.srcmodel_id.model)
                res_id = obj_pool.create(cr, uid, res)
                if action.record_id:
                    self.pool.get(action.model_id.model).write(cr, uid, [context.get('active_id')], {action.record_id.name:res_id})

            if action.state == 'object_copy':
                res = {}
                for exp in action.fields_lines:
                    euq = exp.value
                    if exp.type == 'equation':
                        expr = eval(euq, cxt)
                    else:
                        expr = exp.value
                    res[exp.col1.name] = expr

                model = action.copy_object.split(',')[0]
                cid = action.copy_object.split(',')[1]
                obj_pool = self.pool.get(model)
                obj_pool.copy(cr, uid, int(cid), res)

        return False    
actions_server()  