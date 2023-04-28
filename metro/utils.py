# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (C) 2012 OpenERP S.A. (<http://openerp.com>).
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

import threading
from openerp import pooler
from openerp.tools import mail
from openerp import SUPERUSER_ID
from openerp.osv import osv
from openerp.modules.registry import RegistryManager
from datetime import datetime
import time
import pytz
import logging
from openerp.tools import resolve_attr 
import openerp.tools as tools
from openerp.osv import fields

_logger = logging.getLogger(__name__)


def is_super_user(cr, uid):
    pool = pooler.get_pool(cr.dbname)
    user = pool.get('res.users').browse(cr, uid, uid)
    for group in user.groups_id:
        if group.id in (1, 2):
            return True
    return False

def get_user_language(cr, uid, context=None):
    if not context:
        context = {}
    lang_code = context.get('lang', False)
    if not lang_code:
        pool = pooler.get_pool(cr.dbname)
        user = pool.get("res.users").browse(cr, uid, uid, context=context)
        lang_code = user.lang
    return lang_code

def _format_file_name(file_name):
    file_reserved_char = ('/', '\\', '<', '>', '*', '?', '&','\'','"')
    new_file_name = file_name
    for char in file_reserved_char:
        new_file_name = new_file_name.replace(char, '-')
    return new_file_name

def dtstr_utc2local(cr, uid, dt_str, context=None):
    '''
    @param dt_str: UTC datetime string  of DEFAULT_SERVER_DATETIME_FORMAT format
    @return: Local(context['tz']) datetime string of DEFAULT_SERVER_DATETIME_FORMAT format
    '''
    dt_obj = datetime.strptime(dt_str, DEFAULT_SERVER_DATETIME_FORMAT)
    dt_obj = context_timestamp(cr, uid, dt_obj, context) 
    return datetime.strftime(dt_obj, DEFAULT_SERVER_DATETIME_FORMAT)

def dtstr_local2utc(cr, uid, dt_str, context=None):
    '''
    @param dt_str: Local(context['tz']) datetime string  of DEFAULT_SERVER_DATETIME_FORMAT format
    @return: UTC datetime string of DEFAULT_SERVER_DATETIME_FORMAT format
    '''
    dt_obj = datetime.strptime(dt_str, DEFAULT_SERVER_DATETIME_FORMAT)
    dt_obj = utc_timestamp(cr, uid, dt_obj, context) 
    return datetime.strftime(dt_obj, DEFAULT_SERVER_DATETIME_FORMAT)

def context_timestamp(cr, uid, timestamp, context=None):
    '''
    Convert utc timestamp to timestamp at TZ
    @param timestamp: UTC time
    @return: local time at TZ 
    '''
    return fields.datetime.context_timestamp(cr, uid, timestamp, context=context)    
                            
def utc_timestamp(cr, uid, timestamp, context=None):
    """Returns the given timestamp converted to the client's timezone.
       This method is *not* meant for use as a _defaults initializer,
       because datetime fields are automatically converted upon
       display on client side. For _defaults you :meth:`fields.datetime.now`
       should be used instead.

       :param datetime timestamp: naive datetime value (expressed in LOCAL)
                                  to be converted to the client timezone
       :param dict context: the 'tz' key in the context should give the
                            name of the User/Client timezone (otherwise
                            UTC is used)
       :rtype: datetime
       :return: timestamp converted to timezone-aware datetime in UTC
    """
    assert isinstance(timestamp, datetime), 'Datetime instance expected'
    if context and context.get('tz'):
        tz_name = context['tz']  
    else:
        registry = RegistryManager.get(cr.dbname)
        tz_name = registry.get('res.users').read(cr, SUPERUSER_ID, uid, ['tz'])['tz']
    if tz_name:
        try:
            utc = pytz.timezone('UTC')
            context_tz = pytz.timezone(tz_name)
            context_timestamp = context_tz.localize(timestamp, is_dst=False) # UTC = no DST
            return context_timestamp.astimezone(utc)
        except Exception:
            _logger.debug("failed to compute context/client-specific timestamp, "
                          "using the UTC value",
                          exc_info=True)
    return timestamp
    
