# -*- encoding: utf-8 -*-
from openerp.osv import fields,osv
from openerp.tools.translate import _
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT,DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime
from openerp import netsvc
from openerp.addons.metro_mrp_drawing.drawing_order import PART_TYPE_SELECTION
from openerp.osv.orm import browse_record, browse_null
from openerp import tools
from math import ceil
from openerp import SUPERUSER_ID
from openerp.addons.metro import utils
import base64
import math
import zipfile
import os
import tempfile
import logging
from urllib import urlencode, quote as quote
from openerp.tools.config import config
from socket import gethostname
import time
import xlwt
_logger = logging.getLogger(__name__)


MAX_ATTACHMENT_SIZE = 10000000
MAX_ATTACHMENTS_PER_EMAIL = 5

try:
    # We use a jinja2 sandboxed environment to render mako templates.
    # Note that the rendering does not cover all the mako syntax, in particular
    # arbitrary Python statements are not accepted, and not all expressions are
    # allowed: only "public" attributes (not starting with '_') of objects may
    # be accessed.
    # This is done on purpose: it prevents incidental or malicious execution of
    # Python code that may break the security of the server.
    from jinja2.sandbox import SandboxedEnvironment
    mako_template_env = SandboxedEnvironment(
        block_start_string="<%",
        block_end_string="%>",
        variable_start_string="${",
        variable_end_string="}",
        comment_start_string="<%doc>",
        comment_end_string="</%doc>",
        line_statement_prefix="%",
        line_comment_prefix="##",
        trim_blocks=True,               # do not output newline after blocks
        autoescape=True,                # XML/HTML automatic escaping
    )
    mako_template_env.globals.update({
        'str': str,
        'quote': quote,
        'urlencode': urlencode,
    })
except ImportError:
    _logger.warning("jinja2 not available, templating features will not work!")

