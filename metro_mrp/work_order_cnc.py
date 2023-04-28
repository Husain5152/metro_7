# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp.tools.translate import _
from openerp import netsvc
import time
import datetime
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from pyPdf import PdfFileWriter, PdfFileReader
from openerp.addons.metro import utils
import zipfile
import random
import os
import re
from openerp import SUPERUSER_ID

def _get_file(self, cr, uid, ids, field_names, args, context=None):
    result = dict.fromkeys(ids, {})
    attachment_obj = self.pool.get('ir.attachment')
    for obj in self.browse(cr, uid, ids):
        for field_name in field_names:
            result[obj.id][field_name] = None
            file_ids = attachment_obj.search(
                cr, uid, [('name', '=', field_name),
                          ('res_id', '=', obj.id),
                          ('res_model', '=', self._name)],context=context)
            if file_ids:
                result[obj.id][field_name] = attachment_obj.browse(cr, uid, file_ids[0]).datas
    return result

def _set_file(self, cr, uid, id, field_name, value, args, context=None):
    # if uid != SUPERUSER_ID:
    #     create_uid = self.read(cr, uid, id, ['create_uid'])['create_uid'][0]
    #     if uid != create_uid:
    #         raise osv.except_osv(_('Invalid Action!'), _('Only the creator can change the upload file!'))
    attachment_obj = self.pool.get('ir.attachment')
    file_ids = attachment_obj.search(
        cr, uid, [('name', '=', field_name),
                  ('res_id', '=', id),
                  ('res_model', '=', self._name)])
    file_id = None
    if file_ids:
        file_id = file_ids[0]
        attachment_obj.write(cr, uid, file_id, {'datas': value})
    else:
        file_id = attachment_obj.create(
            cr, uid, {'name':  field_name,
                      'res_id': id,
                      'type': 'binary',
                      'res_model':self._name,
                      'datas': value})    
    return file_id
    