def email_send_template(cr, uid, ids, email_vals, context=None):
    if 'email_template_name' in email_vals:
        threaded_email = threading.Thread(target=_email_send_template, args=(cr, uid, ids, email_vals, context))
        threaded_email.start()
    return True
def _email_send_template(cr, uid, ids, email_vals, context=None):       
    pool =  pooler.get_pool(cr.dbname)
    #As this function is in a new thread, i need to open a new cursor, because the old one may be closed
    new_cr = pooler.get_db(cr.dbname).cursor()
    #send email by template
    if 'email_template_name' in email_vals:
        email_tmpl_obj = pool.get('email.template')
        #check email user 
        if 'email_user_id' in email_vals:
            assignee = pool.get('res.users').browse(new_cr, uid, email_vals['email_user_id'], context=context)
            #only send email when user have email setup
            if not assignee.email:
                return False
        tmpl_ids = email_tmpl_obj.search(new_cr, uid, [('name','=',email_vals['email_template_name'])])
        if tmpl_ids:
            for id in ids:
                email_tmpl_obj.send_mail(new_cr, uid, tmpl_ids[0], id, force_send=True, context=context)
    #close the new cursor
    new_cr.close()
    return True

def email_send_group(cr, uid, email_from, email_to, subject, body, email_to_group_id=False, email_cc=None, context=None, attachments=None):
    if email_from and (email_to or email_to_group_id):
        threaded_email = threading.Thread(target=_email_send_group, args=(cr, uid, email_from, email_to, subject, body, email_to_group_id, email_cc, context, attachments))
        threaded_email.start()
    return True

def _email_send_group(cr, uid, email_from, email_to, subject, body, email_to_group_ids=False, email_cc=None, context=None, attachments=None):
    pool =  pooler.get_pool(cr.dbname)
    new_cr = pooler.get_db(cr.dbname).cursor()
    emails = []
    if email_to: 
        if isinstance(email_to, type(u' ')):
            emails.append(email_to)
        else:
            emails += email_to
    if email_to_group_ids: 
        #get the group user's addresses by group id
        group_obj = pool.get("res.groups")
        if not isinstance(email_to_group_ids, (list, int, long)):
            email_to_group_ids = long(email_to_group_ids)
        #we can use SUPERUSER_ID to ignore the record rule for res_users and res_partner,  the email should send to all users in the group.
#        group = group_obj.browse(new_cr,SUPERUSER_ID,email_to_group_id,context=context)
        if isinstance(email_to_group_ids, (int, long)):
            email_to_group_ids = [email_to_group_ids]
        groups = group_obj.browse(new_cr,uid,email_to_group_ids,context=context)
        emails = []
        for group in groups:
            emails += [user.email for user in group.users if user.email]
    if emails:
        #remove duplicated email address
        emails = list(set(emails))
        email_ccs = []
        if email_cc: 
            if isinstance(email_cc, type(u' ')):
                email_ccs.append(email_cc)
            else:
                email_ccs += email_cc
        #set all email from from the .conf, johnw, 01/07/2015
        email_from = tools.config.get('email_from')        
        mail.email_send(email_from, emails, subject, body, email_cc=email_ccs, attachments=attachments)
    #close the new cursor
    new_cr.close()        
    return True    