class mail_compose_message(osv.TransientModel):
    _name = 'mail.compose.message'
    _inherit = 'mail.compose.message'

    def get_zip_size(self, zip_file):
        zip_size = 0
        for info in zip_file.infolist():
            zip_size += info.compress_size
        return zip_size

    def zip_attachments(self, cr, uid, attachment_ids, zip_file_name, context=None):
        if context is None:
            context = {}
        result_zip_attachment_ids = []
        ir_attachment_obj = self.pool.get('ir.attachment')
        attachments = ir_attachment_obj.browse(cr, uid, attachment_ids, context=context)
        if not attachments:
            return result_zip_attachment_ids
        zip_file = False
        attachment_length = len(attachments)
        index = 0
        temp_attachment_file_names = []
        temp_zip_file_name = False
        while index < attachment_length:
            attachment = attachments[index]
            if attachment.res_model == 'drawing.order.line':
                if not zip_file:
                    temp_zip_file = tempfile.NamedTemporaryFile(delete=False)
                    temp_zip_file_name = temp_zip_file.name
                    temp_zip_file.close()
                    zip_file = zipfile.ZipFile(temp_zip_file_name, 'w', zipfile.ZIP_DEFLATED)
                attach_file = ir_attachment_obj.file_get(cr, uid, attachment.id, context=context)
                temp_attachment_file = tempfile.NamedTemporaryFile(delete=False)
                temp_attachment_file_name = temp_attachment_file.name
                temp_attachment_file_names.append(temp_attachment_file_name)
                temp_attachment_file.close()
                open(temp_attachment_file_name, "wb").write(attach_file.read())
                zip_attachment_file_name = attachment.name
                if attachment.datas_fname not in ['drawing_file', 'dxf_file']:
                    zip_attachment_file_name = attachment.datas_fname
                zip_file.write(temp_attachment_file_name, zip_attachment_file_name)
                zip_size = self.get_zip_size(zip_file)
                if zip_size >= MAX_ATTACHMENT_SIZE or index == attachment_length - 1:
                    zip_attachment_id = ir_attachment_obj.copy(cr, uid, attachment.id, {'datas': False,
                                                                                        'datas_fname': zip_file_name,
                                                                                        'name': zip_file_name,
                                                                                        })
                    zip_file.close()
                    zip_file_data = open(temp_zip_file_name, 'rb').read().encode('base64')
                    os.remove(temp_zip_file_name)
                    for temp_attachment_file_name in temp_attachment_file_names:
                        if os.path.isfile(temp_attachment_file_name):
                            os.remove(temp_attachment_file_name)
                    ir_attachment_obj.write(cr, uid, [zip_attachment_id], {
                        'datas': zip_file_data
                    })
                    result_zip_attachment_ids.append(zip_attachment_id)
                    zip_file = False
                    temp_attachment_file_names = []
            index += 1

        return result_zip_attachment_ids

    def zip_attachment(self, cr, uid, attachment_ids, zip_file_name, context=None):
        if context is None:
            context = {}
        zip_attachment_id = False
        ir_attachment_obj = self.pool.get('ir.attachment')
        attachments = ir_attachment_obj.browse(cr, uid, attachment_ids, context=context)
        if not attachments:
            return zip_attachment_id
        temp_zip_file = tempfile.NamedTemporaryFile(delete=False)
        temp_zip_file_name = temp_zip_file.name
        temp_zip_file.close()
        zip_file = zipfile.ZipFile(temp_zip_file_name, 'w', zipfile.ZIP_DEFLATED)
        temp_attachment_file_names = []
        result_attachment_ids = []
        for attachment in attachments:
            if not zip_attachment_id:
                zip_attachment_id = ir_attachment_obj.copy(cr, uid, attachment.id, {'datas': False,
                                                                                    'datas_fname': zip_file_name,
                                                                                    'name': zip_file_name,
                                                                                    })
            if attachment.res_model != 'drawing.order.line':
                result_attachment_ids.append(attachment.id)
                continue
            attach_file = ir_attachment_obj.file_get(cr, uid, attachment.id, context=context)
            temp_attachment_file = tempfile.NamedTemporaryFile(delete=False)
            temp_attachment_file_name = temp_attachment_file.name
            temp_attachment_file_names.append(temp_attachment_file_name)
            temp_attachment_file.close()
            open(temp_attachment_file_name, "wb").write(attach_file.read())
            zip_attachment_file_name = attachment.name
            if attachment.datas_fname not in ['drawing_file','dxf_file']:
                zip_attachment_file_name = attachment.datas_fname
            zip_file.write(temp_attachment_file_name, zip_attachment_file_name)

        zip_file.close()
        zip_file_data = open(temp_zip_file_name, 'rb').read().encode('base64')
        os.remove(temp_zip_file_name)
        for temp_attachment_file_name in temp_attachment_file_names:
            if os.path.isfile(temp_attachment_file_name):
                os.remove(temp_attachment_file_name)
        if zip_attachment_id:
            ir_attachment_obj.write(cr, uid, [zip_attachment_id], {
                'datas': zip_file_data
            })
            result_attachment_ids.append(zip_attachment_id)
        return result_attachment_ids

    def send_mail(self, cr, uid, ids, context=None):
        """ Process the wizard content and proceed with sending the related
            email(s), rendering any template patterns on the fly if needed. """
        if context is None:
            context = {}
        ir_attachment_obj = self.pool.get('ir.attachment')
        active_ids = context.get('active_ids')
        is_log = context.get('mail_compose_log', False)
        attach_pdf = context.get('attach_pdf', False)
        attach_dxf = context.get('attach_dxf', False)
        # Update email from and email
        email_from = config['email_from']
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user.email:
            user_email = user.email
        else:
            user_email = "%s@%s" % (user.login, gethostname())
        user_name = user.name
        for wizard in self.browse(cr, uid, ids, context=context):
            mass_mail_mode = wizard.composition_mode == 'mass_mail'
            active_model_pool_name = wizard.model if wizard.model else 'mail.thread'
            active_model_pool = self.pool.get(active_model_pool_name)
            attachment_names = []
            # wizard works in batch mode: [res_id] or active_ids
            res_ids = active_ids if mass_mail_mode and wizard.model and active_ids else [wizard.res_id]
            for res_id in res_ids:
                # mail.message values, according to the wizard options
                post_values = {
                    'subject': wizard.subject,
                    'body': wizard.body,
                    'parent_id': wizard.parent_id and wizard.parent_id.id,
                    'partner_ids': [partner.id for partner in wizard.partner_ids],
                    'attachment_ids': [attach.id for attach in wizard.attachment_ids],
                }
                # mass mailing: render and override default values
                if mass_mail_mode and wizard.model:
                    email_dict = self.render_message(cr, uid, wizard, res_id, context=context)
                    post_values['partner_ids'] += email_dict.pop('partner_ids', [])
                    post_values['attachments'] = email_dict.pop('attachments', [])
                    attachment_ids = []
                    for attach_id in post_values.pop('attachment_ids'):
                        new_attach_id = ir_attachment_obj.copy(cr, uid, attach_id,
                                                               {'res_model': self._name, 'res_id': wizard.id},
                                                               context=context)
                        attachment_ids.append(new_attach_id)
                    post_values['attachment_ids'] = attachment_ids
                    post_values.update(email_dict)

                if email_from:
                    post_values.update({'email_from': email_from})
                if user_email:
                    post_values.update({'reply_to': user_email})
                # post the message
                subtype = 'mail.mt_comment'
                if is_log:  # log a note: subtype is False
                    subtype = False
                elif mass_mail_mode:  # mass mail: is a log pushed to recipients, author not added
                    subtype = False
                    context = dict(context, mail_create_nosubscribe=True)  # add context key to avoid subscribing the author
                # Split the attachment_ids so it won't exceed 15MB
                #attachment_groups = {0: {'size': 0, 'attachment_ids': []}}
                #group_index = 0
                #for attachment in ir_attachment_obj.browse(cr, uid, post_values['attachment_ids'], context=context):
                #    if attachment.res_model == 'drawing.order.line':
                #        attachment_names.append(attachment.name)
                #    if attachment.datas:
                #        #attachment_size = math.ceil(3.0 * len(attachment.datas) / 4)
                #        attachment_size = attachment.file_size
                #        if attachment_groups[group_index]['size'] + attachment_size < MAX_ATTACHMENT_SIZE:
                #            attachment_groups[group_index]['size'] += attachment_size
                #            attachment_groups[group_index]['attachment_ids'].append(attachment.id)
                #        else:
                #            group_index += 1
                #            attachment_groups[group_index] = {
                #                'size': attachment_size,
                #                'attachment_ids': [attachment.id]
                #            }
                msg_ids = []

                #for group in range(group_index + 1):
                #    new_post_values = post_values.copy()
                #    attachment_with_zip_ids = []
                #    if group_index >= 1:
                #        new_post_values['subject'] = '%s - %s'%(new_post_values['subject'],group+1)
                #    if len(attachment_groups[group]['attachment_ids']) > MAX_ATTACHMENTS_PER_EMAIL:
                #        # Do zip the attachments
                #        if active_model_pool_name == 'purchase.order':
                #            order = active_model_pool.browse(cr, uid, res_id)
                #            zip_file_name = '%s.zip' % order.name
                #        else:
                #            zip_file_name = '%s.zip'%new_post_values['subject']
                #        attachment_with_zip_ids = self.zip_attachment(cr, uid, attachment_groups[group]['attachment_ids'],
                #                                                zip_file_name, context=context)
                #    if attachment_with_zip_ids:
                #        #ir_attachment_obj.unlink(cr, uid, attachment_groups[group]['attachment_ids'], context=context)
                #        new_post_values['attachment_ids'] = attachment_with_zip_ids
                #    else:
                #        new_post_values['attachment_ids'] = attachment_groups[group]['attachment_ids']
                #    msg_id = active_model_pool.message_post(cr, uid, [res_id], type='comment', subtype=subtype, context=context,
                #                                        **new_post_values)
                #    msg_ids.append(msg_id)
                attachment_ids = post_values['attachment_ids']
                need_zip_attachment_ids = []
                no_zip_attachment_ids = []
                for attachment in ir_attachment_obj.browse(cr, uid, attachment_ids, context=context):
                    if attachment.res_model == 'drawing.order.line':
                        attachment_names.append(attachment.name)
                        need_zip_attachment_ids.append(attachment.id)
                    else:
                        no_zip_attachment_ids.append(attachment.id)
                zip_file_name = 'Attachments.zip'
                if active_model_pool_name == 'purchase.order':
                    order = active_model_pool.browse(cr, uid, res_id)
                    zip_file_name = '%s.zip' % order.name
                zip_attachment_ids = self.zip_attachments(cr, uid, need_zip_attachment_ids, zip_file_name, context=context)
                zip_len = len(zip_attachment_ids)
                if zip_len > 0:
                    first_email = True
                    for index in range(0, zip_len):
                        zip_attachment_id = zip_attachment_ids[index]
                        new_post_values = post_values.copy()
                        if zip_len > 1:
                            new_post_values['subject'] = '%s - %s'%(new_post_values['subject'],index+1)
                        if first_email:
                            first_email = False
                            if no_zip_attachment_ids:
                                no_zip_attachment_ids.append(zip_attachment_id)
                                new_post_values['attachment_ids'] = no_zip_attachment_ids
                            else:
                                new_post_values['attachment_ids'] = [zip_attachment_id]
                        else:
                            new_post_values['attachment_ids'] = [zip_attachment_id]
                        msg_id = active_model_pool.message_post(cr, uid, [res_id], type='comment', subtype=subtype, context=context,
                                                            **new_post_values)
                        msg_ids.append(msg_id)
                else:
                    msg_id = active_model_pool.message_post(cr, uid, [res_id], type='comment', subtype=subtype,
                                                            context=context,
                                                            **post_values)
                    msg_ids.append(msg_id)
                # mass_mailing: notify specific partners, because subtype was False, and no-one was notified
                if mass_mail_mode and post_values['partner_ids']:
                    for msg_id in msg_ids:
                        self.pool.get('mail.notification')._notify(cr, uid, msg_id, post_values['partner_ids'], context=context)
            if active_model_pool_name == 'pur.req':
                active_model_pool.write(cr, uid, res_ids, {'rfq_sent': True}, context=context)
            if active_model_pool_name == 'purchase.order' and (attach_pdf or attach_dxf):
                supplier_names = [partner.name for partner in wizard.partner_ids]
                supplier_emails = [partner.email for partner in wizard.partner_ids]
                email_content = {'subject': 'A user has sent pdfs and dxfs to a supplier ',
                                 'body': 'User %s has send %s with DXF and PDF files to Supplier %s to email %s'%
                                            (user_name
                                             ,','.join(attachment_names)
                                             ,','.join(supplier_names)
                                             ,','.join(supplier_emails))
                                 }
                model_obj = self.pool.get('ir.model.data')
                monitor_group_id = model_obj.get_object_reference(cr, uid, "metro", "group_metro_pdf_dxf_monitor")[1]
                utils.email_send_group(cr, uid, email_from, '', email_content['subject']
                                       , email_content['subject'], email_to_group_id=monitor_group_id)
        return {'type': 'ir.actions.act_window_close'}