class work_order_cnc(osv.osv):
    _name = "work.order.cnc"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "CNC Work Order"

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        for arg in args:
            if arg[0] == 'name':
                if arg[2].isdigit():
                    idx = args.index(arg)
                    args.remove(arg)
                    args.insert(idx, ['id', '=', arg[2]])
                    break
        ids = super(work_order_cnc, self).search(cr, user, args, offset, limit, order, context, count)

        return ids

    def _get_done_info(self, cr, uid, ids, fields, args, context=None):
        result = {}
        for id in ids:
            result[id] = {'can_change_ids':True}
        for order in self.browse(cr,uid,ids,context=context):
            if order.state != 'draft' :
                can_change_ids = False
            else:
                can_change_ids = True
                for line in order.wo_cnc_lines:
                    if line.state == 'done':
                        can_change_ids = False
                        break
            result[order.id].update({'can_change_ids':can_change_ids})
        return result    
    _columns = {
        'name': fields.char('Name', size=64, required=True,readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'note': fields.text('Description', required=False),
        'sale_product_ids': fields.many2many('sale.product','cnc_id_rel','cnc_id','id_id',
                                             string="MFG IDs",readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'wo_cnc_lines': fields.one2many('work.order.cnc.line','order_id','CNC Work Order Lines',readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'state': fields.selection([('draft','Draft'),
                                   ('prepare', 'Prepare CNC'),
                                   ('ready','Ready'),
                                   ('confirmed','Confirmed'),
                                   ('approved','Approved'),
                                   ('rejected','Rejected'),
                                   ('in_progress','In Progress'),
                                   ('done','Done'),
                                   ('cancel','Cancelled')],
            'Status', track_visibility='onchange', required=True),
        'reject_message': fields.text('Rejection Message', track_visibility='onchange'),
        'create_uid': fields.many2one('res.users','Creator',readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True),   
        'company_id': fields.many2one('res.company', 'Company', readonly=True),     
        'product_id': fields.related('wo_cnc_lines','product_id', type='many2one', relation='product.product', string='Product'),
        'can_change_ids' : fields.function(_get_done_info, type='boolean', string='Can Change IDs', multi="done_info"),
        'mfg_task_id': fields.many2one('project.task', string='Manufacture Task',domain=[('project_type','=','mfg'),('state','not in',('cancelled','done'))],readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'date_finished': fields.datetime('Finished Date', readonly=True),
        'partlist_file_name': fields.char('Part List'),
        'partlist_file': fields.function(_get_file, fnct_inv=_set_file, string="Part List File", type="binary", multi="_get_file",readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
    }
    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'work.order.cnc', context=c),
        'state': 'draft',
        'can_change_ids': True,
    }
    _order = 'id desc'
    
    def _set_state(self,cr,uid,ids,state,context=None):
        self.write(cr,uid,ids,{'state':state},context=context)
        line_ids = []
        for wo in self.browse(cr,uid,ids,context=context):
            for line in wo.wo_cnc_lines:
                if not line.state == 'done':
                    line_ids.append(line.id)
        self.pool.get('work.order.cnc.line').write(cr,uid,line_ids,{'state':state})

    def _check_done_lines(self,cr,uid,ids,context=None):
        for wo in self.browse(cr,uid,ids,context=context):
            for line in wo.wo_cnc_lines:
                if line.state == 'done':
                    raise osv.except_osv(_('Invalid Action!'), _('Action was blocked, there are done work order lines!'))
        return True
    def _email_notify(self, cr, uid, ids, action_name, group_params, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            for group_param in group_params:
                email_group_id = self.pool.get('ir.config_parameter').get_param(cr, uid, group_param, context=context)
                if email_group_id:
                    # HoangTK - Add username to email subject
                    user = self.pool.get("res.users").browse(cr, uid, uid, context=context)
                    email_subject = 'CNC reminder: %s %s by %s'%(order.name, action_name, user.name)
                    mfg_id_names = ','.join([mfg_id.name for mfg_id in order.sale_product_ids])
                    email_body = '%s %s, MFG IDs:%s'%(order.name,action_name,mfg_id_names)
                    # email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'],context=context)['email']
                    email_from = user.email
                    utils.email_send_group(cr, uid, email_from, None,email_subject,email_body, email_group_id, context=context)
        
    def action_ready(self, cr, uid, ids, context=None):
        #set the ready state
        self._set_state(cr, uid, ids, 'ready',context)
        #send email to the user group that can confirm
        self._email_notify(cr, uid, ids, 'need your confirmation', ['mrp_cnc_wo_group_confirm'],context)     
        return True

    def action_prepare(self, cr, uid, ids, context=None):
        #set the ready state
        self._set_state(cr, uid, ids, 'prepare',context)
        #send email to the user group that can confirm
        #self._email_notify(cr, uid, ids, 'need your confirmation', ['mrp_cnc_wo_group_confirm'],context)
        return True

    def action_confirm(self, cr, uid, ids, context=None):
        #CNC MFG task required parameter
        cnc_task_required = self.pool.get('ir.config_parameter').get_param(cr, uid, 'mrp.cnc.task.reuqired', '0', context=context)
        cnc_task_required = cnc_task_required == '1' and True or False
        for cnc_wo in self.browse(cr, uid, ids, context=context):
            #must have cnc lines
            if not cnc_wo.wo_cnc_lines:
                raise osv.except_osv(_('Error!'), _('Please add work order lines for CNC work order [%s]%s')%(cnc_wo.id, cnc_wo.name))
            #task required  checking
            if cnc_task_required and not cnc_wo.mfg_task_id:
                    raise osv.except_osv(_('Error!'), _('Manufacture task is required for CNC work order [%s]%s')%(cnc_wo.id, cnc_wo.name))
            #Task and MFG ID matching
            if cnc_wo.mfg_task_id and not self.task_id_check(cr, uid, cnc_wo.mfg_task_id.id, [mfg_id.id for mfg_id in cnc_wo.sale_product_ids], context):
                raise osv.except_osv(_('Invalid Action!'), _('The manufacture task must match the MFG IDs you selected!'))
            # for cnc_line in cnc_wo.wo_cnc_lines:
            #    if not cnc_line.cnc_file_name or not cnc_line.drawing_file_name:
            #        raise osv.except_osv(_('Invalid Action!'), _('The cnc line must have both "CNC File" and "Drawing PDF" files uploaded!'))
        #set state to done
        self._set_state(cr, uid, ids, 'confirmed',context)
        #send email to the user group that can approve
        self._email_notify(cr, uid, ids, 'need your approval', ['mrp_cnc_wo_group_approve'],context)           
        return True

        return True
        
    #TODO, for the feature connecting with the MRP
    '''                   
    def action_confirm(self, cr, uid, ids, context=None):
        #check the related parts
        line_obj = self.pool.get("work.order.cnc.line")
        for cnc in self.browse(cr, uid, ids, context=context):
            if not cnc.wo_cnc_lines:
                raise osv.except_osv(_('Error!'), _("Missing CNC work order lines!"))
            #check lines
            for line in cnc.wo_cnc_lines:
                if not line_obj.check_cnc_line(cr, uid, line, context=context):
                    return False
            #check line's material consuming moves
            consume_move_lines = line_obj.get_consume_move_lines(cr, uid, [line.id for line in cnc.wo_cnc_lines], 
                                                                 mfg_ids = [mfg_id.id for mfg_id in cnc.sale_product_ids], context=context)
            for line_id, move_ids in consume_move_lines.items():
                if not move_ids:
                    ln_file_name = line_obj.read(cr, uid, line_id, ['file_name'],context=context)['file_name']
                    raise osv.except_osv(_('Error!'), _("Finding manufacture consuming move failed,  file name is '%s'"%(ln_file_name,)))
                    
        self._set_state(cr, uid, ids, 'confirmed',context)
        return True
    '''

    def action_force_cancel(self, cr, uid, ids, context=None):
        # TODO: Force cancel even have lines done
        # First cancel all material request
        mr_obj = self.pool.get('material.request')
        done_mr_ids = []
        done_line_ids = []
        other_mr_ids = []
        for order in self.browse(cr, uid, ids, context=context):
            for line in order.wo_cnc_lines:
                if line.mr_id:
                    if line.state == 'done':
                        done_mr_ids.append(line.mr_id.id)
                        done_line_ids.append(line.id)
                    else:
                        other_mr_ids.append(line.mr_id.id)
        if done_mr_ids:
            mr_obj.action_revert_done(cr, uid, done_mr_ids, context=context)
        mr_obj.action_cancel(cr, uid, done_mr_ids + other_mr_ids, context=context)
        if done_line_ids:
            self.pool.get('work.order.cnc.line').write(cr, uid, done_line_ids, {'state': 'cancel'})
        self._set_state(cr, uid, ids, 'cancel', context)
        # Second cancel the CNC
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        self._check_done_lines(cr,uid,ids,context)
        #set the cancel state
        self._set_state(cr, uid, ids, 'cancel',context)
        return True
    
    def action_draft(self, cr, uid, ids, context=None):
        #set the cancel state
        self._set_state(cr, uid, ids, 'draft',context)
        return True

    def action_approve(self, cr, uid, ids, context=None):
        #set the cancel state
        self._set_state(cr, uid, ids, 'approved',context)
        #send email to the user group that can CNC done
        self._email_notify(cr, uid, ids, 'was approved', ['mrp_cnc_wo_group_cnc_mgr'],context) 
        return True

    def action_done(self, cr, uid, ids, context=None):
        #set the cancel state
        self._set_state(cr, uid, ids, 'done',context)
        date_finished = context.get('date_finished') and context.get('date_finished') or datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        self.write(cr, uid, ids, {'date_finished':date_finished}, context=context)
        #send email to the CNC Manager group to notify the CNC working is done
        self._email_notify(cr, uid, ids, 'is finished', ['mrp_cnc_wo_group_confirm','mrp_cnc_wo_group_approve','mrp_cnc_wo_group_cnc_mgr'],context)
        return True

    def action_in_progress(self, cr, uid, ids, context=None):
        ids = self.search(cr, uid, [('id', 'in', ids),('state','=','approved')],context=context)
        self.write(cr,uid,ids,{'state':'in_progress'},context=context)
        return True    
    
    def action_reject_callback(self, cr, uid, ids, message, context=None):
        #set the draft state
        self._set_state(cr, uid, ids, 'rejected',context)
        self.write(cr,uid,ids,{'reject_message':message})
        #send email to the user for the rejection message
        email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'],context=context)['email']
        for order in self.browse(cr, uid, ids, context=context):
            if order.create_uid.email:
                email_content = 'CNC reminder: %s was rejected'%(order.name)
                utils.email_send_group(cr, uid, email_from, order.create_uid.email,email_content,email_content, context = context) 
        return True
                    
    def action_reject(self, cr, uid, ids, context=None):     
        ctx = dict(context)
        ctx.update({'confirm_title':'Confirm rejection message',
                    'src_model':'work.order.cnc',
                    "model_callback":'action_reject_callback',})
        return self.pool.get('confirm.message').open(cr, uid, ids, ctx)
                
    def unlink(self, cr, uid, ids, context=None):
        orders = self.read(cr, uid, ids, ['state'], context=context)
        for s in orders:
            if s['state'] not in ['draft','cancel']:
                raise osv.except_osv(_('Invalid Action!'), _('Only the orders in draft or cancel state can be delete.'))
        self._check_done_lines(cr,uid,ids,context)
        self._email_notify(cr, uid, ids, 'was deleted', ['mrp_cnc_wo_group_cnc_mgr'], context)
        return super(work_order_cnc, self).unlink(cr, uid, ids, context=context)

    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        order = self.browse(cr, uid, id, context=context)
        if order.partlist_file:
            default.update({
                'partlist_file': order.partlist_file,
                'partlist_file_name': order.partlist_file_name,
            })
        else:
            default.update({
                'partlist_file_name': False,
            })
        return super(work_order_cnc, self).copy_data(cr, uid, id, default, context)

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        old_data = self.read(cr,uid,id,['name'],context=context)
        default.update({
            'name': '%s (copy)'%old_data['name'],
            'mfg_task_id': None,
            'sale_product_ids': None,
            'reject_message':None,
            'date_finished':None,
        })
        return super(work_order_cnc, self).copy(cr, uid, id, default, context)    
    def task_id_check(self, cr, uid, task_id, mfg_ids, context=None):
        task_mfg_ids = self.pool.get('project.task').read(cr,uid,task_id,['mfg_ids'])['mfg_ids']
        if not task_mfg_ids or not mfg_ids:
            return False
        #every task's MFG ID must in the CNC WO's MFG ID list
        for task_mfg_id in task_mfg_ids:
            if task_mfg_id not in mfg_ids:
                return False
        #every CNC WO's MFG ID must in the task's MFG ID list
        for mfg_id in mfg_ids:
            if mfg_id not in task_mfg_ids:
                return False
        return True
    def write(self, cr, uid, ids, vals, context=None):
        if not context:
            context = {}
        if vals.get('mfg_task_id',False):
            #manufacture tasks must belongs to the CNC work order's MFG IDs's tasks
            sale_product_ids = []
            if 'sale_product_ids' in vals:
                sale_product_ids = vals['sale_product_ids'][0][2]
                if not self.task_id_check(cr, uid, vals['mfg_task_id'], sale_product_ids, context):
                    raise osv.except_osv(_('Invalid Action!'), _('The manufacture task must match the MFG IDs you selected!'))
            else:
                for wo in self.read(cr, uid, ids, context=context):
                    if not self.task_id_check(cr, uid, vals['mfg_task_id'], wo['sale_product_ids'], context):
                        raise osv.except_osv(_('Invalid Action!'), _('The manufacture task must match the MFG IDs you selected!'))
            
        return super(work_order_cnc, self).write(cr, uid, ids, vals, context=context)  
    def create(self, cr, uid, vals, context=None):
        #manufacture tasks must belongs to the CNC work order's MFG IDs's tasks
        if vals.get('mfg_task_id',False) and not self.task_id_check(cr, uid, vals['mfg_task_id'], vals['sale_product_ids'][2], context):
                raise osv.except_osv(_('Invalid Action!'), _('The manufacture task must match the MFG IDs you selected!'))
        return super(work_order_cnc, self).create(cr, uid, vals, context=context)
    
    # def _format_file_name(self, file_name):
    #     #+++ HoangTK - 01/15/2016 : Add ", ' to special chars
    #     file_reserved_char = ('/','\\','<','>','*','?','"',"'")
    #     #+++ HoangTK - 01/15/2016 : Add ", ' to special chars
    #     new_file_name = file_name
    #     for char in file_reserved_char:
    #         new_file_name = new_file_name.replace(char, '-')
    #     return new_file_name
    
    def print_pdf(self, cr, uid, ids, context):
        assert len(ids) == 1, 'This option should only be used for a single CNC work order at a time'
        attachment_obj = self.pool.get('ir.attachment')
        output = PdfFileWriter() 
        page_cnt = 0
        order = self.browse(cr, uid, ids[0], context=context)
        for line in order.wo_cnc_lines:
            if line.drawing_file_name and line.drawing_file_name.lower().endswith('.pdf'):                    
                file_ids = attachment_obj.search(
                    cr, uid, [('name', '=', 'drawing_file'),
                              ('res_id', '=', line.id),
                              ('res_model', '=', 'work.order.cnc.line')])
                if file_ids:
                    attach_file = attachment_obj.file_get(cr, uid, file_ids[0],context=context)
                    input = PdfFileReader(attach_file, strict=False)
                    for page in input.pages: 
                        output.addPage(page)
                        page_cnt += 1
        if page_cnt > 0:
            full_path_temp = attachment_obj.full_path(cr, uid, 'temp')
            #+++ HoangTK - 01/15/2016 : Remove special character from file name
            #file_name = utils._format_file_name(order.name)
            file_name = utils._format_file_name(order.name)
            #--- HoangTK - 01/15/2016 : Remove special character from file name
            full_file_name =  '%s/%s.pdf'%(full_path_temp, file_name,)
            outputStream = file(full_file_name, "wb") 
            output.write(outputStream) 
            outputStream.close()
            filedata = open(full_file_name,'rb').read().encode('base64')
            os.remove(full_file_name)
            return self.pool.get('file.down').download_data(cr, uid, "%s.pdf"%(file_name,), filedata, context)
    
        return False                
    def zip_cnc_file(self, cr, uid, ids, context):
        assert len(ids) == 1, 'This option should only be used for a single CNC work order at a time'
        attachment_obj = self.pool.get('ir.attachment')      
        try:
            #prepare temp file path for the download files
            full_path_temp = attachment_obj.full_path(cr, uid, 'temp')
            full_path = '%s/%s/'%(full_path_temp, random.randint(1,12000))
            dirname = os.path.dirname(full_path)
            if not os.path.isdir(dirname):
                os.makedirs(dirname)
            
            file_cnt = 0
            order = self.browse(cr, uid, ids[0], context=context)
            #zip file name
            zip_name = utils._format_file_name(order.name)
            zip_file_name =  '%s/%s.zip'%(full_path_temp, zip_name,)
            zip_cnc = zipfile.ZipFile(zip_file_name, 'w' ,zipfile.ZIP_DEFLATED) 
            for line in order.wo_cnc_lines:
                if line.cnc_file_name:                    
                    file_ids = attachment_obj.search(
                        cr, uid, [('name', '=', 'cnc_file'),
                                  ('res_id', '=', line.id),
                                  ('res_model', '=', 'work.order.cnc.line')])
                    if file_ids:
                        attach_file = attachment_obj.file_get(cr, uid, file_ids[0],context=context)
#                        full_path_file = attachment_obj.full_path(cr, uid, '%s/%s'%(full_path,line.cnc_file_name))
                        #+++ HoangTK - 01/18/2016 : Fix can not download zip file
                        #full_path_file = '%s%s'%(full_path,line.cnc_file_name)
                        full_path_file = '%s%s'%(full_path,utils._format_file_name(line.cnc_file_name))
                        #--- HoangTK - 01/18/2016 : Fix can not download zip file
                        open(full_path_file, "wb").write(attach_file.read())
                        zip_cnc.write(full_path_file,line.cnc_file_name)
                        file_cnt += 1
            zip_cnc.close()
            if file_cnt > 0:
                #remove all the files zipped
                for file in os.listdir(full_path): 
                    targetFile = os.path.join(full_path,  file) 
                    if os.path.isfile(targetFile): 
                        os.remove(targetFile)
                os.removedirs(full_path)
                #get the zip file data and remove it
                filedata = open(zip_file_name,'rb').read().encode('base64')
                os.remove(zip_file_name)
                #goto file download page
                return self.pool.get('file.down').download_data(cr, uid, "%s.zip"%(zip_name), filedata, context)
        except IOError, e:
            raise osv.except_osv(_('Error'), "zip_txt writing %s, %s"%(full_path,e))
        
        return False                     
class work_order_cnc_line(osv.osv):
    _name = "work.order.cnc.line"
    _description = "CNC Work Order Lines"
    
    _columns = {
        'order_id': fields.many2one('work.order.cnc','Ref'),
        'create_uid': fields.many2one('res.users','Creator',readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True),   
        'file_name': fields.char('File Name', size=16, required=True),
        'plate_length': fields.integer('Length(mm)', required=True),
        'plate_width': fields.integer('Width(mm)', required=True),
        'plate_height': fields.integer('Height(mm)', required=True),
        'percent_usage_theory': fields.float('Usage Percent in Theory(%)', required=True),
        'percent_usage': fields.float('Usage Percent of Manufacture(%)', required=True),
        'number_of_incision_point': fields.integer('Number of incision Points'),
        'total_cutting_length': fields.float('Total cutting length'),
        'date_finished': fields.datetime('Finished Date', readonly=True),
        'product_id': fields.many2one('product.product','Product', readonly=True),
        'state': fields.selection([('draft','Draft'),('prepare', 'Prepare CNC'),('ready','Ready'),('confirmed','Confirmed'),('approved','Approved'),('rejected','Rejected'),('done','Done'),('cancel','Cancelled')], 'Status', required=True, readonly=True),
        'company_id': fields.related('order_id','company_id',type='many2one',relation='res.company',string='Company'),
        'mr_id': fields.many2one('material.request','MR#', readonly=True),
        'is_whole_plate': fields.boolean('Whole Plate', readonly=True),
        'cnc_file_name': fields.char('CNC File'),
        'drawing_file_name': fields.char('Drawing PDF'),
        'doc_file_name': fields.char('Doc'),
        'cnc_file': fields.function(_get_file, fnct_inv=_set_file, string="CNC Txt", type="binary", multi="_get_file",),
        'drawing_file': fields.function(_get_file, fnct_inv=_set_file, string="Drawing PDF", type="binary", multi="_get_file",),
        'doc_file': fields.function(_get_file, fnct_inv=_set_file, string="Doc", type="binary", multi="_get_file",),
        'cnc_create_date': fields.date('CNC File Create '),
        'drawing_create_date': fields.date('Drawing PDF Create '),
        #connection with the mrp order's components
        'wo_comp_ids': fields.many2many('mrp.wo.comp', string="Part List", readonly=False),
    }

    _defaults = {
        'state': 'draft',
    }
    def _check_size(self,cr,uid,ids,context=None):
        for record in self.browse(cr, uid, ids, context=context):
            if record.state == 'draft' and (record.plate_length <= 0 or record.plate_width <= 0 or record.plate_height <= 0 or record.percent_usage <= 0 or record.percent_usage_theory <= 0):
                raise osv.except_osv(_('Error'), _('The "Length/Width/Height/Usage Percent in Theory/Usage Percent of Manufacture" must be larger than zero\n %s.')% (record.file_name,))
        return True
    def _check_file_name(self,cr,uid,ids,context=None):
        for record in self.browse(cr, uid, ids, context=context):
            same_file_name_ids = self.search(cr, uid, [('order_id','=',record.order_id.id),('id','!=',record.id),('file_name','=',record.file_name)],context=context)
            if same_file_name_ids:
                raise osv.except_osv(_('Error'), _('File name "%s" is duplicated under same cnc order!')% (record.file_name,))
        return True
    _constraints = [
        (_check_size,
            'You must assign a serial number for this product.',
            ['plate_length','plate_width','plate_height','percent_usage','percent_usage_theory']),
        (_check_file_name,
            'File name is duplicated under same cnc order!',
            ['file_name'])
                    ]    
    #TODO, for the feature connecting with the MR
    '''
    def check_cnc_line(self, cr, uid, cnc_line, product_id = None, context=None):
        #must define the line's part list
        if not cnc_line.wo_comp_ids:
            raise osv.except_osv(_('Error!'), _("Line - %s must add the part list!"%(cnc_line.file_name,)))
        #All part list of a line must have same product to consume
        comp_material_prod_id = None
        for comp in cnc_line.wo_comp_ids:
            #The component must have bom lines to include the raw materials
            if not comp.comp_id.bom_lines:
                raise osv.except_osv(_('Error!'), _("Line - %s, Component - %s, must be a BOM component with bom lines!"%(cnc_line.file_name,comp.comp_id.name)))
            for bom_prod in comp.comp_id.bom_lines:
                #only check the component with raw material
                if bom_prod.bom_lines:
                    continue
                if not comp_material_prod_id:
                    comp_material_prod_id = bom_prod.product_id.id
                elif comp_material_prod_id != bom_prod.product_id.id:
                    raise osv.except_osv(_('Error!'), _("Line - %s, all components should consume same material!"%(cnc_line.file_name,)))
        if not comp_material_prod_id:
            raise osv.except_osv(_('Error!'), _("Line - %s, all components must contains raw material in bom lines!"%(cnc_line.file_name,)))
        #check product_id parameter, it should be same as the component's product
        if product_id and comp_material_prod_id != product_id:
            prod_names = self.pool.get('product.product').name_get(cr, uid, [product_id,comp_material_prod_id], context=context)
            names = {}
            for name in prod_names:
                names.update({name[0]:name[1]})
            raise osv.except_osv(_('Error!'), _("Product - '%s' is not same as component's product '%s', please correct it"%(names[product_id], names[comp_material_prod_id])))
            
        return True
    '''
    #TODO, for the feature connecting with the MR
#    def get_consume_move_lines(self, cr, uid, cnc_line_ids, mfg_ids=None, context=None):
#        #get the MO's consuming move lines by cnc line's part list       
#        sql = '''
#        select distinct a.id, d.consume_move_id
#        from work_order_cnc_line a
#        join mrp_wo_comp_work_order_cnc_line_rel b
#            on a.id = b.work_order_cnc_line_id
#        join mrp_wo_comp c
#            on c.id = b.mrp_wo_comp_id
#        join mrp_production_product_line d
#            on c.comp_id = d.parent_bom_id and c.mo_id = d.production_id
#        '''
#        where = 'where a.id = ANY(%s)'
#        args = (cnc_line_ids,)
#        if not mfg_ids:
#            sql += '\n join stock_move e on d.consume_move_id = e.id and e.sale_product_id = ANY(%s)'
#            args = (cnc_line_ids,cnc_line_ids)
#        
#        sql += '\n' + where        
#        cr.execute(sql, args)
#        res=dict.fromkeys(cnc_line_ids,[])
#        for data in cr.fetchall():
#            res[data[0]].append(data[1])
#        return res     
               
    def action_done(self, cr, uid, ids, context=None):
        #TODO, for the feature connecting with the MR
        '''
        cnc_obj = self.pool.get('cnc.workorder')
        #loop to check the line's data
        for line in self.browse(cr, uid, ids, context=context):
            if not cnc_obj.check_cnc_line(cr, uid, line, product_id = context.get('product_id'), context=context):
                return False
        '''
        #set the done data
        vals = {'state':'done','product_id':context.get('product_id'),'date_finished':context.get('date_finished'),'is_whole_plate':context.get('is_whole_plate')}
        if not context:
            context = {}
        context.update({'force_write':True})
        self.write(cr, uid, ids, vals ,context=context)
        #auto set the CNC order done once all lines are done
        order_ids = {}
        order_ids_done = []
        order_ids_in_progress = []
        for line in self.read(cr,uid,ids,['order_id'],context=context):
            order_id = line['order_id'][0]
            if not order_ids.has_key(order_id):
                order_ids.update({order_id:order_id})
        order_ids = order_ids.keys()
        for order in self.pool.get('work.order.cnc').browse(cr,uid,order_ids,context=context):
            order_done = True
            for line in order.wo_cnc_lines:
                if not line.state == 'done':
                    order_done = False
                    break
            if order_done:
                order_ids_done.append(order.id)
            else:
                order_ids_in_progress.append(order.id)
        #generate material requisition
        self.make_material_requisition(cr, uid, ids, context)
        #decrease the quantity of whole plate
        if context.get("is_whole_plate"):
            self.pool.get('plate.material').update_plate_whole_qty(cr, uid, context.get('product_id'), -1, context=context)
        #set order status
        self.pool.get('work.order.cnc').action_done(cr,uid,order_ids_done,context=context)
        self.pool.get('work.order.cnc').action_in_progress(cr,uid,order_ids_in_progress,context=context)
        return True
    
    #get the material request price
    def _get_mr_prod_price(self, cr, uid, product, context = None):
        result = {}
        #update the price_unit the and price_currency_id
        #default is the product's cost price
        price_unit = product.standard_price
        price_currency_id = None
        #get the final purchase price
        move_obj = self.pool.get('stock.move')
        #get the final purchase price
        move_ids = move_obj.search(cr,uid,[('product_id','=',product.id),('state','=','done'),('type','=','in')],limit=1,order='create_date desc')
        if move_ids:
            move_price = move_obj.read(cr,uid,move_ids[0],['price_unit','price_currency_id'],context=context)
            price_unit = move_price['price_unit']
            price_currency_id = move_price['price_currency_id']
        result['price_unit'] = price_unit
        result['price_currency_id'] = price_currency_id
        return result
    #generate the material requisition  
    def make_material_requisition(self, cr, uid, wo_cnc_lines, context = None):
        mr_obj = self.pool.get("material.request")
        mr_line_obj = self.pool.get("material.request.line")
        #create material requisition
        mr_name = self.pool.get('ir.sequence').get(cr, uid, 'material.request') or '/'
        mr_name += ' from CNC'
        mr_vals = {'type':'mr','mr_dept_id':context.get('mr_dept_id'),'name':mr_name,'date':fields.datetime.now()}
        mr_id = mr_obj.create(cr, uid, mr_vals, context=context)
        #create material requisition lines
        mr_line_vals = []
        mr_line_ids = []
        cnc_lines = self.pool.get('work.order.cnc.line').browse(cr, uid, wo_cnc_lines, context=context)
        #get the employee id
        mr_emp_id = None
        user = self.pool.get('res.users').browse(cr,uid,uid,context=context)
        if user.employee_ids:
            mr_emp_id = user.employee_ids[0].id
        
        loc_from_id, loc_to_id = mr_line_obj.default_mr_loc(cr, uid, context=context)
        for ln in cnc_lines:
            ln_volume = (ln.plate_length * ln.plate_width * ln.plate_height * ln.percent_usage/100)
            #the name will be like 'Manganese Plate(T20*2200*11750mm)'
            prod_name = ln.product_id.name
            # HoangTK - 09/26/2016 Search volumne like 120*10*100
            # dimensions = re.findall(r'(\d+)\s*\*\s*(\d+)\s*\*\s*(\d+)', prod_name)
            dimensions = re.findall(r'(\d+)\s*[x\*]\s*(\d+)\s*[x\*]\s*(\d+)', prod_name)
            prod_volume = 1
            if len(dimensions) > 0:
                if len(dimensions[0]) == 3:
                    prod_volume = int(dimensions[0][0]) * int(dimensions[0][1]) * int(dimensions[0][2])
                else:
                    raise osv.except_osv(_('Calculate Volume Error!'), _(
                        'The product name do not satisfy the format, can not get the plate volume!\n%s') % (prod_name,))

            #start_idx = -1
            #end_idx = -1
            #try:
            #    start_idx = prod_name.index('(T')
            #    end_idx = prod_name.index('mm)')
            #except Exception, e:

            #    raise osv.except_osv(_('Calculate Volume Error!'), _('The product name do not satisfy the format, can not get the plate volume!\n%s')%(prod_name,))
            #prod_volume = eval(prod_name[start_idx+2:end_idx])

            ln_quantity = ln_volume/prod_volume
            #check the available inventory
            qty_avail = self.pool.get('stock.location')._product_reserve(cr, uid, [loc_from_id], ln.product_id.id, ln_quantity, {'uom': ln.product_id.uom_id.id}, lock=True)
            if not qty_avail:
                raise osv.except_osv(_('Error!'), _('%s inventory is not enough (location: %s, required quantity:%s, dimension: %s-%s-%s), please check onhand quantity and ready to delivery stock move for it.')%(ln.product_id.name, loc_from_id, ln_quantity, int(dimensions[0][0]), int(dimensions[0][1]), int(dimensions[0][2])))

            price = self._get_mr_prod_price(cr, uid, ln.product_id)
            #loop ids to generate mr line
            if ln.order_id.sale_product_ids:
                id_cnt = len(ln.order_id.sale_product_ids)
                for sale_id in ln.order_id.sale_product_ids:
                    mr_line_vals = {'picking_id':mr_id,
                                    'name':'CNC_' + ln.file_name,
                                    'product_id':ln.product_id.id,
                                        'product_qty':ln_quantity/id_cnt,
                                        'product_uom':ln.product_id.uom_id.id,
                                        'price_unit':price['price_unit'],
                                        'price_currency_id':price['price_currency_id'],
                                        'mr_emp_id':mr_emp_id,
                                        'mr_sale_prod_id':sale_id.id,
                                        'mr_notes':'CNC Work Order Finished',}
                    mr_line_id = mr_line_obj.create(cr,uid,mr_line_vals,context=context)
                    mr_line_ids.append(mr_line_id)
            else:
                    mr_line_vals = {'picking_id':mr_id,
                                    'name':'CNC_' + ln.file_name,
                                    'product_id':ln.product_id.id,
                                        'product_qty':ln_quantity,
                                        'product_uom':ln.product_id.uom_id.id,
                                        'price_unit':price['price_unit'],
                                        'price_currency_id':price['price_currency_id'],
                                        'mr_emp_id':mr_emp_id,
                                        'mr_notes':'CNC Work Order Finished',}
                    mr_line_id = mr_line_obj.create(cr,uid,mr_line_vals,context=context)
                    mr_line_ids.append(mr_line_id)
                
            self.pool.get('work.order.cnc.line').write(cr,uid,ln.id,{'mr_id':mr_id},context=context)
        #confirm and assign if inventory is available
        mr_obj.draft_force_assign(cr, uid, [mr_id], {'context':context})
#        mr_line_obj.action_confirm(cr, uid, mr_line_ids)
#        mr_line_obj.force_assign(cr, uid, mr_line_ids)
#        wf_service = netsvc.LocalService("workflow")
#        wf_service.trg_validate(uid, 'stock.picking', mr_id, 'button_confirm', cr)
        
        #do auto receiving
        if mr_obj.read(cr,uid,mr_id,['state'],context=context)['state'] == 'assigned':
            partial_data = {
                'delivery_date' : time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            }
            for mr_line in mr_line_obj.browse(cr, uid, mr_line_ids, context=context):
                partial_data['move%s' % (mr_line.id)] = {
                    'product_id': mr_line.product_id.id,
                    'product_qty': mr_line.product_qty,
                    'product_uom': mr_line.product_uom.id,
                    'prodlot_id': mr_line.prodlot_id.id,
                }
            self.pool.get('stock.picking').do_partial(cr, uid, [mr_id], partial_data, context=context)
    #TODO, for the feature connecting with the MRP
    '''
    def make_material_requisition(self, cr, uid, cnc_line_ids, context = None):
        mr_obj = self.pool.get("material.request")
        mr_line_obj = self.pool.get("material.request.line")
        #create material requisition
        mr_name = self.pool.get('ir.sequence').get(cr, uid, 'material.request') or '/'
        mr_name += ' from CNC'
        mr_vals = {'type':'mr','mr_dept_id':context.get('mr_dept_id'),'name':mr_name,'date':fields.datetime.now()}
        mr_id = mr_obj.create(cr, uid, mr_vals, context=context)
        #get the employee id
        mr_emp_id = None
        user = self.pool.get('res.users').browse(cr,uid,uid,context=context)
        if user.employee_ids:
            mr_emp_id = user.employee_ids[0].id
        #get the MO's consuming move lines
        #check line's material consuming moves
        cnc_line_data = self.pool.get('work.order.cnc.line').browse(cr,uid,cnc_line_ids[0],context=context)
        mfg_ids = [mfg_id.id for mfg_id in cnc_line_data.order_id.sale_product_ids]
        consume_move_lines = self.get_consume_move_lines(cr, uid, cnc_line_ids,mfg_ids, context=context)
        for line_id, move_ids in consume_move_lines.items():
            if not move_ids:
                ln_file_name = self.read(cr, uid, line_id, ['file_name'],context=context)['file_name']
                raise osv.except_osv(_('Error!'), _("Finding manufacture consuming move failed,  file name is '%s'"%(ln_file_name,)))
        #update the consume moves
        mr_line_ids = []
        for line_id,move_ids in consume_move_lines.items():
            ln_file_name = self.read(cr, uid, line_id, ['file_name'])['file_name']
            mr_line_vals = {'picking_id':mr_id,
                            'name':'CNC_' + ln_file_name,
                            'mr_emp_id':mr_emp_id,
                            'mr_notes':'CNC Work Order Finished',}
            mr_line_obj.write(cr, uid, move_ids, mr_line_vals, context=context)
            mr_line_ids += move_ids
        #update cnc lines mr_id
        self.pool.get('work.order.cnc.line').write(cr,uid,cnc_line_ids,{'mr_id':mr_id},context=context)
        
        #do material auto confirm and assign
        mr_line_obj.action_confirm(cr, uid, mr_line_ids)
        mr_line_obj.force_assign(cr, uid, mr_line_ids)
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'stock.picking', mr_id, 'button_confirm', cr)
                
        #do auto deliver
        partial_data = {
            'delivery_date' : time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        }
        for mr_line in mr_line_obj.browse(cr, uid, mr_line_ids, context=context):
            partial_data['move%s' % (mr_line.id)] = {
                'product_id': mr_line.product_id.id,
                'product_qty': mr_line.product_qty,
                'product_uom': mr_line.product_uom.id,
                'prodlot_id': mr_line.prodlot_id.id,
            }
        self.pool.get('stock.picking').do_partial(cr, uid, [mr_id], partial_data, context=context)      
    '''
    def _check_changing(self, cr, uid, ids, context=None):
        lines = self.read(cr, uid, ids, ['state','file_name'], context=context)
        for s in lines:
            if s['state'] not in ['draft','rejected']:
                raise osv.except_osv(_('Invalid Action!'), _('Only the lines in draft or rejected state can be change.\n%s')%(s['file_name'],))
        
    def unlink(self, cr, uid, ids, context=None):
        self._check_changing(cr, uid, ids, context)
        return super(work_order_cnc_line, self).unlink(cr, uid, ids, context=context) 
        
    def write(self, cr, uid, ids, vals, context=None):
        if not context:
            context = {}        
        if not context.get('force_write') \
            and not(len(vals) == 1 and vals.has_key('order_id')) \
            and not(len(vals) == 1 and vals.has_key('state')):
            self._check_changing(cr, uid, ids, context)
        return super(work_order_cnc_line, self).write(cr, uid, ids, vals, context=context)  

    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        line_data = self.browse(cr,uid,id,context=context)
        default.update({
            'date_finished': None,
            'product_id': None,
            'mr_id': None,
            'is_whole_plate': None,
            'wo_comp_ids': None,
            'cnc_file':line_data.cnc_file,
            'drawing_file':line_data.drawing_file,
            'doc_file':line_data.doc_file
        })
                
        return super(work_order_cnc_line, self).copy_data(cr, uid, id, default, context)        