def email_notify(cr, uid, obj_name, obj_ids, actions, action, subject_fields = None, email_to = None, context=None):
    '''
    @param param:obj_name the model name that related to email, 'hr.holiday'
    @param param:object ids list, [1,2,3...]
    @param param:actions, one dict that define the action name and related message and groups
    actions = {'confirmed':{'msg':'need your approval','groups':['metro_purchase.group_pur_req_checker']},
                  'approved':{'msg':'approved, please issue PO','groups':['metro_purchase.group_pur_req_buyer']},
                  'rejected':{'msg':'was rejected, please check','groups':[]},
                  'in_purchase':{'msg':'is in purchasing','groups':[],},
                  'done':{'msg':'was done','groups':[]},
                  'cancel':{'msg':'was cancelled','groups':[]},
                  }  
    @param param: optional, subject_fields, one list that will generated the subject, if missing then user object.name
    @param email_to:optional, email to addresss
    '''
    pool =  pooler.get_pool(cr.dbname)
    model_obj = pool.get('ir.model.data')
    obj_obj = pool.get(obj_name)
    if actions.get(action,False):
        msg = actions[action].get('msg')
        group_params = actions[action].get('groups')
        for order in obj_obj.browse(cr, uid, obj_ids, context=context):
            #email to groups
            email_group_ids = []
            for group_param in group_params:
                grp_data = group_param.split('.')
                email_group_ids.append(model_obj.get_object_reference(cr, uid, grp_data[0], grp_data[1])[1])
            #email messages      
            subject_sub = ""       
            if not subject_fields:
                subject_sub = order._description
            else:
                for field in subject_fields:
                    subject_sub +=  '%s,'%(resolve_attr(order, field),)
            email_subject = '%s: %s %s'%(obj_obj._description, subject_sub, msg)
            email_body = email_subject
            #the current user is the from user
            email_from = pool.get("res.users").read(cr, uid, uid, ['email'],context=context)['email']
            #send emails
            email_send_group(cr, uid, email_from, email_to, email_subject,email_body, email_group_ids, context) 

class msg_tool(osv.TransientModel):
    _name = 'msg.tool'
    #msg_vals = {'subject':'111','body':'111222333444555','model':'purchase.order','res_id':1719}
    def send_msg(self, cr, uid, user_ids, msg_vals, unread = False, starred = False, group_ids = None, context=None):
        """ Process the wizard content and proceed with sending the related
            email(s), rendering any template patterns on the fly if needed. """
        if not user_ids and not group_ids:
            return None
        if context is None:
            context = {}        
        if user_ids is None:
            user_ids = []
        #fetch users from group
        if group_ids:
            groups = self.pool.get('res.groups').browse(cr, uid, group_ids, context=context)
            add_user_ids = []
            for group in groups:
                add_user_ids = [u.id for u in group.users]
            user_ids += add_user_ids
        #get partners
        users = self.pool.get('res.users').browse(cr, uid, user_ids, context=context)
        partner_ids = [u.partner_id.id for u in users]
        
        msg_vals['partner_ids'] = partner_ids
        # post the message
        subtype = 'mail.mt_comment'
        msg_id = self.pool.get('mail.thread').message_post(cr, uid, [0], type='comment', subtype=subtype, context=context, **msg_vals)
        upt_vals = {}
        if 'model' in msg_vals:
            upt_vals['model'] = msg_vals['model']
        if 'res_id' in msg_vals:
            upt_vals['res_id'] = msg_vals['res_id']
        if upt_vals:
            self.pool.get('mail.message').write(cr, uid, [msg_id], upt_vals, context=context)
        #set unread and star flag
        if unread:
            for user_id in user_ids:
                self.pool.get("mail.message").set_message_read(cr, user_id, [msg_id], False, context=context)
        if starred:
            for user_id in user_ids:
                self.pool.get("mail.message").set_message_starred(cr, user_id, [msg_id], True, context=context)

        return msg_id
    
    def test_msg(self,cr,uid,ids,context=None):
        (model, mail_group_id) = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_purchase', 'group_pur_req_manager')
        user_ids = [uid,37]
        group_ids=[mail_group_id]      
        msg_vals = {'subject':'Order approve','body':'Please help approve the purchase order','model':'purchase.order','res_id':1719}
        
        msg_tool = self.pool.get('msg.tool')
        msg_id = msg_tool.send_msg(cr, uid, [uid,37],msg_vals,unread=True,starred=True,group_ids=[mail_group_id],context=context)        

        '''
        #fetch users from group
        if group_ids:
            groups = self.pool.get('res.groups').browse(cr, uid, group_ids, context=context)
            add_user_ids = []
            for group in groups:
                add_user_ids = [u.id for u in group.users]
            user_ids += add_user_ids
        #get partners
        users = self.pool.get('res.users').browse(cr, uid, user_ids, context=context)
        partner_ids = [u.partner_id.id for u in users]
        msg_vals['partner_ids'] = partner_ids
               
        msg_id = self.pool.get('purchase.order').message_post(cr, uid, 1719, **msg_vals)
                        
        #set unread and star flag
        for user_id in user_ids:
            self.pool.get("mail.message").set_message_read(cr, user_id, [msg_id], False, context=context)
        for user_id in user_ids:
            self.pool.get("mail.message").set_message_starred(cr, user_id, [msg_id], True, context=context)
        '''
                                        
        print msg_id    
        