class email_template(osv.osv):
    _name = "email.template"
    _inherit = "email.template"

    def render_template(self, cr, uid, template, model, res_id, context=None):
        """Render the given template text, replace mako expressions ``${expr}``
           with the result of evaluating these expressions with
           an evaluation context containing:

                * ``user``: browse_record of the current user
                * ``object``: browse_record of the document record this mail is
                              related to
                * ``context``: the context passed to the mail composition wizard

           :param str template: the template text to render
           :param str model: model name of the document record this mail is related to.
           :param int res_id: id of the document record this mail is related to.
        """
        if not template:
            return u""
        if context is None:
            context = {}
        try:
            template = tools.ustr(template)
            record = None
            if res_id:
                record = self.pool.get(model).browse(cr, uid, res_id, context=context)
            user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
            variables = {
                'object': record,
                'user': user,
                'ctx': context,  # context kw would clash with mako internals
            }
            #TODO: Get the pR lines object and pass to variables
            if model == 'pur.req':
                pr_line_ids = context.get('pr_line_ids',[])
                if not pr_line_ids:
                    pr_lines = record.line_ids

                else:
                    pur_req_line_obj = self.pool.get('pur.req.line')
                    pr_lines = pur_req_line_obj.browse(cr, uid, pr_line_ids, context=context)
                variables.update({'pr_lines': pr_lines})
            result = mako_template_env.from_string(template).render(variables)
            if result == u"False":
                result = u""
            return result
        except Exception:
            _logger.exception("failed to render mako template value %r", template)
            return u""

    def add_watermark_to_attachments(self, cr, uid, attachment_ids, context=None):
        company_obj = self.pool.get('res.company')
        company_obj.add_watermark_to_attachments(cr, uid, attachment_ids,
                                                 stamp_pos_x=0,
                                                 stamp_pos_y=0,
                                                 stamp_size=110,
                                                 date_x=False,
                                                 date_y=False,
                                                 sign_date=False,
                                                 user_sign_x=False,
                                                 user_sign_y=False,
                                                 user_sign_width=False,
                                                 user_sign_height=False,
                                                 user_sign=False
                                                 )
        return True

    def get_pdf_dxf_attachments(self, cr, uid, order_line_ids, attach_dxf, attach_pdf, context=None):
        attachment_ids = []
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        attachment_obj = self.pool.get('ir.attachment')
        for order_line_id in order_line_ids:
            if order_line_id:
                if attach_pdf and order_line_id.drawing_file_name:
                    file_ids = drawing_order_line_obj.get_order_line_pdf_ids(cr, uid, order_line_id.id, order_line_id.drawing_file_name)
                    if file_ids:
                        attachment_ids.append(file_ids[0])
                        #Check if attachment name is corrected ?
                        attachment = attachment_obj.browse(cr, uid, file_ids[0], context=context)
                        if attachment.name == 'drawing_file':
                            attachment_obj.write(cr, uid, [file_ids[0]], {'name': order_line_id.drawing_file_name,
                                                                          'datas_fname': order_line_id.drawing_file_name})
                if attach_dxf and order_line_id.dxf_file_name:
                    file_ids = drawing_order_line_obj.get_order_line_dxf_ids(cr, uid, order_line_id.id,
                                                                             order_line_id.dxf_file_name)
                    if file_ids:
                        attachment_ids.append(file_ids[0])
                        # Check if attachment name is corrected ?
                        attachment = attachment_obj.browse(cr, uid, file_ids[0], context=context)
                        if attachment.name == 'dxf_file':
                            attachment_obj.write(cr, uid, [file_ids[0]], {'name': order_line_id.dxf_file_name,
                                                                          'datas_fname': order_line_id.dxf_file_name})
        return attachment_ids

    def get_bom_xls_attachment(self, cr, uid, po, context=None):
        attachment_id = False
        if po:
            do_name = ''
            if po.unit:
                do_name = po.unit.name
            mfg_ids = [mfg_id.name for mfg_id in po.sale_product_ids]
            workbook = xlwt.Workbook()
            sheet = workbook.add_sheet("CNC BOM")
            sheet.write(0, 0,
                        'CNC Requisition for %s (ID %s)'%(do_name, ','.join(mfg_ids)))
            sheet.write(1, 0, 'ITEM NO')
            sheet.write(1, 1, 'PART NUMBER')
            sheet.write(1, 2, 'DESCRIPTION')
            sheet.write(1, 3, 'QUANTITY')
            sheet.write(1, 4, 'MATERIAL')
            sheet.write(1, 5, 'THICKNESS/LENGTH')
            sheet.write(1, 6, 'TOTAL QTY')
            sheet.write(1, 7, 'FILE NAME')
            sheet.write(1, 8, 'DEPARTMENTS')
            attachment_obj = self.pool.get('ir.attachment')

            sequence = 0
            row = 2
            for line in po.order_line:
                sequence += 1
                sheet.write(row, 0, sequence)
                if line.order_line_id:
                    sheet.write(row, 1, line.order_line_id.part_number)
                    sheet.write(row, 2, line.order_line_id.description)
                    sheet.write(row, 4, line.order_line_id.material)
                    sheet.write(row, 5, line.order_line_id.thickness)
                    if line.order_line_id.drawing_file_name and line.order_line_id.pdf_valid:
                        sheet.write(row, 7, line.order_line_id.drawing_file_name)
                    sheet.write(row, 8, line.order_line_id.work_steps)
                else:
                    sheet.write(row, 1, line.product_id.name)
                    sheet.write(row, 2, line.name)
                sheet.write(row, 3, line.product_qty)
                row += 1
            temp_xls_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xls')
            temp_xls_file_name = temp_xls_file.name
            temp_xls_file.close()
            workbook.save(temp_xls_file_name)
            bom_xls_name = 'CNC BOM-%s.xls'% po.name
            xls_data = open(temp_xls_file_name, 'rb').read().encode('base64')
            attachment_id = attachment_obj.create(cr, uid, {
                'res_id': po.id,
                'res_model': 'purchase.order',
                'name': bom_xls_name,
                'datas': xls_data,
                'datas_fname': bom_xls_name,

            }, context=context)
            os.remove(temp_xls_file_name)

        return attachment_id

    def generate_email(self, cr, uid, template_id, res_id, context=None):
        values = super(email_template, self).generate_email(cr, uid, template_id, res_id, context=context)
        if not context:
            context={}
        # Add POEM pdf
        model = context.get('default_model', context.get('active_model'))
        res_id = context.get('default_res_id', context.get('active_id'))
        ir_actions_report = self.pool.get('ir.actions.report.xml')
        attachment_obj = self.pool.get('ir.attachment')
        attachment_ids = []
        pdf_dxf_attachment_names = []
        attach_pdf = context.get('attach_pdf', False)
        attach_dxf = context.get('attach_dxf', False)
        add_watermark = context.get('add_watermark', False)
        attach_bom_xls = context.get('attach_bom_xls', False)
        if res_id:
            if model == 'pur.req':
                pr_line_ids = context.get('pr_line_ids',[])
                pur_req_obj = self.pool.get('pur.req')
                pur_req_line_obj = self.pool.get('pur.req.line')
                req = pur_req_obj.browse(cr, uid, res_id, context=context)
                # Attach the report with selected pr lines
                matching_reports = ir_actions_report.search(cr, uid, [('name', '=', 'report.pr.mfg.form')])
                if matching_reports:
                    report = ir_actions_report.browse(cr, uid, matching_reports[0])
                    report_service = 'report.' + report.report_name
                    service = netsvc.LocalService(report_service)
                    (result, format) = service.create(cr, uid, [res_id], {'model': 'pur.req'}, context=context)
                    eval_context = {'time': time, 'object': req}
                    if not report.attachment or not eval(report.attachment, eval_context):
                        # no auto-saving of report as attachment, need to do it manually
                        result = base64.b64encode(result)
                        file_name = "PR MFG Form.pdf"
                        attachment_id = attachment_obj.create(cr, uid,
                                                              {
                                                                  'name': file_name,
                                                                  'datas': result,
                                                                  'datas_fname': file_name,
                                                                  'res_model': 'pur.req',
                                                                  'res_id': req.id,
                                                                  'type': 'binary'
                                                              }, context=context)
                        attachment_ids.append(attachment_id)
                pr_lines = pur_req_line_obj.browse(cr, uid, pr_line_ids, context=context)
                order_line_ids = []
                for line in pr_lines:
                    if line.order_line_id:
                        order_line_ids.append(line.order_line_id)
                pdf_dxf_attachment_ids = self.get_pdf_dxf_attachments(cr, uid, order_line_ids, attach_dxf, attach_pdf, context)
                attachment_ids.append(pdf_dxf_attachment_ids)

            elif model == 'purchase.order':
                po_obj = self.pool.get('purchase.order')
                po = po_obj.browse(cr, uid, res_id, context=context)
                # Add watermark to po report
                if add_watermark and po.state in ['confirmed', 'approved']:
                    self.add_watermark_to_attachments(cr, uid, values['attachment_ids'],context)
                order_line_ids = []
                for line in po.order_line:
                    if line.order_line_id:
                        order_line_ids.append(line.order_line_id)
                        if attach_pdf and line.order_line_id.drawing_file_name:
                            pdf_dxf_attachment_names.append(line.order_line_id.drawing_file_name)
                        if attach_dxf and line.order_line_id.dxf_file_name:
                            pdf_dxf_attachment_names.append(line.order_line_id.dxf_file_name)
                if attach_bom_xls:
                    bom_xls_attachment_id = self.get_bom_xls_attachment(cr, uid, po, context=context)
                    if bom_xls_attachment_id:
                        attachment_ids.append(bom_xls_attachment_id)
                pdf_dxf_attachment_ids = self.get_pdf_dxf_attachments(cr, uid, order_line_ids, attach_dxf, attach_pdf, context)
                attachment_ids += pdf_dxf_attachment_ids

        if attachment_ids:
            #Update the attachment file names
            #print(attachment_ids)
            for attachment in attachment_obj.browse(cr, uid, attachment_ids, context=context):
                if not attachment.datas_fname:
                    attachment_obj.write(cr, uid, [attachment.id],{'datas_fname': attachment.name},context=context)
            #if values.get('attachment_ids'):
            #    values['attachment_ids'].append(poem_pdf_attachment_ids)
            #else:
            if model == 'pur_req':
                values['attachment_ids'] = attachment_ids
            else:
                values['attachment_ids'] = values['attachment_ids'] and values['attachment_ids'].append(attachment_ids) or attachment_ids

        if model =='purchase.order' and pdf_dxf_attachment_names:
            values.update({'pdf_dxf_attachment_names':pdf_dxf_attachment_names})
        return values