def field_get_file(self, cr, uid, ids, field_names, args, context=None):
    result = dict.fromkeys(ids, {})
    attachment_obj = self.pool.get('ir.attachment')
    for obj in self.browse(cr, uid, ids):
        result[obj.id] = {}
        for field_name in field_names:
            #+++ HoangTK - 11/13/2015: Fix downloading wrong pdf file content in drawing order line
            result[obj.id][field_name] = None
            if self._name == 'drawing.order.line':
                # if not (field_name == 'drawing_file' and obj.drawing_file_name) and \
                #     not (field_name == 'dxf_file' and obj.dxf_file_name):
                #     file_ids = attachment_obj.search(
                #     cr, uid, ['|', ('name', '=', field_name),
                #               ('res_name', '=', field_name),
                #               ('res_id', '=', obj.id),
                #               ('res_model', '=', self._name)], context=context)
                # elif field_name == 'drawing_file' and obj.drawing_file_name:
                #         file_ids = attachment_obj.search(
                #         cr, uid, ['|','|',('name', '=', field_name),
                #                   ('name', '=', obj.drawing_file_name),
                #                   ('res_name','=', obj.drawing_file_name),
                #                   ('res_id', '=', obj.id),
                #                   ('res_model', '=', self._name)],context=context)
                # elif field_name == 'dxf_file' and obj.dxf_file_name:
                #         file_ids = attachment_obj.search(
                #         cr, uid, ['|', '|', ('name', '=', field_name),
                #                   ('name', '=', obj.dxf_file_name),
                #                   ('res_name', '=', obj.dxf_file_name),
                #                   ('res_id', '=', obj.id),
                #                   ('res_model', '=', self._name)], context=context)
                if field_name == 'drawing_file':
                    file_ids = self.get_order_line_pdf_ids(cr, uid, obj.id, obj.drawing_file_name, context=context)
                elif field_name == 'dxf_file':
                    file_ids = self.get_order_line_dxf_ids(cr, uid, obj.id, obj.dxf_file_name, context=context)
                else:
                    file_ids = attachment_obj.search(
                         cr, uid, ['|', ('name', '=', field_name),
                                   ('res_name', '=', field_name),
                                   ('res_id', '=', obj.id),
                                   ('res_model', '=', self._name),
                                   ('store_fname', '!=', False)], order='create_date desc', context=context)
            elif self._name == 'drawing.order' and obj.name:
                file_ids = attachment_obj.search(
                cr, uid, ['|',('name', '=', field_name),
                          ('res_name','=', obj.name),
                          ('res_id', '=', obj.id),
                          ('res_model', '=', self._name)], order='create_date desc', context=context)
            else:
                #_logger.debug("_GET_FILE:-->Field:%s,id:%s,model:%s",field_name,obj.id,self._name)
                file_ids = attachment_obj.search(
                cr, uid, [('name', '=', field_name),
                          ('res_id', '=', obj.id),
                          ('res_model', '=', self._name)], order='create_date desc', context=context)
            #file_ids = attachment_obj.search(
            #    cr, uid, [('name', '=', field_name),
            #              ('res_id', '=', obj.id),
            #              ('res_model', '=', self._name)],context=context)
            #--- HoangTK - 11/13/2015
            if file_ids:
                _logger.debug("+++++GET_FILE:-->Field:%s,id:%s,model:%s, attach id: %s",field_name,obj.id,self._name,file_ids[0])
                result[obj.id][field_name] = attachment_obj.browse(cr, uid, file_ids[0]).datas
    return result

def field_set_file(self, cr, uid, id, field_name, value, args, context=None):
    attachment_obj = self.pool.get('ir.attachment')
    file_ids = attachment_obj.search(
    cr, uid, [('name', '=', field_name),
              ('res_id', '=', id),
              ('res_model', '=', self._name)])
    if file_ids:
        #+++ HoangTK - 03/18/2016 - Fix can not replace same file name
        file_id = file_ids[0]
        #HoangTK - Fix to only keep 1 attachment only for 1 field
        if len(file_ids) > 0:
            attachment_obj.unlink(cr, uid, file_ids[1:], context=context)
        #if args and args.get('unlink'):
        #    #called by related object's unlink method, need manual program on the model to call this method
        #    attachment_obj.unlink(cr, uid, [file_id], context=context)
        #else:
        attachment_obj.write(cr, uid, file_id, {'datas': value})
        #--- HoangTK - 03/18/2016 - Fix can not replace same file name
    else:
        attachment_vals = {'name': field_name,
                      'res_id': id,
                      'type': 'binary',
                      'res_model':self._name,
                      'datas': value}
        file_id = attachment_obj.create(
            cr, uid, attachment_vals)
    return file_id        

from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT

def deal_args_dt(cr, uid, obj,args,dt_fields,context=None):  
    new_args = []
    for arg in args:
        fld_name = arg[0]
        if fld_name in dt_fields:
            fld_operator = arg[1]
            fld_val = arg[2]
            fld = obj._columns.get(fld_name)
            if fld._type == 'datetime':
                if len(fld_val) == 10:
                    '''
                    ['date','=','2013-12-12] only supply the date part without time
                    ''' 
                    dt_val = datetime.strptime(fld_val + ' 00:00:00', DEFAULT_SERVER_DATETIME_FORMAT)
                    dt_val = utc_timestamp(cr, uid, dt_val, context=context)
                    fld_val = dt_val.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                if fld_val.endswith('00:00'):
                    if fld_operator == "=":
                        '''
                        ['date','=','2013-12-12 16:00:00'] the '16' was generated for the timezone
                        the user inputed is '2013-12-13 00:00:00', subtract 8 hours, then get this value
                        ''' 
                        time_start = [fld_name,'>=',fld_val]
                        time_obj = datetime.strptime(fld_val,DEFAULT_SERVER_DATETIME_FORMAT)
                        time_obj += relativedelta(days=1)
                        time_end = [fld_name,'<=',time_obj.strftime(DEFAULT_SERVER_DATETIME_FORMAT)]
                        new_args.append(time_start)
                        new_args.append(time_end)
                    elif fld_operator == "!=":
                        time_start = [fld_name,'<',fld_val]
                        time_obj = datetime.strptime(fld_val,DEFAULT_SERVER_DATETIME_FORMAT)
                        time_obj += relativedelta(days=1)
                        time_end = [fld_name,'>',time_obj.strftime(DEFAULT_SERVER_DATETIME_FORMAT)]
                        new_args.extend(['|', '|', [fld_name,'=',False], time_start, time_end])                    
                    else:
                        new_args.append(arg)
                else:
                    new_args.append(arg)
        else:
            new_args.append(arg) 
                    
            
#            if fld._type == 'datetime' and fld_operator == "=" and fld_val.endswith('00:00'):
#                '''
#                ['date','=','2013-12-12 16:00:00'] the '16' was generated for the timezone
#                the user inputed is '2013-12-13 00:00:00', subtract 8 hours, then get this value
#                ''' 
#                time_start = [fld_name,'>=',fld_val]
#                time_obj = datetime.strptime(fld_val,DEFAULT_SERVER_DATETIME_FORMAT)
#                time_obj += relativedelta(days=1)
#                time_end = [fld_name,'<=',time_obj.strftime(DEFAULT_SERVER_DATETIME_FORMAT)]
#                new_args.append(time_start)
#                new_args.append(time_end)
#            elif fld._type == 'datetime' and fld_operator == "=" and len(fld_val) == 10:
#                '''
#                ['date','=','2013-12-12] only supply the date part without time
#                ''' 
#                dt_val = datetime.strptime(fld_val + ' 00:00:00', DEFAULT_SERVER_DATETIME_FORMAT)
#                dt_val = utc_timestamp(cr, uid, dt_val, context=context)
#                fld_val = dt_val.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
#                
#                time_start = [fld_name,'>=',fld_val]
#                time_obj = datetime.strptime(fld_val,DEFAULT_SERVER_DATETIME_FORMAT)
#                time_obj += relativedelta(days=1)
#                time_end = [fld_name,'<=',time_obj.strftime(DEFAULT_SERVER_DATETIME_FORMAT)]
#                new_args.append(time_start)
#                new_args.append(time_end)
#            elif fld._type == 'datetime' and fld_operator == "!=" and fld_val.endswith('00:00'):
#                '''
#                ['date','=','2013-12-12 16:00:00'] the '16' was generated for the timezone
#                the user inputed is '2013-12-13 00:00:00', subtract 8 hours, then get this value
#                ''' 
#                time_start = [fld_name,'<',fld_val]
#                time_obj = datetime.strptime(fld_val,DEFAULT_SERVER_DATETIME_FORMAT)
#                time_obj += relativedelta(days=1)
#                time_end = [fld_name,'>',time_obj.strftime(DEFAULT_SERVER_DATETIME_FORMAT)]
#                new_args.extend(['|', [fld_name,'=',False], '&', time_start, time_end])
#            elif fld._type == 'datetime' and fld_operator == "!=" and len(fld_val) == 10:
#                '''
#                ['date','=','2013-12-12] only supply the date part without time
#                ''' 
#                dt_val = datetime.strptime(fld_val + ' 00:00:00', DEFAULT_SERVER_DATETIME_FORMAT)
#                dt_val = utc_timestamp(cr, uid, dt_val, context=context)
#                fld_val = dt_val.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
#                
#                time_start = [fld_name,'<',fld_val]
#                time_obj = datetime.strptime(fld_val,DEFAULT_SERVER_DATETIME_FORMAT)
#                time_obj += relativedelta(days=1)
#                time_end = [fld_name,'>',time_obj.strftime(DEFAULT_SERVER_DATETIME_FORMAT)]
#                new_args.extend(['|', [fld_name,'=',False], '&', time_start, time_end])
#            else:
#                new_args.append(arg)
#        else:
#            new_args.append(arg)    
          
        
    #TODO: refer fields.datetime.context_timestamp() to deal with the timezone
    #TODO: Improve the code in line#1014@osv/expression.py to handel the timezone for the datatime field:
    '''
                if field._type == 'datetime' and right and len(right) == 10:
                    if operator in ('>', '>='):
                        right += ' 00:00:00'
                    elif operator in ('<', '<='):
                        right += ' 23:59:59'
                    push(create_substitution_leaf(leaf, (left, operator, right), working_model))    
    '''
    return new_args

def set_seq(cr, uid, data, table_name=None, context=None):
    '''
    Set the new data sequence in the related model's create() or write method.
    @param data: the dict data will be create 
    @param table_name: table name
    '''
    if not data or data.get('sequence') and data['sequence'] > 0: 
        return
    #get max seq in db
    seq_max = 0
    cr.execute('select max(sequence) as seq from %s'%(table_name))
    seq_max = cr.fetchone()[0]
    if seq_max is None:
        seq_max = 0
    seq_max += 1
    data['sequence'] = seq_max
        
def set_seq_o2m(cr, uid, lines, m_table_name=None, o_id_name=None, o_id=None, context=None):
    '''
    Set the one2many list sequence in the 'one' in 'one2many' model's create() or write method.
    @param lines: one list that contains list of line of one2many lines  
    @param m_table_name: 'many' table name
    @param o_id_name: field name of 'many' table related to 'one' table
    @param o_id:'one' id value of field 'o_id_name'   
    '''
    '''
    line's format in lines:
    **create**:[0,False,{values...}]
    **write**:[1,%so_line_id%,{values...}]
    **delete**:[2, %so_line_id%, False]
    **no change**:[4, %so_line_id%, False]
    '''
    if not lines: 
        return
    #get max seq in db
    seq_max = 0
    if m_table_name and o_id_name and o_id:
        cr.execute('select max(sequence) as seq from %s where %s=%s'%(m_table_name, o_id_name, o_id))
        seq_max = cr.fetchone()[0]
        if seq_max is None:
            seq_max = 0
    #get max seq from saving data
    lines_deal = []
    for line in lines:
        data = line[2]
        if data and data.get('sequence') and data['sequence'] and seq_max < data['sequence']:
            seq_max = data['sequence']
        elif line[0] == 0:
            lines_deal.append(line)
    #generate the new seq
    for line in lines_deal:
        seq_max += 1
        line[2]['sequence'] = seq_max


class cnumber:
    cdict={}
    gdict={}
    xdict={}
    def __init__(self):
        self.cdict={1:u'',2:u'拾',3:u'佰',4:u'仟'}
        self.xdict={1:u'元',2:u'万',3:u'亿',4:u'兆'} #数字标识符
        self.gdict={0:u'零',1:u'壹',2:u'贰',3:u'叁',4:u'肆',5:u'伍',6:u'陆',7:u'柒',8:u'捌',9:u'玖'}       

    def csplit(self,cdata): #拆分函数，将整数字符串拆分成[亿，万，仟]的list
        g=len(cdata)%4
        csdata=[]
        lx=len(cdata)-1
        if g>0:
            csdata.append(cdata[0:g])
        k=g
        while k<=lx:
            csdata.append(cdata[k:k+4])
            k+=4
        return csdata
    
    def cschange(self,cki): #对[亿，万，仟]的list中每个字符串分组进行大写化再合并
        lenki=len(cki)
        i=0
        lk=lenki
        chk=u''
        for i in range(lenki):
            if int(cki[i])==0:
                if i<lenki-1:
                    if int(cki[i+1])!=0:
                        chk=chk+self.gdict[int(cki[i])]                    
            else:
                chk=chk+self.gdict[int(cki[i])]+self.cdict[lk]
            lk-=1
        return chk
        
    def cwchange(self,data_c):
        data=data_c.replace(',', '') #去掉    67,500.00   数字里面的','
        cdata=str(data).split('.')
        
        cki=cdata[0]
        ckj=cdata[1]
        i=0
        chk=u''
        cski=self.csplit(cki) #分解字符数组[亿，万，仟]三组List:['0000','0000','0000']
        ikl=len(cski) #获取拆分后的List长度
        #大写合并
        for i in range(ikl):
            if self.cschange(cski[i])=='': #有可能一个字符串全是0的情况
                chk=chk+self.cschange(cski[i]) #此时不需要将数字标识符引入
            else:
                chk=chk+self.cschange(cski[i])+self.xdict[ikl-i] #合并：前字符串大写+当前字符串大写+标识符
        #处理小数部分
        lenkj=len(ckj)
        if lenkj==1: #若小数只有1位
            if int(ckj[0])==0: 
                chk=chk+u'整'
            else:
                chk=chk+self.gdict[int(ckj[0])]+u'角整'
        else: #若小数有两位的四种情况
            if int(ckj[0])==0 and int(ckj[1])!=0:
                chk=chk+u'零'+self.gdict[int(ckj[1])]+u'分'
            elif int(ckj[0])==0 and int(ckj[1])==0:
                chk=chk+u'整'
            elif int(ckj[0])!=0 and int(ckj[1])!=0:
                chk=chk+self.gdict[int(ckj[0])]+u'角'+self.gdict[int(ckj[1])]+u'分'
            else:
                chk=chk+self.gdict[int(ckj[0])]+u'角整'
        return chk
      
#if __name__=='__main__':  #this is just for test
#    pt=cnumber()
#    print pt.cwchange('600190101000.80')