# -*- encoding: utf-8 -*-
from osv import fields, osv
from openerp.tools.translate import _
from datetime import datetime
import subprocess
from shutil import copyfile, rmtree
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT,DEFAULT_SERVER_DATE_FORMAT
#from openerp.report.pyPdf import PdfFileWriter, PdfFileReader
from pyPdf import PdfFileWriter, PdfFileReader
#from utils import PdfReadError
from openerp.report import pdfrw
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from openerp.addons.metro import utils
import zipfile
import random
import os
import base64
from openerp import SUPERUSER_ID
import xlrd
import xlwt
from xlutils.copy import copy
from xlrd import XLRDError
import StringIO
from decimal import *
from math import ceil,floor
try:
    import json
except ImportError:
    import simplejson as json
import tempfile
import tools
from lxml import etree
import logging
_logger = logging.getLogger(__name__)

CHUNK_SIZE = 100

PART_TYPE_SELECTION = [('ASM', 'ASM'),
                       ('PMC', 'PMC'),
                       ('PMS', 'PMS'),
                       ('PML', 'PML'),
                       ('PS', 'PS'),
                       ('POEM', 'POEM'),
                       ('CD','CD')]
WORK_STEP_LIST = ['Wa','P', 'Fc', 'B', 'Ma', 'D', 'Mi', 'W', 'A', 'Ct', 'Bt', 'Ps', 'G', 'K','Ht']

class missing_erpno(osv.osv):
    _inherit = ['mail.thread']
    _name = "missing.erpno"
    _description = "Missing ERP No"
    _columns = {
        'creator': fields.many2one('res.users','Creator',readonly=True),
        'date': fields.date('Date',readonly=True),
        'name': fields.related('order_id','name',string='Name',type='char',size=128),
        'order_id': fields.many2one('drawing.order', string='Drawing Order', readonly=True),
        'lines': fields.one2many('missing.erpno.line','missing_id', string='Missing Lines', ondelete="cascade"),
    }

    def update_bom_file(self, cr, uid, ids, context=None):
        drawing_order_obj = self.pool.get('drawing.order')
        order_ids = []
        for missing_erpno in self.browse(cr, uid, ids):
            order_ids.append(missing_erpno.order_id.id)
        drawing_order_obj.update_missing_erpno(cr, uid, order_ids, context=context)
        return self.pool.get('warning').info(cr, uid, title='Information', message=_(
                "Bom file has been updated!"))

    _defaults = {
        'creator': lambda self,cr, uid, c: uid,
        'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
    }
missing_erpno()

class missing_erpno_line(osv.osv):
    _name = "missing.erpno.line"
    _description = "Missing ERP Lines"
    _columns = {
        'missing_id': fields.many2one('missing.erpno','Missing ERP No'),
        'product_id': fields.many2one('product.product', string='Product'),
        'erp_no': fields.related('product_id','default_code', string='ERP #',type='char',size=128,readonly=True),
        'item_no': fields.char('Item No', readonly=True),
        'name': fields.char('Part Number', size=128, readonly=True),
        'description': fields.char('Description', size=128, readonly=True),
    }

class drawing_order_history(osv.osv):
    _name = "drawing.order.history"
    _description = "Drawing Order History"
    _columns = {
        'date': fields.datetime('Modified Date', readonly=True),
        'drawing_order_id': fields.many2one('drawing.order', 'Drawing Order', readonly=True),
        'user_id': fields.many2one('res.users', 'User', readonly=True),
        'content': fields.char('Content', readonly=True),
        'vals': fields.char('Update Values', readonly=True, size=256),
    }
    _order = 'date desc'
drawing_order_history()


class drawing_order(osv.osv):
    _name = "drawing.order"
    _inherit = ['mail.thread']
    _description = "Drawing Order"
    _order = 'id desc'

    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        result = []
        for order in self.browse(cr, user, ids, context=context):
            order_id = getattr(order, 'id')
            order_name = getattr(order, 'name')
            result.append((order.id,'[%s] %s' % (order_id , order_name)))
        return result

    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if name:
            ids = []
            if name.isdigit():
                ids = self.search(cr, user, [('id', '=', name)] + args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, user, [('name', '=', name)] + args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, user, args + [('name', operator, name)], limit=limit, context=context)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
        result = self.name_get(cr, user, ids, context=context)
        return result

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        for arg in args:
            if arg[0] == 'name':
                if arg[2].isdigit():
                    idx = args.index(arg)
                    args.remove(arg)
                    args.insert(idx, ['id', '=', arg[2]])
                    break
        ids = super(drawing_order, self).search(cr, user, args, offset, limit, order, context, count)

        return ids

    def open_do_lines(self, cr, uid, ids, context=None):
        if not isinstance(ids, list):
            ids = [ids]
        return {
            'domain': "[('order_id', 'in', [" + ",".join(str(do_id) for do_id in ids) + "])]",
            'name': _('Drawing Order Files'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'drawing.order.line',
            'type': 'ir.actions.act_window',
            'context': context,
        }

    def get_big_subassembly_qty(self, cr, uid, order):
        result = 1
        bom_obj = self.pool.get('mrp.bom')
        mo_qty = order.mo_id.product_qty
        big_assembly_bom_ids = bom_obj.search(cr, uid, [
            ('bom_id', '=', order.mo_id.bom_id.id),
            ('product_id', '=', order.product_id.id),
        ])
        if len(big_assembly_bom_ids) > 0:
            big_assembly_boms = bom_obj.browse(cr, uid, big_assembly_bom_ids)
            if order.mo_id.bom_id.product_qty > 0:
                result = big_assembly_boms[0].product_qty / order.mo_id.bom_id.product_qty
        return result * mo_qty

    def _get_product_ids_from_mo(self, cr, uid, mo):
        product_ids = []
        if mo.bom_id:
            for bom_line in mo.bom_id.bom_lines:
                product_ids.append(bom_line.product_id.id)
        return product_ids

    def _get_product_ids(self, cr, uid, order):
        product_ids = []
        if order.mo_id :
            product_ids = self._get_product_ids_from_mo(cr, uid, order.mo_id)
        return product_ids

    def _get_mo_bigsubassembly(self, cr, uid, ids, name, args, context=None):
        result = {}
        for order in self.browse(cr, uid, ids):
            result[order.id] = self._get_product_ids(cr, uid, order)
        return result

    def _is_bom_error(self, cr, uid, ids, name, args, context=None):
        result = {}
        for order in self.browse(cr, uid, ids):
            result[order.id] = ''
            if order.bom_log:
                result[order.id] = _('Please check the Error Log!')
        return result

    def get_type_qty(self, cr, uid, ids, part_types):
        result = {}
        #for order in self.browse(cr, uid, ids):
        for order_id in ids:
            qty = 0
            cr.execute("SELECT quantity from drawing_order_line where order_id = %s and part_type in %s", (order_id, tuple(part_types)))
            records = cr.dictfetchall()
            for r in records:
            #for line in order.order_lines:
                #if line.part_type in part_types:
                    #qty += line.bom_qty * self.get_big_subassembly_qty(cr, uid, order)
                    #qty += line.quantity
                qty += r["quantity"]
            result[order_id] = qty
        return result

    def _get_produced_type_qty(self, cr, uid, ids, name=None, args=None, context=None):
        return self.get_type_qty(cr, uid, ids, ['ASM'])

    def _get_purchs_type_qty(self, cr, uid, ids, name=None, args=None, context=None):
        return self.get_type_qty(cr, uid, ids, ['PS'])

    def _get_purchoem_type_qty(self, cr, uid, ids, name=None, args=None, context=None):
        return self.get_type_qty(cr, uid, ids, ['POEM'])

    def _get_purchm_type_qty(self, cr, uid, ids, name=None, args=None, context=None):
        return self.get_type_qty(cr, uid, ids, ['PMC','PML','PMS'])

    def _get_purchmc_type_qty(self, cr, uid, ids, name=None, args=None, context=None):
        return self.get_type_qty(cr, uid, ids, ['PMC'])

    def _get_purchms_type_qty(self, cr, uid, ids, name=None, args=None, context=None):
        return self.get_type_qty(cr, uid, ids, ['PMS'])

    def _get_purchml_type_qty(self, cr, uid, ids, name=None, args=None, context=None):
        return self.get_type_qty(cr, uid, ids, ['PML'])

    def _get_purchcd_type_qty(self, cr, uid, ids, name=None, args=None, context=None):
        return self.get_type_qty(cr, uid, ids, ['CD'])

    def _get_order_ids_from_order_line(self, cr, uid, ids, context=None):
        result = []
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        for line in drawing_order_line_obj.browse(cr, uid, ids, context=context):
            if line.order_id.id not in result:
                result.append(line.order_id.id)
        return result

    def _build_query_columns(self, columns=[]):
        for step in WORK_STEP_LIST:
            columns.append('"%s_prepare_qty"' % step)
            columns.append('"%s_done_qty"' % step)
            columns.append('"%s_need_qty"' % step)
        return columns


    def _get_do_quantity(self, cr, uid, ids, name=None, args=None, context=None):
        res = dict((res_id, {}) for res_id in ids)
        columns = self._build_query_columns(['last_step'])
        for order_id in ids:
            prepare_qty = 0
            done_qty = 0
            need_qty = 0
            #for order_line in order.order_lines:
            cr.execute("SELECT %s from drawing_order_line where order_id = %s and last_step is not null" % (','.join(columns),order_id))
            result = cr.dictfetchall()
            for r in result:
                # prepare_qty += getattr(order_line, "%s_prepare_qty" % order_line.last_step, 0)
                # done_qty += getattr(order_line, "%s_done_qty" % order_line.last_step, 0)
                # need_qty += getattr(order_line, "%s_need_qty" % order_line.last_step, 0)
                #if order_line.last_step:
                #    prepare_qty += self.get_department_qty(order_line.last_step, 'prepare_qty', order_line)
                #    done_qty += self.get_department_qty(order_line.last_step, 'done_qty', order_line)
                #    need_qty += self.get_department_qty(order_line.last_step, 'need_qty', order_line)
                prepare_qty += r['%s_prepare_qty' % r['last_step']]
                done_qty += r['%s_done_qty' % r['last_step']]
                need_qty += r['%s_need_qty' % r['last_step']]
            #res[order.id].update({
            res[order_id].update({
                'prepare_qty': prepare_qty,
                'done_qty': done_qty,
                'need_qty': need_qty,
            })
        return res

    _columns = {
        'name': fields.char('Name', size=128, readonly=True,
                            states={'draft': [('readonly', False)],
                                    'bom_uploaded': [('readonly', False)],
                                    'pdf_uploaded': [('readonly', False)],
                                    'rejected': [('readonly', False)],
                                    }),
        'copy_order_id': fields.many2one('drawing.order','Copied From',readonly=True),
        'note': fields.text('Description', required=False),
        # +++ HoangTK - 11/17/2015: Change sale_product_ids to related field of mo_id
        # 'sale_product_ids': fields.many2many('sale.product','drawing_order_id_rel','drawing_order_id','id_id',
        #                                     string="MFG IDs",readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'sale_product_ids': fields.related('mo_id', 'mfg_ids', type="many2many", relation="sale.product",
                                           string="MFG IDs", readonly=True),
        # --- HoangTK - 11/17/2015
        'order_lines': fields.one2many('drawing.order.line', 'order_id', 'Drawing Order Lines', readonly=True,
                                       states={'draft': [('readonly', False)], 'rejected': [('readonly', False)],
                                               'bom_uploaded': [('readonly', False)],
                                               'pdf_uploaded': [('readonly', False)]
                                               }),
        'state': fields.selection(
            [('draft', 'Draft'),
             ('bom_uploaded','Bom Uploaded'),
             ('pdf_uploaded','Pdf Uploaded'),
             ('ready', 'Ready'), ('confirmed', 'Confirmed'), ('approved', 'Approved'),
             ('rejected', 'Rejected'), ('cancel', 'Cancelled')],
            'Status', track_visibility='onchange', required=True),
        'reject_message': fields.text('Rejection Message', track_visibility='onchange'),
        'create_uid': fields.many2one('res.users', 'Creator', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True),
        #        'date_finished': fields.datetime('Finished Date', readonly=True),
        'company_id': fields.many2one('res.company', 'Company', readonly=True),
        # +++ HoangTK 11/17/2015: Replace product_id below
        # 'product_id': fields.related('order_lines','product_id', type='many2one', relation='product.product', string='Product'),
        # --- HoangTK 11/17/2015
        'main_part_id': fields.many2one('product.product', 'Unit', readonly=True,
                                        states={'draft': [('readonly', False)], 'rejected': [('readonly', False)],
                                                'bom_uploaded': [('readonly', False)],
                                                'pdf_uploaded': [('readonly', False)]
                                                }),
        'bom_file_name': fields.char('BOM File Name', size=64),
        'bom_file': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file, string="BOM File",
                                    type="binary", multi="_get_file", filters='*.xls,*.xlsx'),
        # HoangTK - Drawing Download field is used to display link to download drawing
        # it will fix the overload on Openerp when it will keep read whole the binary if display drawing_file
        'bom_download': fields.char('BOM File',size=128,readonly=True),
        # +++ HoangTK - 11/16/2015: Attach drawing order to MO
        'mo_id': fields.many2one('mrp.production', 'Manufacturer Order'),
        'product_id': fields.many2one('product.product', 'Big Sub Assembly', required=True),
        #'prepare_qty': fields.integer('Prepare Qty', readonly=True),
        'prepare_qty': fields.function(_get_do_quantity, string='Prepare Qty', type='integer',
                                       multi="do_quantity",
                                       readonly=True,
                                           store={
                                               'drawing.order.line': (
                                                   _get_order_ids_from_order_line, ['quantity'],
                                                   40),
                                       }),
        #'done_qty': fields.integer('Done Qty', readonly=True),
        'done_qty': fields.function(_get_do_quantity, string='Done Qty', type='integer',
                                       readonly=True,
                                       multi="do_quantity",
                                       store={
                                           'drawing.order.line': (
                                               _get_order_ids_from_order_line, ['quantity'],
                                               40),
                                       }),
        #'need_qty': fields.integer('Need Qty', readonly=True),
        'need_qty': fields.function(_get_do_quantity, string='Need Qty', type='integer',
                                    readonly=True,
                                    multi="do_quantity",
                                    store={
                                        'drawing.order.line': (
                                            _get_order_ids_from_order_line, ['quantity'],
                                            40),
                                    }),
        #'history_ids': fields.one2many('drawing.order.history', 'drawing_order_id', 'History', readonly=True),
        'bom_log': fields.text('Error Log',readonly=True),
        'bom_error': fields.function(_is_bom_error,string='Bom error',type="char",size=100,method=True),
        'notice': fields.char('Notice',size=128,readonly=True),
        'mo_bigsubassembly_ids': fields.function(_get_mo_bigsubassembly,string='MO Big Subassembly',type="many2many",relation="product.product"),
        'confirm_date': fields.date(string='Confirm Date',readonly=True),
        'produced_type_qty': fields.function(_get_produced_type_qty, string="ASM Qty", type="integer",readonly=True,
                                             store={
                                                 'drawing.order.line': (
                                                     _get_order_ids_from_order_line, ['bom_qty'],
                                                     10),
                                             },
                                             help="ASM – Assemblies"),
        'purchs_type_qty': fields.function(_get_purchs_type_qty, string="PS Qty", type="integer",
                                             readonly=True,
                                           store={
                                               'drawing.order.line': (
                                                   _get_order_ids_from_order_line, ['bom_qty'],
                                                   10),
                                           },
                                           help="PS – Standard purchased parts"
                                           ),
        'purchoem_type_qty': fields.function(_get_purchoem_type_qty, string="POEM Qty", type="integer",
                                           readonly=True,
                                            store={
                                                'drawing.order.line': (
                                                _get_order_ids_from_order_line, ['bom_qty'],
                                                10),
                                            },
                                             help="POEM – Outsourced parts, which require drawings"
                                            ),
        'purchm_type_qty': fields.function(_get_purchm_type_qty, string="All Materials Qty", type="integer",
                                            readonly=True,
                                            store={
                                                'drawing.order.line': (
                                                _get_order_ids_from_order_line, ['bom_qty'],
                                                10),
                                            },
                                           help="All Materials (PMC, PMS & PML)"
                                           ),
        'purchmc_type_qty': fields.function(_get_purchmc_type_qty, string="PMC Qty", type="integer",
                                             readonly=True,
                                            store={
                                                'drawing.order.line': (
                                                    _get_order_ids_from_order_line, ['bom_qty'],
                                                    40),
                                            },
                                            help="PMC – Cylinder Materials"
                                            ),
        'purchms_type_qty': fields.function(_get_purchms_type_qty, string="PMS Qty", type="integer",
                                            readonly=True,
                                            store={
                                                'drawing.order.line': (
                                                _get_order_ids_from_order_line, ['bom_qty'],
                                                40),
                                            },
                                            help="PMS – Sheet Material"),
        'purchml_type_qty': fields.function(_get_purchml_type_qty, string="PML Qty", type="integer",
                                            readonly=True,
                                            store={
                                                'drawing.order.line': (
                                                _get_order_ids_from_order_line, ['bom_qty'],
                                                40),
                                            },
                                            help="PML – Long Material"
                                            ),
        'purchcd_type_qty': fields.function(_get_purchcd_type_qty, string="CD Qty", type="integer",
                                            readonly=True,
                                            store={
                                                'drawing.order.line': (
                                                    _get_order_ids_from_order_line, ['bom_qty'],
                                                    40),
                                            },
                                            help="CD – Composite Dept"
                                            ),
        'add_watermark_when_ready': fields.boolean('Add Watermark when ready?'),
        'req_ids': fields.one2many('pur.req','drawing_order_id', string='Generated PRs', readonly=True),
        'req_id': fields.many2one('pur.req','Generated PR',readonly=True),
        'req_id_pms': fields.many2one('pur.req','Generated PMS PR', readonly=True),
        'req_id_pml': fields.many2one('pur.req', 'Generated PMS PR', readonly=True),
        'req_o_id': fields.many2one('pur.req', 'Generated PR-O', readonly=True),
        'workorder_id': fields.many2one('mrp.production.workcenter.line','Work Order',readonly=True),
        'cnc_workorder_id': fields.many2one('work.order.cnc','CNC Work Order',readonly=True),
        'urgent': fields.boolean('Urgent'),
        # --- HoangTK - 11/16/2015
    }
    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid,
                                                                                                 'drawing.order',
                                                                                                 context=c),
        'state': 'draft',
        'bom_download': 'bom_file',
        'add_watermark_when_ready': True,
    }

    def _set_state(self, cr, uid, ids, state, context=None):
        self.write(cr, uid, ids, {'state': state}, context=context)
        line_ids = []
        for order in self.browse(cr, uid, ids, context=context):
            if state == 'draft' and order.bom_file_name:
                self.write(cr, uid, [order.id], {'state': 'bom_uploaded'}, context=context)
            for line in order.order_lines:
                if not line.state == 'done':
                    line_ids.append(line.id)
        self.pool.get('drawing.order.line').write(cr, uid, line_ids, {'state': state})

    def fix_task_pdf(self, cr, uid, ids, context=None):
        for order_id in ids:
            if order_id:
                drawing_order_line_obj = self.pool.get('drawing.order.line')
                task_obj = self.pool.get('project.task')
                task_line_obj = self.pool.get('project.task.line')
                task_ids = task_obj.search(cr, uid, [('drawing_order_id','=',order_id)], context=context)
                task_line_ids = task_line_obj.search(cr, uid, [('task_id','in', task_ids),
                                                               ('order_line_id','=',False)], context=context)
                for task_line in task_line_obj.browse(cr, uid, task_line_ids, context=context):
                    order_line_ids = drawing_order_line_obj.search(cr, uid, [('order_id','=',order_id),
                                                                             ('product_id','=',task_line.product_id.id),
                                                                             ('part_number','=',task_line.part_number)], context=context)
                    if order_line_ids:
                        task_line_obj.write(cr, uid, [task_line.id], {'order_line_id': order_line_ids[0]})
        return True



    @staticmethod
    def _check_done_lines(cr, uid, ids, context=None):
        #        for wo in self.browse(cr,uid,ids,context=context):
        #            for line in wo.wo_cnc_lines:
        #                if line.state == 'done':
        #                    raise osv.except_osv(_('Invalid Action!'), _('Action was blocked, there are done work order lines!'))
        return True

    def _email_notify(self, cr, uid, ids, action_name, group_params, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            for group_param in group_params:
                email_group_id = self.pool.get('ir.config_parameter').get_param(cr, uid, group_param, context=context)
                if email_group_id:
                    # HoangTK - Add username to email subject
                    user = self.pool.get("res.users").browse(cr, uid, uid, context=context)
                    email_subject = 'Drawing reminder: %s %s by %s' % (order.name, action_name, user.name)
                    mfg_id_names = ','.join([mfg_id.name for mfg_id in order.sale_product_ids])
                    # [(id1,name1),(id2,name2),...(idn,namen)]
                    main_part_name = ''
                    if order.main_part_id:
                        main_part_name = \
                        self.pool.get('product.product').name_get(cr, uid, [order.main_part_id.id], context=context)[0][
                            1]
                    email_body = '%s %s %s, MFG IDs:%s' % (order.name, main_part_name, action_name, mfg_id_names)
                    # email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'], context=context)['email']
                    email_from = user.email
                    utils.email_send_group(cr, uid, email_from, None, email_subject, email_body, email_group_id,
                                           context=context)

    def action_ready(self, cr, uid, ids, context=None):
        # +++ HoangTK - 12/14/2015 : Check if drawing order ready
        if not self._is_ready(cr, uid, ids, context=context):
            return False
        # +++ HoangTK - 12/14/2015 : Check if drawing order ready
        # set the ready state
        self._set_state(cr, uid, ids, 'ready', context)
        self.write(cr, uid, ids, {
            'confirm_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)
        })
        #Update PR if any
        pur_req_obj = self.pool.get('pur.req')
        pr_ids = pur_req_obj.search(cr, uid, [('drawing_order_id','in',ids)])
        if pr_ids:
            pur_req_obj.update_pdf(cr, uid, pr_ids)
        # Add watermark
        addwatermark_line_ids = []
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        for order in self.browse(cr, uid, ids, context=context):
            if order.add_watermark_when_ready:
                #TODO: Remove drawing_file and original_drawing search
                line_ids = drawing_order_line_obj.search(cr, uid, [('order_id','=',order.id),
                                                               ('drawing_file_name','!=',False),
                                                               #('drawing_file','!=',False),
                                                               ('original_drawing','=',False)], context=context)
                if line_ids:
                    addwatermark_line_ids.extend(line_ids)
                    for i in xrange(0, len(line_ids), CHUNK_SIZE):
                        for line in drawing_order_line_obj.browse(cr, uid, line_ids[i:i + CHUNK_SIZE], context=context):
                            drawing_order_line_obj.write(cr, uid, [line.id], {
                                'original_drawing': line.drawing_file,
                            })
        drawing_order_line_obj._add_watermark(cr, uid, addwatermark_line_ids)
        # send email to the user group that can confirm
        self._email_notify(cr, uid, ids, 'need your confirmation', ['mrp_cnc_wo_group_confirm'], context)
        return True

    # +++ HoangTK - 12/14/2015 : Add check drawing order lines into a separate function
    def _is_ready(self, cr, uid, ids, context=None):
        logs = self.check_bom_file_and_drawing(cr, uid, ids,for_ready=True)

        if len(logs) == 0:
            super(drawing_order,self).write(cr, uid, ids, {
                'notice': ''
            })
            return True
        return False

    # --- HoangTK - 12/14/2015
    def action_confirm(self, cr, uid, ids, context=None):
        # +++ HoangTK - 12/14/2015 : Move to action_ready
        #         for order in self.browse(cr, uid, ids, context=context):
        #             #must have cnc lines
        #             if not order.order_lines:
        #                 raise osv.except_osv(_('Error!'), _('Please add lines for order [%s]%s')%(order.id, order.name))
        #             for line in order.order_lines:
        #                 if not line.drawing_file_name:
        #                     raise osv.except_osv(_('Invalid Action!'), _('The line''s "Drawing PDF" file is required!'))
        # --- HoangTK - 12/14/2015 : Move to action_ready
        if not self._is_ready(cr, uid, ids, context=context):
            return False
        self._set_state(cr, uid, ids, 'confirmed', context)

        pur_req_obj = self.pool.get('pur.req')
        generate_wizard_ids = []
        generate_pr_wizard_obj = self.pool.get('generate.pr.wizard')
        warehouse_obj = self.pool.get('stock.warehouse')
        order_line_obj = self.pool.get('drawing.order.line')
        product_do_line_obj = self.pool.get('product.do.line')
        attachment_obj = self.pool.get('ir.attachment')
        show_pr_wizzard_do_ids = []
        for order in self.browse(cr, uid, ids, context=context):
            for line in order.order_lines:
                if line.part_type in ['ASM','PS','POEM','CD']:
                     if line.drawing_file_name:
                         product_do_line_vals = {
                             'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                             'product_id': line.product_id.id,
                             'do_line_id': line.id,
                             'drawing_order_id': order.id,
                             'drawing_file_name': line.drawing_file_name,
                             #'drawing_file': line.drawing_file,
                             'type': 'auto'
                         }
                         file_ids = order_line_obj.get_order_line_pdf_ids(cr, uid,line.id, line.drawing_file_name)
                         if file_ids:
                             drawing_file = attachment_obj.browse(cr, uid, file_ids[0]).datas
                             product_do_line_vals.update({
                                 'drawing_file2': drawing_file,
                             })
                             product_do_line_obj.create(cr, uid, product_do_line_vals)

            #Check if no PR with this DO ?
            existing_pr_ids = pur_req_obj.search(cr, uid, [('drawing_order_id','=',order.id),
                                                           ('pr_type','!=','mfg_o')])
            if not existing_pr_ids:
                delivery_date = False
                warehouse_id = False
                if order.mo_id:
                    if order.mo_id.delivery_date:
                        delivery_date = order.mo_id.delivery_date
                    warehouse_ids = warehouse_obj.search(cr, uid, [('lot_input_id', '=', order.mo_id.location_src_id and
                                                                    order.mo_id.location_src_id.id or False)],
                                                         context=context)
                    if warehouse_ids:
                        warehouse_id = warehouse_ids[0]
                if delivery_date and warehouse_id:
                    generate_wizard_ids.append(generate_pr_wizard_obj.create(cr, uid, {'delivery_date': delivery_date,
                                                                            'warehouse_id': warehouse_id}, context=context))
            else:
                show_pr_wizzard_do_ids.append(order.id)

        # send email to the user group that can approve
        self._email_notify(cr, uid, ids, 'need your approval', ['mrp_cnc_wo_group_approve'], context)
        # Automatic generate PR
        if generate_wizard_ids:
            generate_pr_wizard_obj.do_generate(cr, uid, generate_wizard_ids, context={
                'drawing_order_ids': ids,
            })
        if show_pr_wizzard_do_ids:
            return self.generate_pr(cr, uid, show_pr_wizzard_do_ids, context)

    def action_cancel(self, cr, uid, ids, context=None):
        self._check_done_lines(cr, uid, ids, context)
        # set the cancel state
        self._set_state(cr, uid, ids, 'cancel', context)
        return True

    def action_draft(self, cr, uid, ids, context=None):
        self._set_state(cr, uid, ids, 'draft', context)
        return True

    def action_approve(self, cr, uid, ids, context=None):
        if not self._is_ready(cr, uid, ids, context=context):
            return False
        self._set_state(cr, uid, ids, 'approved', context)
        # send email to the user group that can CNC done
        self._email_notify(cr, uid, ids, 'was approved', ['mrp_cnc_wo_group_cnc_mgr'], context)
        return True

    def action_reject_callback(self, cr, uid, ids, message, context=None):
        # set the draft state
        self._set_state(cr, uid, ids, 'rejected', context)
        self.write(cr, uid, ids, {'reject_message': message})
        # send email to the user for the rejection message
        email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'], context=context)['email']
        for order in self.browse(cr, uid, ids, context=context):
            if order.create_uid.email:
                email_content = 'CNC reminder: %s was rejected' % order.name
                utils.email_send_group(cr, uid, email_from, order.create_uid.email, email_content, email_content,
                                       context=context)
        return True

    def action_reject(self, cr, uid, ids, context=None):
        ctx = dict(context)
        ctx.update({'confirm_title': 'Confirm rejection message',
                    'src_model': 'drawing.order',
                    "model_callback": 'action_reject_callback',})
        return self.pool.get('confirm.message').open(cr, uid, ids, ctx)

    def unlink(self, cr, uid, ids, context=None):
        orders = self.read(cr, uid, ids, ['state','w'
                                                  'orkorder_id'], context=context)
        for s in orders:
            if s['state'] not in ['draft', 'cancel']:
                raise osv.except_osv(_('Invalid Action!'), _('Only the orders in draft or cancel state can be delete.'))
            if s['workorder_id']:
                raise osv.except_osv(_('Invalid Action!'), _('Can not delete DO that already generated tasks.'))
        self._check_done_lines(cr, uid, ids, context)
        self._email_notify(cr, uid, ids, 'was deleted', ['mrp_cnc_wo_group_cnc_mgr'], context)
        return super(drawing_order, self).unlink(cr, uid, ids, context=context)

    def unlink_pr_workorder(self, cr, uid, ids, context=None):
        if not ids:
            ids = []
        if isinstance(ids, (int, long)):
            ids = [ids]
        pur_req_obj = self.pool.get('pur.req')
        work_order_obj = self.pool.get('mrp.production.workcenter.line')
        cnc_work_order_obj = self.pool.get('work.order.cnc')
        for order in self.browse(cr, uid, ids, context=context):
            req_ids = pur_req_obj.search(cr, uid, [('drawing_order_id','=',order.id)], context=context)
            if req_ids:
                pur_req_obj.write(cr, uid, req_ids, {'drawing_order_id': None}, context=context)
            wo_ids = work_order_obj.search(cr, uid, [('drawing_order_id','=',order.id)], context=context)
            if wo_ids:
                work_order_obj.write(cr, uid, {'drawing_order_id': None}, context=context)
            cnc_wo_ids = cnc_work_order_obj.search(cr, uid, [('drawing_order_id','=',order.id)], context=context)
            if cnc_wo_ids:
                cnc_work_order_obj.write(cr, uid, {'drawing_order_id': None}, context=context)
            self.write(cr, uid, ids, {
                'req_id': None,
                'req_id_pms': None,
                'req_id_pml': None,
                'req_o_id': None,
                'cnc_workorder_id': None,
                'workorder_id': None,
            }, context=context)

    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        order = self.browse(cr, uid, id, context=context)
        if order.bom_file:
            default.update({
                'bom_file': order.bom_file,
                'bom_file_name': order.bom_file_name,
                'state': 'bom_uploaded'
            })
        else:
            default.update({
                'bom_file_name': False,
            })
        return super(drawing_order, self).copy_data(cr, uid, id, default, context)

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        old_data = self.read(cr, uid, id, ['name', 'state'], context=context)
        default.update({
            #'name': '%s (copy)' % old_data['name'],
            'name': old_data['name'],
            'mfg_task_id': None,
            'sale_product_ids': None,
            'reject_message': None,
            'req_id': None,
            'req_id_pms': None,
            'req_id_pml': None,
            'req_o_id': None,
            'req_ids': [],
            'cnc_workorder_id': None,
            'workorder_id': None,
            'copy_order_id': id,
        })
        new_id = super(drawing_order, self).copy(cr, uid, id, default, context)
        has_pdf = False
        if new_id:
            #Try to copy the pdf and dxfs:
            order_line_obj = self.pool.get('drawing.order.line')
            new_line_ids = order_line_obj.search(cr, uid, [('order_id', '=', new_id),
                                             '|', ('drawing_file_name', '!=', False),('dxf_file_name','!=', False)],
                                   context=context)

            for new_line in order_line_obj.read(cr, uid, new_line_ids, ["id","item_no","part_number","product_id"]):
                origin_line_ids = order_line_obj.search(cr, uid, [('order_id', '=', id),
                                                                  ('item_no', '=', new_line["item_no"]),
                                                                  ('part_number', '=', new_line["part_number"]),
                                                                  ('product_id', '=', new_line["product_id"] and new_line["product_id"][0] or new_line["product_id"])],
                                                        context=context)
                if origin_line_ids:
                    has_pdf = True
                    origin_line = order_line_obj.browse(cr, uid, origin_line_ids, context=context)[0]
                    order_line_obj.write(cr, uid, [new_line["id"]],{
                        'drawing_file': origin_line.drawing_file,
                        'original_drawing': origin_line.original_drawing,
                        'dxf_file': origin_line.dxf_file,
                    })

        if has_pdf:
            self.write(cr, uid, [new_id], {'state': 'pdf_uploaded'})
        return new_id
        # +++ HoangTK - 11/17/2015: Add update_parts function

    @staticmethod
    def split_work_steps(work_steps):
        steps = []
        if work_steps:
            steps = work_steps.split(' ')
        return steps

    def upload_dxf(self, cr, uid, ids, context=None):
        #Check if cnc work order of this DO is in prepare state ?
        work_order_cnc_obj = self.pool.get('work.order.cnc')
        cnc_wo_ids = work_order_cnc_obj.search(cr, uid, [('drawing_order_id','in',ids),
                                                         ('state','=','prepare')], context=context)
        if cnc_wo_ids:
            return self.pool.get('warning').info(cr, uid, title='Information', message=_(
                "Can not upload DXF when CNC Work Order in Prepare state, please change state!"))
        mod_obj = self.pool.get('ir.model.data')
        res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'view_upload_multi_dxfs')
        res_id = res and res[1] or False
        return {
            'name': 'Upload multi DXFs',
            'res_model': 'upload.multi.dxfs',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'target': 'new'
        }

    def generate_pr(self, cr, uid, ids, context=None):
        mod_obj = self.pool.get('ir.model.data')
        res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'view_generate_pr_wizard')
        res_id = res and res[1] or False
        mfg_o = context and context.get('mfg_o', False) or False
        today = datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)
        return {
            'name': 'Purchase Requisition Generator',
            'res_model': 'generate.pr.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'context': {'drawing_order_ids': ids, 'mfg_o': mfg_o, 'delivery_date': today},
            'target': 'new'
        }

    def generate_tasks(self, cr, uid, ids, context):
        production_obj = self.pool.get('mrp.production')
        production_obj._generate_task_from_drawing_orders(cr, uid, ids, context=context)
        return True

    @staticmethod
    def get_string_from_xls_cell(cell_value):
        value = False
        if cell_value == xlrd.empty_cell.value:
            return value
        value = '%s' % cell_value
        value = value.strip('\t').strip().replace('\n', ' ').replace('\r', '')
        return value

    def _read_cell(self, worksheet, data_name, row, column):
        try:
            return worksheet.cell(row, column).value
        except IndexError,e:
            raise osv.except_osv(_('Error!'),_('Bom file errors, can not read %s from row %s, column %s!.')%(data_name, row+1, column+1))

    def read_bom_line(self, worksheet, row):
        #item_cell_value = worksheet.cell(row, 0).value
        item_cell_value = self._read_cell(worksheet, _('Item No'), row, 0)
        item_no = self.get_string_from_xls_cell(item_cell_value)
        if type(item_cell_value) is float:
            if item_cell_value == ceil(item_cell_value):
                item_no = int(item_cell_value)
            else:
                current_item_no = item_cell_value
                previous_item_no = False
                if row >= 3:
                    # previous_item_no = worksheet.cell(row-1, 0).value
                    previous_item_no = self._read_cell(worksheet, _('Item No'), row-1, 0)
                if isinstance(current_item_no, float) and isinstance(previous_item_no, float):
                    if (floor(previous_item_no) == floor(current_item_no)):
                        item_first_part = int(floor(previous_item_no))
                        previous_decimal_str = '%s' % (previous_item_no - floor(previous_item_no))
                        prev_decimals = ['0.9', '0.19', '0.29', '0.39', '0.49', '0.59', '0.69', '0.79', '0.89', '0.99']
                        curr_decimals = ['10', '20', '30', '40', '50', '60', '70', '80', '90', '100']
                        for i in range(len(prev_decimals)):
                            prev_decimal = prev_decimals[i]
                            if prev_decimal == previous_decimal_str:
                                item_no = '%s.%s' % (item_first_part, curr_decimals[i])
        # thickness = worksheet.cell(row, 6).value
        thickness = self._read_cell(worksheet, _('Thickness'), row, 6)

        if type(thickness) is float:
            if thickness.is_integer():
                thickness = int(thickness)
        else:
            thickness = self.get_string_from_xls_cell(thickness)
        return {
            'item_no' : item_no,
            # 'part_name' : self.get_string_from_xls_cell(worksheet.cell(row, 1).value),
            'part_name': self.get_string_from_xls_cell(self._read_cell(worksheet, _('Part Number'), row, 1)),
            # 'description': self.get_string_from_xls_cell(worksheet.cell(row, 2).value),
            'description': self.get_string_from_xls_cell(self._read_cell(worksheet, _('Description'), row, 2)),
            # 'erp_no' : self.get_string_from_xls_cell(worksheet.cell(row, 3).value),
            'erp_no': self.get_string_from_xls_cell(self._read_cell(worksheet, _('ERP #'), row, 3)),
            # 'standard': self.get_string_from_xls_cell(worksheet.cell(row, 4).value),
            'standard': self.get_string_from_xls_cell(self._read_cell(worksheet, _('Standard'), row, 4)),
            # 'material': self.get_string_from_xls_cell(worksheet.cell(row, 5).value),
            'material': self.get_string_from_xls_cell(self._read_cell(worksheet, _('Material'), row, 5)),
            'thickness': thickness,
            # 'work_steps': self.get_string_from_xls_cell(worksheet.cell(row, 7).value),
            'work_steps': self.get_string_from_xls_cell(self._read_cell(worksheet, _('Work Steps'), row, 7)),
            # 'part_type': self.get_string_from_xls_cell(worksheet.cell(row, 8).value),
            'part_type': self.get_string_from_xls_cell(self._read_cell(worksheet, _('Part Type'), row, 8)),
            # 'bom_qty': worksheet.cell(row, 9).value,
            'bom_qty': self._read_cell(worksheet, _('Bom Quantity'), row, 9),
            # 'total_qty': worksheet.cell(row, 10).value,
            'total_qty': self._read_cell(worksheet, _('Total Quantity'), row, 10),
        }

    def check_bom_file_content(self, cr, uid, order_name, bom_file_name, bom_content,
                               check_bom_file_name = True,
                               check_item_no = True,
                               check_erp_no_missing = True,
                               check_erp_no_duplicate = True,
                               check_total_qty = False,
                               check_description_instead_of_part_name = False,
                               use_row_instead_of_item_no_for_error=False):
        logs = []
        department_obj = self.pool.get('hr.department')
        product_obj = self.pool.get('product.product')
        # Rule 1: Check if valid XLS file
        inputStr = StringIO.StringIO()
        inputStr.write(bom_content.decode('base64'))
        workbook = False
        try:
            workbook = xlrd.open_workbook(file_contents=inputStr.getvalue())
        except XLRDError:
            logs.append(_('Invalid file type'))
        if workbook:
            worksheet = workbook.sheet_by_index(0)
            # Rule 2: File name, A1 cell in BOM File = Order name
            a1_cell = self.get_string_from_xls_cell(worksheet.cell(0, 0).value)
            if check_bom_file_name:
                if bom_file_name != order_name or a1_cell != order_name:
                    logs.append(_('Bom file name (%s) and A1 cell (%s) not match drawing order name (%s)' % (
                    bom_file_name, a1_cell, order_name)))
            # Check if bom file has valid format
            row = 2
            if worksheet.ncols < 11:
                logs.append(_('Bom file does not contain enough columns, please check the bom file'))
            item_nos = []
            erp_nos = {}
            #produced_partnames = []
            while row < worksheet.nrows:
                row_logs = []
                bom_line = self.read_bom_line(worksheet=worksheet, row=row)
                check_row = True
                if check_description_instead_of_part_name:
                    if not bom_line['description']:
                        check_row = False
                else:
                    if not bom_line['part_name']:
                        check_row = False
                if check_row:
                    # Rule 3: Check item no duplicate
                    if check_item_no:
                        if bom_line['item_no'] in item_nos:
                            row_logs.append('Item (%s) is duplicated' % bom_line['item_no'])
                        else:
                            item_nos.append(bom_line['item_no'])
                    # Rule 4: Check produced part name duplicate
                    #if bom_line['part_type'] == 'ASM':
                    #    if bom_line['part_name'] in produced_partnames:
                    #        row_logs.append('Part name (%s) is duplicated' % bom_line['part_name'])
                    #    else:
                    #        produced_partnames.append(bom_line['part_name'])
                    # Rule 5: Check thickness not empty for PML
                    if bom_line['part_type'] in ['PML','PMS']:
                        thickness = bom_line['thickness']
                        try:
                            if not thickness:
                                raise ValueError('Thickness can not be empty')
                            thickness = int(bom_line['thickness'])
                        except ValueError:
                            row_logs.append('Thickness (%s) is invalid' % bom_line['thickness'])
                    # Rule 6: Check material not empty for PURCH-MS
                    if bom_line['part_type'] == 'PMS':
                        if not bom_line['material']:
                            row_logs.append('Material must not be empty')
                    # Rule 7: Check missing erp_no and exists in database

                    if bom_line['part_type'] not in ['ASM','CD']:
                        if not bom_line['erp_no']:
                            if check_erp_no_missing:
                                # If PURCH-MS check material and thickness first
                                if bom_line['part_type'] == 'PMS':
                                    product_ids = product_obj.search(cr, uid, [
                                        ('material', '=', bom_line['material']),
                                        ('thickness', '=', bom_line['thickness']),
                                    ])
                                    if not product_ids or len(product_ids) >= 2:
                                        row_logs.append('ERP # (%s) is missing (Can not find any erp # or found more '
                                                        'than 2 with material=%s and thickness=%s)' % (bom_line['part_type'],
                                                                                                      bom_line['material'],
                                                                                                      bom_line['thickness']))
                                else:
                                    row_logs.append('ERP # (%s) is missing' % bom_line['part_type'])
                        else:
                            #Rule 8: Not allow duplicate ERP #, name, description for PURCH-OEM
                            if check_erp_no_duplicate:
                                if bom_line['part_type'] == 'POEM':
                                    name_des = '%s-%s'% (bom_line['part_name'], bom_line['description'])
                                    if bom_line['erp_no'] in erp_nos:
                                        if name_des != erp_nos[bom_line['erp_no']]:
                                            row_logs.append('Item (%s): ERP # (%s) is duplicated' % (bom_line['item_no'],bom_line['erp_no']))
                                    else:
                                        erp_nos.update({bom_line['erp_no']:name_des})
                            product_ids = product_obj.search(cr, uid, [
                                ('default_code', '=', bom_line['erp_no'])
                            ])
                            if not product_ids:
                                row_logs.append('ERP # (%s) is invalid' % bom_line['erp_no'])
                    try:
                        bom_qty = int(bom_line['bom_qty'])

                    # Rule 9.1: Check bom quantity
                    except ValueError:
                        row_logs.append('Bom quantity (%s) is invalid' % bom_line['bom_qty'])
                    if check_total_qty:
                        try:
                            total_qty = int(bom_line['total_qty'])
                        # Rule 9.2: Check total quantity
                        except ValueError:
                            row_logs.append('Total quantity (%s) is invalid' % bom_line['total_qty'])
                    # Rule 10: Check part type
                    part_types = [type[0] for type in PART_TYPE_SELECTION]
                    if not bom_line['part_type'] in part_types:
                        row_logs.append('Part type (%s) must in %s' % (bom_line['part_type'], PART_TYPE_SELECTION))
                    # Rule 11: Check work steps
                    steps = self.split_work_steps(bom_line['work_steps'])
                    department_ids = department_obj.search(cr, uid, [
                        ('code', 'in', steps),
                        ('code', 'in', WORK_STEP_LIST)
                    ])
                    if len(department_ids) != len(steps) or len(steps) == 0:
                        row_logs.append(
                            'Work steps (%s) must in %s and not empty' % (bom_line['work_steps'], WORK_STEP_LIST))
                        #Rule 12: PURCH-S have only 1 workstep
                    elif bom_line['part_type'] == 'PS' and len(steps) != 1:
                        row_logs.append(_('PS must have only 1 work step'))
                    if len(row_logs) > 0:
                        if use_row_instead_of_item_no_for_error:
                            logs.append(
                                '------------Row %s-------------' % (row+1))
                        else:
                            logs.append('-------------%s-%s-------------' % (bom_line['item_no'], bom_line['part_name']))
                        logs.extend(row_logs)
                row += 1
        return logs

    def is_empty_drawing(self, cr, uid, ids):
        result = False
        for order in self.browse(cr, uid, ids):
            if len(order.order_lines) == 0:
                bom_log = _('Order lines must not be empty')
                if order.bom_log:
                    bom_log += '\n' + order.bom_log
                super(drawing_order, self).write(cr, uid, [order.id], {'bom_log': bom_log})
                result = True
        return result

    def is_enough_drawing(self, cr, uid, ids):
        result = True
        for order in self.browse(cr, uid, ids):
            total_required_drawing = 0
            missing_upload_drawing = 0
            order_line_obj = self.pool.get('drawing.order.line')
            line_ids = order_line_obj.search(cr, uid, [('order_id', '=', order.id)])
            order_lines = order_line_obj.read(cr, uid, line_ids, ['part_type', 'drawing_file_name'])
            for line in order_lines:
                #if line.part_type in ['ASM','CD']:
                if line['part_type'] in ['ASM', 'CD']:
                    total_required_drawing += 1
                    #if not line.drawing_file_name:
                    if not line['drawing_file_name']:
                        missing_upload_drawing += 1
            if missing_upload_drawing > 0:
                bom_log = _('%s parts are missing PDF drawings, please upload them ' \
                            '(Total %s are required, %s are uploaded)!') % (missing_upload_drawing,
                                                                          total_required_drawing,
                                                                          total_required_drawing - missing_upload_drawing)
                if order.bom_log:
                    bom_log += '\n' + order.bom_log
                super(drawing_order, self).write(cr, uid, [order.id],{'bom_log': bom_log})
                result = False
        return result


    def check_bom_file_and_drawing(self, cr, uid, ids,for_ready=False):
        error_logs = {}
        for order in self.browse(cr, uid, ids):
            logs = []
            if order.bom_file:
                #bom_file_name = order.bom_file_name.split('.')[0]
                bom_file_name = os.path.splitext(order.bom_file_name)[0]
                logs = self.check_bom_file_content(cr, uid, order.name, bom_file_name, order.bom_file)
            total_required_drawing = 0
            total_required_dxf = 0
            missing_upload_dxf = 0
            missing_dxf_part_names = []
            missing_upload_drawing = 0
            missing_part_names = []
            invalid_pdf_list = []
            invalid_dxf_list = []
            if for_ready:
                if len(order.order_lines) == 0:
                    logs.append(_('Order must not be empty'))
                #Change to read function
                order_line_obj = self.pool.get('drawing.order.line')
                line_ids = order_line_obj.search(cr, uid, [('order_id','=', order.id)])
                order_lines = order_line_obj.read(cr, uid, line_ids, ['part_type','drawing_file_name',
                                                                  'material','part_number','dxf_file_name',
                                                                  'pdf_valid','dxf_valid','item_no'
                                                                  ])
                for line in order_lines:
                #for line in order.order_lines:
                    #if line.part_type in ['ASM','POEM','PML','CD','PMS']:
                    if line['part_type'] in ['ASM', 'POEM', 'PML', 'CD', 'PMS','PMC']:
                        total_required_drawing += 1
                        #if not line.drawing_file_name:
                        if not line['drawing_file_name']:
                            missing_upload_drawing += 1
                            #missing_part_names.append(line.part_number)
                            missing_part_names.append(line['part_number'])
                    #if line.part_type == 'PMS':
                    if line['part_type'] == 'PMS':
                        #if line.material and not "rubber" in line.material.lower():
                        if line['material'] and not "rubber" in line['material'].lower():
                            total_required_dxf += 1
                        #if not line.dxf_file_name:
                        if not line['dxf_file_name']:
                            #if line.material and not "rubber" in line.material.lower():
                            if line['material'] and not "rubber" in line['material'].lower():
                                missing_upload_dxf += 1
                                #missing_dxf_part_names.append(line.part_number)
                                missing_dxf_part_names.append(line['part_number'])
                    #if not line.pdf_valid:
                    if not line['pdf_valid']:
                        #invalid_pdf_list.append({'item_no': line.item_no, 'part_number': line.part_number})
                        invalid_pdf_list.append({'item_no': line['item_no'], 'part_number': line['part_number']})
                    #if not line.dxf_valid:
                    if not line['dxf_valid']:
                        #invalid_dxf_list.append({'item_no': line.item_no, 'part_number': line.part_number})
                        invalid_dxf_list.append({'item_no': line['item_no'], 'part_number': line['part_number']})
                if missing_upload_drawing > 0:
                    logs.append(_('%s parts are missing PDF drawings, please upload them ' \
                                '(Total %s are required, %s are uploaded):') % (missing_upload_drawing,
                                                                                total_required_drawing,
                                                                                total_required_drawing - missing_upload_drawing))
                    for part_name in missing_part_names:
                        logs.append("- %s"%part_name)
                if missing_upload_dxf > 0:
                    logs.append(_('%s parts are missing DXF drawings, please upload them ' \
                                  '(Total %s are required, %s are uploaded):') % (missing_upload_dxf,
                                                                                  total_required_dxf,
                                                                                  total_required_dxf - missing_upload_dxf))
                    for part_name in missing_dxf_part_names:
                        logs.append("- %s" % part_name)

                for invalid_part in invalid_pdf_list:
                    logs.append('(%s) %s has invalid pdf' % (invalid_part['item_no'], invalid_part['part_number']))
                for invalid_part in invalid_dxf_list:
                    logs.append('(%s) %s has invalid dxf' % (invalid_part['item_no'], invalid_part['part_number']))

            if len(logs) > 0:
                error_logs.update({order.id: logs})
                super(drawing_order,self).write(cr, uid, [order.id],{
                    'bom_log': '\n'.join(logs),
                    'notice': '',
                                                                     })
            else:
                super(drawing_order, self).write(cr, uid, [order.id], {'bom_log': ''})
        return error_logs

    def can_reuse_drawing_file(self, cr, uid, id, context=None):
        result = False
        order_part_numbers = []
        order_line_obj = self.pool.get('drawing.order.line')
        line_ids = order_line_obj.search(cr, uid, [('order_id', '=', id)])
        order_lines = order_line_obj.read(cr, uid, line_ids, ['drawing_file_name','part_number'])
        for line in order_lines:
            if not line['drawing_file_name']:
                order_part_numbers.append(line['part_number'])
        existing_line_ids = order_line_obj.search(cr, uid, [
            ('part_number', 'in', order_part_numbers),
            ('state', 'in', ['confirmed', 'approved']),
            ('drawing_file_name', '!=', False)
        ])
        if len(existing_line_ids) > 0:
            result = True
        return result

    def reuse_dxfs(self, cr, uid, ids, context=None):
        reuse_count = 0
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        attachment_obj = self.pool.get('ir.attachment')
        for order in self.browse(cr, uid, ids, context=context):
            if order.state in ['draft', 'bom_uploaded', 'pdf_uploaded', 'rejected','confirmed']:
                line_ids = drawing_order_line_obj.search(cr, uid, [('order_id', '=', order.id),
                                                                   ('part_number', '!=', False)
                                                                   ],
                                                         context=context)
                order_lines = drawing_order_line_obj.read(cr, uid, line_ids, ['id','dxf_valid','dxf_file_name',
                                                                              'part_number'])
                for line in order_lines:
                    if line['dxf_valid'] == False or line['dxf_file_name'] == False:
                        existing_line_ids = drawing_order_line_obj.search(cr, uid, [
                            ('part_number', '=', line['part_number']),
                            ('state', 'in', ['ready', 'confirmed', 'approved']),
                            ('dxf_file_name', '!=', False),
                        ], order='create_date desc')
                        if not existing_line_ids:
                            # Try to search pdf in current order id
                            existing_line_ids = drawing_order_line_obj.search(cr, uid, [
                                ('order_id','=',order.id),
                                ('id','!=',line['id']),
                                ('part_number', '=', line['part_number']),
                                ('dxf_file_name', '!=', False),
                            ], order='create_date desc')
                        if existing_line_ids:
                            existing_line = drawing_order_line_obj.read(cr, uid, existing_line_ids[0],
                                                                        ['dxf_file_name'], context=context)
                            dxf_file_name = existing_line['dxf_file_name']
                            file_ids = drawing_order_line_obj.get_order_line_dxf_ids(cr, uid, existing_line_ids,
                                                                                     dxf_file_name)
                            if file_ids:
                                attachment = attachment_obj.read(cr, uid, file_ids[0], ['res_id'], context=context)
                                reuse_id = attachment['res_id']
                                reuse_line = drawing_order_line_obj.browse(cr, uid, reuse_id, context=context)
                                new_attachment_id = attachment_obj.create(cr, uid, {
                                    'name': reuse_line.dxf_file_name,
                                    'res_name': reuse_line.dxf_file_name,
                                    'datas_fname': reuse_line.dxf_file_name,
                                    'res_id': line['id'],
                                    'type': 'binary',
                                    'res_model': 'drawing.order.line',
                                    'datas': reuse_line.dxf_file
                                })
                                drawing_order_line_obj.write(cr, uid, [line['id']], {
                                    'dxf_file_name': reuse_line.dxf_file_name,
                                })
                                reuse_count += 1
        self.check_bom_file_and_drawing(cr, uid, ids, for_ready=True)
        return self.pool.get('warning').info(cr, uid, title='Information', message=_(
            "%s DXF has been reused.") % reuse_count)

    def reuse_parts(self, cr, uid, ids, context=None):
        """ Search all drawing order line to find if we can reuse any existing pdf

        :param cr:
        :param uid:
        :param ids:
        :param context:
        :return:
        """
        reuse_count = 0
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        attachment_obj = self.pool.get('ir.attachment')
        for order in self.browse(cr, uid, ids):
            if order.state in ['draft','bom_uploaded','pdf_uploaded','rejected']:
                order_count = 0
                line_ids = drawing_order_line_obj.search(cr, uid, [('order_id', '=', order.id),
                                                                   ('part_number','!=', False)
                                                                   ],
                                                         context=context)
                order_lines = drawing_order_line_obj.read(cr, uid, line_ids, ['id','pdf_valid','drawing_file_name',
                                                                              'part_number'])
                for line in order_lines:
                    if line['pdf_valid'] == False or line['drawing_file_name'] == False:
                        existing_line_ids = drawing_order_line_obj.search(cr, uid, [
                            ('part_number','=',line['part_number']),
                            ('state','in',['ready','confirmed','approved']),
                            ('drawing_file_name','!=',False),
                        ], order='create_date desc')
                        if not existing_line_ids:
                            # Try to search pdf in current order id
                            existing_line_ids = drawing_order_line_obj.search(cr, uid, [
                                ('order_id','=',order.id),
                                ('id','!=',line['id']),
                                ('part_number', '=', line['part_number']),
                                ('drawing_file_name', '!=', False),
                            ], order='create_date desc')
                        if existing_line_ids:
                            existing_line = drawing_order_line_obj.read(cr, uid, existing_line_ids[0], ['drawing_file_name'], context=context)
                            drawing_file_name = existing_line['drawing_file_name']
                            file_ids = drawing_order_line_obj.get_order_line_pdf_ids(cr, uid, existing_line_ids, drawing_file_name)
                            if file_ids:
                                attachment = attachment_obj.read(cr, uid, file_ids[0], ['res_id'], context=context)
                                reuse_id = attachment['res_id']
                                reuse_line = drawing_order_line_obj.browse(cr, uid, reuse_id, context=context)
                                new_attachment_id = attachment_obj.create(cr, uid, {
                                    'name': reuse_line.drawing_file_name,
                                    'res_name': reuse_line.drawing_file_name,
                                    'datas_fname': reuse_line.drawing_file_name,
                                    'res_id': line['id'],
                                    'type': 'binary',
                                    'res_model': 'drawing.order.line',
                                    'datas': reuse_line.drawing_file
                                })
                                drawing_order_line_obj.write(cr, uid, [line['id']],{
                                    'drawing_file_name': reuse_line.drawing_file_name,
                                    'original_drawing': reuse_line.original_drawing,
                                })
                                order_count += 1
                if order_count > 0 and order.state == 'bom_uploaded':
                    super(drawing_order, self).write(cr, uid, [order.id], {
                        'state': 'pdf_uploaded'
                    })
                reuse_count += order_count
        self.check_bom_file_and_drawing(cr, uid, ids)
        return self.pool.get('warning').info(cr, uid, title='Information', message=_(
                "%s drawing PDF has been reused.") % reuse_count)

    def update_parts(self, cr, uid, ids, context=None):
        """ Read the bom file and add/update part and quantity to drawing order line.
        """
        result = True
        error_logs = self.check_bom_file_and_drawing(cr, uid, ids)
        if len(error_logs) > 0:
            raise osv.except_osv(_('Error!'),
                                 _('Bom file errors, please check the log tab!.'))
        product_obj = self.pool.get('product.product')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        bom_obj = self.pool.get('mrp.bom')
        department_obj = self.pool.get('hr.department')
        duplicate_parts = []
        for order in self.browse(cr, uid, ids):
            if order.bom_file:
                #mo_qty = order.mo_id.product_qty
                big_assembly_qty = self.get_big_subassembly_qty(cr, uid, order)
                # Remove old drawing order lines
                old_drawing_order_line_ids = drawing_order_line_obj.search(cr, uid, [
                    ('order_id', '=', order.id)
                ])
                drawing_order_line_obj.unlink(cr, uid, old_drawing_order_line_ids)
                # Read the bom file and add parts
                inputStr = StringIO.StringIO()
                inputStr.write(order.bom_file.decode('base64'))
                workbook = xlrd.open_workbook(file_contents=inputStr.getvalue())
                worksheet = workbook.sheet_by_index(0)
                row = 2
                while row < worksheet.nrows:
                    bom_line = self.read_bom_line(worksheet=worksheet, row=row)
                    if bom_line['part_name']:
                        item_no = bom_line['item_no']
                        part_name = bom_line['part_name']
                        erp_no = bom_line['erp_no']
                        description = bom_line['description']
                        bom_qty = int(bom_line['bom_qty'])
                        standard = bom_line['standard']
                        material = bom_line['material']
                        thickness = bom_line['thickness']
                        need_qty = bom_qty * big_assembly_qty
                        part_type = bom_line['part_type']
                        work_steps = bom_line['work_steps']
                        steps = self.split_work_steps(work_steps)
                        if part_name:
                            product_id = False
                            if part_type in ['ASM','CD']:
                                product_ids = product_obj.search(cr, uid, [
                                    ('name', '=', part_name)
                                ])
                                if not product_ids:
                                    product_id = product_obj.create(cr, uid, {
                                        'name': part_name,
                                    })
                                else:
                                    product_id = product_ids[0]
                            else:
                                product_ids = []
                                if part_type == 'PMS':
                                    product_ids = product_obj.search(cr, uid, [
                                        ('material', '=', bom_line['material']),
                                        ('thickness', '=', bom_line['thickness']),
                                    ])
                                if len(product_ids) == 0 or len(product_ids) > 1:
                                    product_ids = product_obj.search(cr, uid, [
                                        ('default_code', '=', erp_no)
                                    ])
                                if len(product_ids) > 0:
                                    product_id = product_ids[0]
                            product = product_obj.browse(cr, uid, product_id)
                            if product:
                                erp_no = product.default_code
                            first_step = steps[0]
                            last_step = steps[len(steps) - 1]
                            # Check if drawing order line exits ?
                            # Not combine line anymore
                            #order_line_ids = drawing_order_line_obj.search(cr, uid, [
                            #    ('order_id', '=', order.id),
                            #    ('product_id', '=', product_id),
                            #    ('work_steps', '=', work_steps)
                            #])
                            #if order_line_ids:
                            #    if part_type in ['PURCH-S', 'PURCH-OEM', 'PRODUCED']:
                            #        duplicate_parts.append(part_name)
                            #        row += 1
                            #        continue
                            #    else:
                            #        order_line_id = order_line_ids[0]
                            #else:
                            order_line_id = drawing_order_line_obj.create(cr, uid, {
                                'order_id': order.id,
                                'product_id': product_id,
                            })
                            order_line = drawing_order_line_obj.browse(cr, uid, order_line_id)
                            vals = {
                                'part_number': part_name,
                                'item_no': item_no,
                                #'bom_qty': bom_qty + order_line.bom_qty,
                                'bom_qty': bom_qty,
                                'quantity': need_qty,
                                'work_steps': work_steps,
                                'first_step': first_step,
                                'last_step': last_step,
                                'part_type': part_type,
                                'description': description,
                                'erp_no': erp_no,
                                'material': material,
                                'standard': standard,
                                'thickness': thickness,
                            }
                            for step in steps:
                                vals.update({
                                    #'%s_need_qty' % (step,): need_qty + getattr(order_line, "%s_need_qty" % step, 0),
                                    '%s_need_qty' % (step,): need_qty + self.get_department_qty(step, 'need_qty', order_line),
                                    '%s_prepare_qty' % (step,): 0,
                                    '%s_done_qty' % (step,): 0,
                                })
                            vals.update({
                                #'%s_prepare_qty' % (first_step,): need_qty + getattr(order_line,"%s_prepare_qty" % first_step,0)
                                '%s_prepare_qty' % (first_step,): need_qty + self.get_department_qty(first_step, 'prepare_qty', order_line),
                            })
                            drawing_order_line_obj.write(cr, uid, order_line_id, vals)
                            #Update part type to product
                            product_obj.write(cr, uid, [product_id],{'part_type': part_type})
                    row += 1
        if len(duplicate_parts):
            return self.pool.get('warning').info(cr, uid, title='Information', message=_(
                "Part %s has duplicate erp # or erp name!") % ",".join(duplicate_parts))
        return result

    # --- HoangTK - 11/17/2015
    @staticmethod
    def get_department_qty(department_code, quantity_type, line):
        result = 0
        quantity_vals = {}
        if department_code =='P':
            quantity_vals.update({department_code:
                                      {
                                          '%s_prepare_qty' % department_code: line.P_prepare_qty,
                                          '%s_done_qty' % department_code: line.P_done_qty,
                                          '%s_need_qty' % department_code: line.P_need_qty,
                                      }
                                  })
        elif department_code == 'Fc':
            quantity_vals.update({department_code:
                {
                    '%s_prepare_qty' % department_code: line.Fc_prepare_qty,
                    '%s_done_qty' % department_code: line.Fc_done_qty,
                    '%s_need_qty' % department_code: line.Fc_need_qty,
                }
            })
        elif department_code == 'B':
            quantity_vals.update({department_code:
                {
                    '%s_prepare_qty' % department_code: line.B_prepare_qty,
                    '%s_done_qty' % department_code: line.B_done_qty,
                    '%s_need_qty' % department_code: line.B_need_qty,
                }
            })
        elif department_code == 'Ma':
            quantity_vals.update({department_code:
                {
                    '%s_prepare_qty' % department_code: line.Ma_prepare_qty,
                    '%s_done_qty' % department_code: line.Ma_done_qty,
                    '%s_need_qty' % department_code: line.Ma_need_qty,
                }
            })
        elif department_code == 'D':
            quantity_vals.update({department_code:
                {
                    '%s_prepare_qty' % department_code: line.D_prepare_qty,
                    '%s_done_qty' % department_code: line.D_done_qty,
                    '%s_need_qty' % department_code: line.D_need_qty,
                }
            })
        elif department_code == 'Mi':
            quantity_vals.update({department_code:
                {
                    '%s_prepare_qty' % department_code: line.Mi_prepare_qty,
                    '%s_done_qty' % department_code: line.Mi_done_qty,
                    '%s_need_qty' % department_code: line.Mi_need_qty,
                }
            })
        elif department_code == 'W':
            quantity_vals.update({department_code:
                {
                    '%s_prepare_qty' % department_code: line.W_prepare_qty,
                    '%s_done_qty' % department_code: line.W_done_qty,
                    '%s_need_qty' % department_code: line.W_need_qty,
                }
            })
        elif department_code == 'A':
            quantity_vals.update({department_code:
                {
                    '%s_prepare_qty' % department_code: line.A_prepare_qty,
                    '%s_done_qty' % department_code: line.A_done_qty,
                    '%s_need_qty' % department_code: line.A_need_qty,
                }
            })

        elif department_code == 'Ct':
            quantity_vals.update({department_code:
                {
                    '%s_prepare_qty' % department_code: line.Ct_prepare_qty,
                    '%s_done_qty' % department_code: line.Ct_done_qty,
                    '%s_need_qty' % department_code: line.Ct_need_qty,
                }
            })
        elif department_code == 'Bt':
            quantity_vals.update({department_code:
                {
                    '%s_prepare_qty' % department_code: line.Bt_prepare_qty,
                    '%s_done_qty' % department_code: line.Bt_done_qty,
                    '%s_need_qty' % department_code: line.Bt_need_qty,
                }
            })
        elif department_code == 'Ps':
            quantity_vals.update({department_code:
                {
                    '%s_prepare_qty' % department_code: line.Ps_prepare_qty,
                    '%s_done_qty' % department_code: line.Ps_done_qty,
                    '%s_need_qty' % department_code: line.Ps_need_qty,
                }
            })
        elif department_code == 'G':
            quantity_vals.update({department_code:
                {
                    '%s_prepare_qty' % department_code: line.G_prepare_qty,
                    '%s_done_qty' % department_code: line.G_done_qty,
                    '%s_need_qty' % department_code: line.G_need_qty,
                }
            })
        elif department_code == 'K':
            quantity_vals.update({department_code:
                {
                    '%s_prepare_qty' % department_code: line.K_prepare_qty,
                    '%s_done_qty' % department_code: line.K_done_qty,
                    '%s_need_qty' % department_code: line.K_need_qty,
                }
            })
        elif department_code == 'Ht':
            quantity_vals.update({department_code:
                {
                    '%s_prepare_qty' % department_code: line.Ht_prepare_qty,
                    '%s_done_qty' % department_code: line.Ht_done_qty,
                    '%s_need_qty' % department_code: line.Ht_need_qty,
                }
            })
        elif department_code == 'Wa':
            quantity_vals.update({department_code:
                {
                    '%s_prepare_qty' % department_code: line.Wa_prepare_qty,
                    '%s_done_qty' % department_code: line.Wa_done_qty,
                    '%s_need_qty' % department_code: line.Wa_need_qty,
                }
            })
        if department_code in quantity_vals:
            result = quantity_vals[department_code]['%s_%s'% (department_code,quantity_type)]
        return result

    # +++ HoangTK - 12/08/2015: Override write method to update drawing order quantity

    def update_qty(self, cr, uid, ids):
        for order in self.browse(cr, uid, ids):
            prepare_qty = 0
            done_qty = 0
            need_qty = 0
            for order_line in order.order_lines:
                #prepare_qty += getattr(order_line, "%s_prepare_qty" % order_line.last_step, 0)
                #done_qty += getattr(order_line, "%s_done_qty" % order_line.last_step, 0)
                #need_qty += getattr(order_line, "%s_need_qty" % order_line.last_step, 0)
                prepare_qty += self.get_department_qty(order_line.last_step,'prepare_qty',order_line)
                done_qty += self.get_department_qty(order_line.last_step, 'done_qty', order_line)
                need_qty += self.get_department_qty(order_line.last_step, 'need_qty', order_line)

            super(drawing_order, self).write(cr, uid, [order.id], {
                'prepare_qty': prepare_qty,
                'need_qty': need_qty,
                'done_qty': done_qty
            })

    def _generate_name(self, cr, uid, ids, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            #mo_id = order.mo_id
            product_id = order.product_id
            #if mo_id and product_id:
            if product_id:
                name = product_id.name
                #mfg_ids = []
                #for mfg_id in mo_id.mfg_ids:
                #    mfg_ids.append("ID" + str(mfg_id.name))
                #mfg_name = "_".join(mfg_ids)
                #if mfg_name:
                #    name += "-" + mfg_name
                super(drawing_order, self).write(cr, uid, [order.id], {'name': name})

    def create(self, cr, uid, vals, context=None):
        result = super(drawing_order, self).create(cr, uid, vals, context)
        order_history_obj = self.pool.get('drawing.order.history')
        if result:
            self._generate_name(cr, uid, [result], context=context)
            if vals.get('bom_file',False):
               vals['bom_file'] = '**BOM FILE CONTENT**'
            order_history_obj.create(cr, uid, {
                'drawing_order_id': result,
                'user_id': uid,
                'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'content': _('Create Drawing Order'),
                #'vals': '%s' % vals,
            })
        if vals.get('bom_file',False):
            error_logs = self.check_bom_file_and_drawing(cr, uid, [result])
        return result

    def write(self, cr, uid, ids, vals, context=None):
        if not type(ids) is list:
            ids = [ids]
        result = super(drawing_order, self).write(cr, uid, ids, vals, context=context)
        #if vals.get('mo_id',False) or vals.get('product_id',False):
        #    self._generate_name(cr, uid, ids, context=context)
        #self.update_qty(cr, uid, ids)
        order_history_obj = self.pool.get('drawing.order.history')
        order_line_obj = self.pool.get('drawing.order.line')
        if vals.get('bom_file', False):
            error_logs = self.check_bom_file_and_drawing(cr, uid, ids)
        for order_id in ids:
            if vals.get('bom_file', False):
                vals['bom_file'] = '**BOM FILE CONTENT**'
                order = self.browse(cr, uid, order_id)
                if order.state == 'draft':
                    super(drawing_order, self).write(cr, uid, [order_id], {
                        'state': 'bom_uploaded'
                    })
                elif order.state == 'bom_uploaded' and order.bom_file == False:
                    super(drawing_order, self).write(cr, uid, [order_id], {
                        'state': 'draft'
                    })
                if len(error_logs) == 0 and len(order.order_lines) == 0:
                    super(drawing_order, self).write(cr, uid, [order_id], {
                        'notice': _('BOM Successfully uploaded. Please generate parts lines to continue')
                    })
                else:
                    super(drawing_order, self).write(cr, uid, [order_id], {
                        'notice': ''
                    })
            order_history_obj.create(cr, uid, {
                'drawing_order_id': order_id,
                'user_id': uid,
                'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'content': _('Update Drawing Order'),
                'vals': '%s' % vals,
            })

        if vals.get('mo_id',False):
            self.update_do_line_quantity(cr, uid, ids)
        return result

    def get_missing_erpno_parts(self, cr, uid, bom_file_content):
        missing_parts = []
        if bom_file_content:
            inputStr = StringIO.StringIO()
            inputStr.write(bom_file_content.decode('base64'))
            workbook = xlrd.open_workbook(file_contents=inputStr.getvalue())
            worksheet = workbook.sheet_by_index(0)
            row = 2
            while row < worksheet.nrows:
                bom_line = self.read_bom_line(worksheet=worksheet, row=row)
                if bom_line['part_name']:
                    if bom_line['part_type'] not in ['ASM','PMS','CD']:
                        if not bom_line['erp_no']:
                            missing_parts.append(bom_line)
                row += 1
        return missing_parts

    def update_missing_erpno(self, cr, uid, ids, context=None):
        missing_erpno_obj = self.pool.get('missing.erpno')
        missing_erpno_line_obj = self.pool.get('missing.erpno.line')
        part_names = []
        for order in self.browse(cr, uid, ids):
            if order.bom_file:
                missing_erpno_parts = self.get_missing_erpno_parts(cr, uid, order.bom_file)
                if len(missing_erpno_parts) > 0:
                    bom_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xls')
                    bom_file_name = bom_file.name
                    bom_file.close()
                    bom_file = open(bom_file_name, "wb+")
                    bom_file.write(order.bom_file.decode('base64'))
                    bom_file.close()
                    #inputStr = StringIO.StringIO()
                    #inputStr.write(order.bom_file.decode('base64'))
                    workbook = xlrd.open_workbook(bom_file_name)
                    new_workbook = copy(workbook)
                    worksheet = workbook.sheet_by_index(0)
                    new_worksheet = new_workbook.get_sheet(0)
                    row = 2
                    while row < worksheet.nrows:
                        bom_line = self.read_bom_line(worksheet=worksheet, row=row)
                        if bom_line['part_name']:
                            if bom_line['part_type'] not in ['ASM', 'PMS','CD']:
                                if not bom_line['erp_no']:
                                    missing_ids = missing_erpno_obj.search(cr, uid, [('order_id','=',order.id)])
                                    missing_line_ids = missing_erpno_line_obj.search(cr, uid, [
                                        ('missing_id', 'in', missing_ids),
                                        ('item_no','=',bom_line['item_no']),
                                        ('name','=',bom_line['part_name']),
                                        ('product_id','!=',False)
                                    ])
                                    if missing_line_ids:
                                        missing_line = missing_erpno_line_obj.browse(cr, uid, missing_line_ids[0])
                                        if missing_line.erp_no:
                                            new_worksheet.write(row,3,missing_line.erp_no)
                                            part_names.append(bom_line['part_name'])
                        row += 1
                    new_bom_file = tempfile.NamedTemporaryFile(delete=False,suffix='.xls')
                    new_bom_file_name = new_bom_file.name
                    new_bom_file.close()
                    new_workbook.save(new_bom_file_name)
                    new_file = open(new_bom_file_name,"rb")
                    self.write(cr, uid, [order.id],{
                        'bom_file': base64.b64encode(new_file.read()),
                        'bom_file_name': order.name + '.xls',
                    })
                    new_file.close()
        if len(part_names):
            return self.pool.get('warning').info(cr, uid, title='Information', message=_(
                "Part %s has been updated erp # to bom file!")%",".join(part_names))
        return True

    def create_missing_erpno(self, cr, uid, ids, context=None):
        missing_erpno_obj = self.pool.get('missing.erpno')
        missing_erpno_line_obj = self.pool.get('missing.erpno.line')
        have_missing_erpno = False
        for order in self.browse(cr, uid, ids):
            missing_erpno_parts = self.get_missing_erpno_parts(cr, uid, order.bom_file)
            if len(missing_erpno_parts) > 0:
                have_missing_erpno = True
                missing_id = missing_erpno_obj.create(cr, uid, {'order_id': order.id})
                for part in missing_erpno_parts:
                    missing_erpno_line_obj.create(cr, uid, {
                        'missing_id': missing_id,
                        'item_no': part['item_no'],
                        'name': part['part_name'],
                        'description': part['description'],
                    })
        if have_missing_erpno:
            return self.pool.get('warning').info(cr, uid, title='Information', message=_(
                "Missing erp no parts are created!"))
        return self.pool.get('warning').info(cr, uid, title='Information', message=_(
                "Dont have any missing erp no parts to create!"))
    #--- HoangTK - 12/08/2015: Override write method to update drawing order quantity

    def print_pms_xls(self, cr, uid, ids, context=None):
        if not type(ids) is list:
            ids = [ids]
        if len(ids) == 0:
            if context.get('active_model', False) == 'drawing.order':
                if context.get('active_ids', False):
                    ids = context.get('active_ids')
                elif context.get('active_id', False):
                    ids = [context.get('active_id')]
        order_line_ids = []
        for id in ids:
            order = self.read(cr, uid, id, ['name', 'order_lines'], context=context)
            if len(ids) == 1 and context.get('order_name', False) == False:
                context['order_name'] = order['name']
            order_line_ids += order['order_lines']

        return self.pool.get('drawing.order.line').print_pms_xls(cr, uid, order_line_ids, context=context)

    def print_pdf_zip(self, cr, uid, ids, context=None):
        if not type(ids) is list:
            ids = [ids]
        if len(ids) == 0:
            if context.get('active_model', False) == 'drawing.order':
                if context.get('active_ids', False):
                    ids = context.get('active_ids')
                elif context.get('active_id', False):
                    ids = [context.get('active_id')]
        order_line_ids = []
        for id in ids:
            order = self.read(cr, uid, id, ['name', 'order_lines'], context=context)
            if len(ids) == 1 and context.get('order_name', False) == False:
                context['order_name'] = order['name']
            order_line_ids += order['order_lines']
        return self.pool.get('drawing.order.line').print_pdf_zip(cr, uid, order_line_ids, context=context)

    def print_pdf_pdftk(self, cr, uid, ids, context=None):
        if not type(ids) is list:
            ids = [ids]
        if len(ids) == 0:
            if context.get('active_model', False) == 'drawing.order':
                if context.get('active_ids', False):
                    ids = context.get('active_ids')
                elif context.get('active_id', False):
                    ids = [context.get('active_id')]
        order_line_ids = []
        for id in ids:
            order = self.read(cr, uid, id, ['name', 'order_lines'], context=context)
            if len(ids) == 1:
                context['order_name'] = order['name']
            order_line_ids += order['order_lines']

        return self.pool.get('drawing.order.line').print_pdf_pdftk(cr, uid, order_line_ids, context=context)

    def print_pdf(self, cr, uid, ids, context=None):
        if not type(ids) is list:
            ids = [ids]
        if len(ids) == 0:
            if context.get('active_model', False) == 'drawing.order':
                if context.get('active_ids', False):
                    ids = context.get('active_ids')
                elif context.get('active_id', False):
                    ids = [context.get('active_id')]
        order_line_ids = []
        for id in ids:
            order = self.read(cr, uid, id, ['name', 'order_lines'], context=context)
            if len(ids) == 1:
                context['order_name'] = order['name']
            order_line_ids += order['order_lines']

        return self.pool.get('drawing.order.line').print_pdf(cr, uid, order_line_ids, context=context)

    def print_dxf(self, cr, uid, ids, context=None):
        if not type(ids) is list:
            ids = [ids]
        if len(ids) == 0:
            if context.get('active_model', False) == 'drawing.order':
                if context.get('active_ids', False):
                    ids = context.get('active_ids')
                elif context.get('active_id', False):
                    ids = [context.get('active_id')]
        order_line_ids = []
        for id in ids:
            order = self.read(cr, uid, id, ['name', 'order_lines'], context=context)
            if len(ids) == 1:
                context['order_name'] = order['name']
            order_line_ids += order['order_lines']

        return self.pool.get('drawing.order.line').print_dxf(cr, uid, order_line_ids, context=context)

    def print_bom_xls(self, cr, uid, ids, context=None):
        if not ids:
            raise osv.except_osv(_("Error!"), _('No BOM lines were found!'))
        if not type(ids) is list:
            ids = [ids]
        if ids:
            drawing_order_obj = self.pool.get('drawing.order')
            workbook = xlwt.Workbook()
            file_name = False
            if context.get('order_name'):
                file_name = u'%s.xls' % (utils._format_file_name(context.get('order_name')))
            for order in drawing_order_obj.browse(cr, uid, ids, context=context):
                if not file_name:
                    file_name = '%s.xls'%(utils._format_file_name(order.name))
                cr.execute("SELECT item_no,erp_no,part_number,description,bom_qty,standard,part_type,material,thickness,quantity,work_steps "\
                           "from drawing_order_line l WHERE l.order_id = %s "\
                           "order by l.item_no asc", (order.id,))
                result = cr.dictfetchall()
                sequence = 0
                sheet = workbook.add_sheet("DO#%s"% order.id)
                sheet.write(0, 0,'%s'%order.name)
                sheet.write(1, 0, 'ITEM NO')
                sheet.write(1, 1, 'PART NUMBER')
                sheet.write(1, 2, 'DESCRIPTION')
                sheet.write(1, 3, 'ERP#')
                sheet.write(1, 4, 'STANDARD')
                sheet.write(1, 5, 'MATERIAL')
                sheet.write(1, 6, 'THICKNESS/LENGTH')
                sheet.write(1, 7, 'DEPARTMENTS')
                sheet.write(1, 8, 'PART TYPE')
                sheet.write(1, 9, 'QTY FOR 1 UNIT')
                sheet.write(1, 10, 'TOTAL QTY')
                sheet.write(1, 11, 'NOTES')
                row = 2
                for r in result:
                    sequence += 1
                    sheet.write(row, 0, r['item_no'])
                    sheet.write(row, 1, r['part_number'])
                    sheet.write(row, 2, r['description'])
                    sheet.write(row, 3, r['erp_no'])
                    sheet.write(row, 4, r['standard'])
                    sheet.write(row, 5, r['material'])
                    sheet.write(row, 6, r['thickness'])
                    sheet.write(row, 7, r['work_steps'])
                    sheet.write(row, 8, r['part_type'])
                    sheet.write(row, 9, r['bom_qty'])
                    row += 1

            if file_name:
                temp_xls_file = tempfile.NamedTemporaryFile(delete=False,suffix='.xls')
                temp_xls_file_name = temp_xls_file.name
                temp_xls_file.close()
                workbook.save(temp_xls_file_name)
                return {
                    'type': 'ir.actions.act_url',
                    'url': '/web/export/drawing_order_print_pdf?file_name=%s&file_data=%s' % (
                        file_name, temp_xls_file_name),
                    'target': 'self',
                }
        raise osv.except_osv(_("Error!"), _('No BOM lines were found!'))

    def update_do_line_quantity(self, cr, uid, order_ids, context=None):
        for order in self.browse(cr, uid, order_ids,context=context):
            mo_quantity = self.get_big_subassembly_qty(cr, uid, order)
            cr.execute('update drawing_order_line set quantity = bom_qty * %s ' \
                       'where order_id = %s' % (mo_quantity, order.id))

            cr.execute("SELECT id,last_step from drawing_order_line where last_step is not null and order_id = %s" % (order.id,))
            result = cr.dictfetchall()
            for r in result:
                cr.execute('update drawing_order_line ' \
                           'set "%s_prepare_qty" = bom_qty * %s, ' \
                           '"%s_need_qty" = bom_qty * %s ' \
                           'where id = %s' % (
                               r['last_step'], mo_quantity,
                               r['last_step'], mo_quantity, r['id']))

        order_quantities = self._get_do_quantity(cr, uid, order_ids)
        asm_qty = self._get_produced_type_qty(cr, uid, order_ids)
        purchs_qty = self._get_purchs_type_qty(cr, uid, order_ids)
        purchoem_qty = self._get_purchoem_type_qty(cr, uid, order_ids)
        purchm_qty = self._get_purchm_type_qty(cr, uid, order_ids)
        purchmc_qty = self._get_purchmc_type_qty(cr, uid, order_ids)
        purchms_qty = self._get_purchms_type_qty(cr, uid, order_ids)
        purchml_qty = self._get_purchml_type_qty(cr, uid, order_ids)
        purchcd_qty = self._get_purchcd_type_qty(cr, uid, order_ids)
        for order_id in order_ids:
            cr.execute('update drawing_order set ' \
                       'prepare_qty = %s, ' \
                       'done_qty = %s, ' \
                       'need_qty = %s, ' \
                       'produced_type_qty = %s, ' \
                       'purchs_type_qty = %s, ' \
                       'purchoem_type_qty = %s, ' \
                       'purchm_type_qty = %s, ' \
                       'purchmc_type_qty = %s, ' \
                       'purchms_type_qty = %s, ' \
                       'purchml_type_qty = %s, ' \
                       'purchcd_type_qty = %s ' \
                       'where id=%s' % (
                           order_quantities[order_id]['prepare_qty'],
                           order_quantities[order_id]['done_qty'],
                           order_quantities[order_id]['need_qty'],
                           asm_qty[order_id],
                           purchs_qty[order_id],
                           purchoem_qty[order_id],
                           purchm_qty[order_id],
                           purchmc_qty[order_id],
                           purchms_qty[order_id],
                           purchml_qty[order_id],
                           purchcd_qty[order_id],
                           order_id))

    def link_cnc_workorder(self, cr, uid, ids, context=None):
        if context is None:
            context= {}
        return {
            'name': 'Link CNC Work Order',
            'res_model': 'do.link.cnc.workorder.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def onchange_mo_id_product_id(self, cr, uid, ids, mo_id, product_id, context=None):
        vals = {}
        if mo_id:
            mo = self.pool.get('mrp.production').browse(cr, uid, mo_id)
            vals.update({'mo_bigsubassembly_ids': self._get_product_ids_from_mo(cr, uid, mo),
                         'main_part_id': mo.product_id.id})

        if mo_id and product_id:
            duplicate_do_ids = self.search(cr, uid, [
                ('mo_id','=',mo_id),
                ('product_id','=',product_id),
                ('state','not in',['rejected','cancel'])
            ])
            if len(duplicate_do_ids) > 1:
                return self.pool.get('warning').info(cr, uid, title='Warning', message=_("There is another DO with the same MO and Big Subassembly, consider to revise it!"))
        return {'value': vals}

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if view_type == 'form' and not view_id:
            view_name = 'view_drawing_order_form'
            view_obj = self.pool.get('ir.ui.view')
            view_ids = view_obj.search(cr, uid, [('name', '=', view_name)])
            if view_ids:
                view = view_obj.browse(cr, uid, view_ids[0])
                department_obj = self.pool.get('hr.department')
                department_ids = department_obj.search(cr, uid, [('code', 'in', WORK_STEP_LIST)], order='sequence asc')
                departments = department_obj.browse(cr, uid, department_ids)
                work_step_fields = ''
                for department in departments:
                    work_step_fields = work_step_fields + \
                                       "<field name='%s_prepare_qty' attrs=\"{'invisible':[('%s_prepare_qty', '==', 0)]}\" readonly='1'/> \
                                       <field name='%s_done_qty' attrs=\"{'invisible':[('%s_done_qty', '==', 0)]}\" readonly='1'/> \
                                       <field name='%s_need_qty' attrs=\"{'invisible':[('%s_need_qty', '==', 0)]}\" readonly='1'/>" % (
                                       department.code, department.code, department.code, department.code,
                                       department.code, department.code)
                arch_parts = view.arch.split('<!--DYNAMIC WORKSTEPS DO NOT DELETE-->')
                if len(arch_parts) == 3:
                    view_arch = arch_parts[0] + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                                work_step_fields + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                                arch_parts[2]
                    view_obj.write(cr, SUPERUSER_ID, [view_ids[0]], {
                        'arch': view_arch
                    })
        res = super(drawing_order, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        return res


class drawing_step(osv.osv):
    _name = "drawing.step"
    _description = "Drawing Step"
    _columns = {
        'name': fields.char('Name', size=32),
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Name must be unique!'),
    ]


class drawing_order_line(osv.osv):
    _name = "drawing.order.line"
    _description = "Drawing Order Line"
    #_rec_name = "drawing_file_name"
    # +++ HoangTK - 11/06/2015: Order by Drawing PDF Name asc
    _order = "item_no asc"

    def generate_pr(self, cr, uid, ids, context):
        mod_obj = self.pool.get('ir.model.data')
        res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'view_generate_pr_wizard')
        res_id = res and res[1] or False
        mfg_o = context and context.get('mfg_o', False) or False
        return {
            'name': 'Purchase Requisition Generator',
            'res_model': 'generate.pr.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'context': {'drawing_order_line_ids': ids, 'mfg_o': mfg_o},
            'target': 'new'
        }

    # --- HoangTK
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if view_type == 'form' and not view_id:
            view_name = 'view_drawing_order_line_form'
            view_obj = self.pool.get('ir.ui.view')
            view_ids = view_obj.search(cr, uid, [('name', '=', view_name)])
            if view_ids:
                view = view_obj.browse(cr, uid, view_ids[0])
                department_obj = self.pool.get('hr.department')
                department_ids = department_obj.search(cr, uid, [('code', 'in', WORK_STEP_LIST)], order='sequence asc')
                departments = department_obj.browse(cr, uid, department_ids)
                work_step_fields = '<group colspan="4" col="%s">'% (len(departments)*6)
                for department in departments:
                    work_step_fields = work_step_fields + \
                                       "<label string='%s P' colspan='2' class='metro_header_label'/> \
                                       <label string='%s D' colspan='2' class='metro_header_label'/> \
                                       <label string='%s N' colspan='2' class='metro_header_label'/>" % (
                                       department.code, department.code, department.code)
                for department in departments:
                    work_step_fields = work_step_fields + \
                                       "<field name='%s_prepare_qty' nolabel='1' colspan='2'/> \
                                       <field name='%s_done_qty' nolabel='1' colspan='2'/> \
                                       <field name='%s_need_qty' nolabel='1' colspan='2'/>" % (
                                       department.code, department.code, department.code)
                work_step_fields = work_step_fields + '</group>'
                arch_parts = view.arch.split('<!--DYNAMIC WORKSTEPS DO NOT DELETE-->')
                if len(arch_parts) == 3:
                    view_arch = arch_parts[0] + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                                work_step_fields + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                                arch_parts[2]
                    view_obj.write(cr, SUPERUSER_ID, [view_ids[0]], {
                        'arch': view_arch
                    })
        res = super(drawing_order_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        return res

    def _compute_pdf_dxf_valid(self, cr, uid, ids, field_names, args=None, context=None):
        if not field_names:
            field_names = []
        if context is None:
            context = {}
        res = {}
        for id in ids:
            res[id] = {}.fromkeys(field_names, False)
        order_lines = self.read(cr, uid, ids, ['id', 'dxf_file_name', 'drawing_file_name'], context=context)
        for line in order_lines:
            pdf_valid = False
            dxf_valid = False
            color = 'black'
            if not line['dxf_file_name']:
                dxf_valid = True
            else:
                file_ids = self.get_order_line_dxf_ids(cr, uid, line['id'], line['dxf_file_name'], context=context)
                if file_ids:
                    dxf_valid = True
            if not line['drawing_file_name']:
                pdf_valid = True
            else:
                file_ids = self.get_order_line_pdf_ids(cr, uid, line['id'], line['drawing_file_name'], context=context)
                if file_ids:
                    pdf_valid = True
            if not pdf_valid:
                color = 'red'
            elif not dxf_valid:
                color = 'maroon'
            res[line['id']]['color'] = color
            res[line['id']]['pdf_valid'] = pdf_valid
            res[line['id']]['dxf_valid'] = dxf_valid
        return res

    def _have_original_drawing_search(self, cr, uid, obj, field_name, args, context=None):
        '''
        the original 'is set'/'is not set' searching options
        @param args: [(u'original_drawing', u'=', False)]  or [(u'original_drawing', u'!=', False)]
        '''
        if not args or args[0][2]:
            return []

        # get line with original drawing
        cr.execute("select distinct res_id from ir_attachment \
                        where res_model = 'drawing.order.line' \
                        and name = 'original_drawing' and file_size > 0 and store_fname != NULL")
        res = cr.fetchall()
        # fetchall: [(251,), (2026,), (2409,)]
        # dictfetchall:[{'res_id': 251}, {'res_id': 2026}]
        have_file_ids = []
        if res:
            have_file_ids = [line_id for line_id, in res]

        # [(u'original_drawing', u'=', False)] , the line without original drawing
        if args[0][1] == '=':
            if have_file_ids:
                return [('id', 'not in', have_file_ids)]
            else:
                return []
        # [(u'original_drawing', u'!=', False)], the line with original drawing
        if args[0][1] == '!=':
            if have_file_ids:
                return [('id', 'in', have_file_ids)]
            else:
                # no line with original pdf
                return [('id', '<', 0)]
        return []

    _columns = {
        'order_id': fields.many2one('drawing.order', 'Drawing Order'),
        'color': fields.function(_compute_pdf_dxf_valid, multi='pdf_dxf_valid', type='char', size=50, string='Color', readonly=True,
                                 # store={
                                 #     'drawing.order.line': (lambda self, cr, uid, ids, context=None: ids,
                                 #                            ['product_id', 'drawing_file_name', 'drawing_file',
                                 #                             'dxf_file_name', 'dxf_file'], 10)
                                 # }
                                 ),
        # +++ HoangTK - 11/17/2015: Change name to Part
        # 'product_id': fields.many2one('product.product','Sub Product'),
        'product_id': fields.many2one('product.product', 'ERP Part'),
        # --- HoangTK - 11/17/2015
        'drawing_file_name': fields.char('Drawing PDF Name', size=128),
        'drawing_file': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file,
                                        string="Drawing PDF",
                                        type="binary", multi="_get_file", ),
        'dxf_file_name': fields.char('Drawing PDF Name', size=128),
        'dxf_file': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file,
                                    string="Drawing DXF",
                                        type="binary", multi="_get_file", ),
        'pdf_valid': fields.function(_compute_pdf_dxf_valid, multi='pdf_dxf_valid', string='Valid Pdf?',type="boolean", readonly=True,
                             # store={
                             #     'drawing.order.line': (lambda self, cr, uid, ids, context=None: ids,
                             #                            ['product_id', 'drawing_file_name', 'drawing_file',
                             #                             'dxf_file_name', 'dxf_file'], 10)
                             # }
                                     ),
        'dxf_valid': fields.function(_compute_pdf_dxf_valid, multi='pdf_dxf_valid', string='Valid Dxf?', type="boolean", readonly=True,
                             # store={
                             #     'drawing.order.line': (lambda self, cr, uid, ids, context=None: ids,
                             #                            ['product_id', 'drawing_file_name', 'drawing_file',
                             #                             'dxf_file_name', 'dxf_file'], 10)
                             # }
                                     ),
        # HoangTK - Drawing Download field is used to display link to download drawing
        # it will fix the overload on Openerp when it will keep read whole the binary if display drawing_file
        'drawing_download': fields.char('Drawing PDF', size=128, readonly=True),
        'dxf_download': fields.char('Drawing DXF', size=128, readonly=True),
        'original_drawing_file': fields.binary('Original File'),
        'original_drawing': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file,
                                        fnct_search=_have_original_drawing_search,
                                        string="Original Drawing PDF",
                                        type="binary", multi="_get_file", ),
        'moved_original_drawing': fields.boolean('Moved Original Drawing to File?'),
        'step_ids': fields.many2many('drawing.step', string='Working Steps'),
        'company_id': fields.related('order_id', 'company_id', type='many2one', relation='res.company',
                                     string='Company'),
        'create_uid': fields.many2one('res.users', 'Creator', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True),
        'state': fields.selection(
            [('draft', 'Draft'), ('ready', 'Ready'), ('confirmed', 'Confirmed'), ('approved', 'Approved'),
             ('rejected', 'Rejected'), ('cancel', 'Cancelled')], 'Status', required=True, readonly=True),
        # order fields to show in the drawing files view
        'sale_product_ids': fields.related('order_id', 'sale_product_ids', type='many2many', relation='sale.product',
                                           rel='drawing_order_id_rel', id1='drawing_order_id', id2='id_id',
                                           string="MFG IDs", readonly=True,
                                           states={'draft': [('readonly', False)], 'rejected': [('readonly', False)]}),
        'main_part_id': fields.related('order_id', 'main_part_id', type='many2one', relation='product.product',
                                       string='Unit'),
        # +++ HoangTK - 11/17/2015: Add quantity and work steps to drawing order lines
        'name': fields.related('product_id', 'name', string="Name", type="char", readonly=True),
        'part_number': fields.char('Part Number',size=128,readonly=True),
        'bom_qty': fields.integer('BOM Qty', readonly=True),
        'quantity': fields.integer('Quantity',readonly=True),
        'Wa_prepare_qty': fields.integer('Wa P', readonly=True),
        'Wa_done_qty': fields.integer('Wa D'),
        'Wa_need_qty': fields.integer('Wa N', readonly=True),
        'P_prepare_qty': fields.integer('P P', readonly=True),
        'P_done_qty': fields.integer('P D'),
        'P_need_qty': fields.integer('P N', readonly=True),
        'Fc_prepare_qty': fields.integer('Fc P', readonly=True),
        'Fc_done_qty': fields.integer('Fc D'),
        'Fc_need_qty': fields.integer('Fc N', readonly=True),
        'B_prepare_qty': fields.integer('B P', readonly=True),
        'B_done_qty': fields.integer('B D'),
        'B_need_qty': fields.integer('B N', readonly=True),
        'Ma_prepare_qty': fields.integer('Ma P', readonly=True),
        'Ma_done_qty': fields.integer('Ma D'),
        'Ma_need_qty': fields.integer('Ma N', readonly=True),
        'Ht_prepare_qty': fields.integer('Ht P', readonly=True),
        'Ht_done_qty': fields.integer('Ht D'),
        'Ht_need_qty': fields.integer('Ht N', readonly=True),
        'D_prepare_qty': fields.integer('D P', readonly=True),
        'D_done_qty': fields.integer('D D'),
        'D_need_qty': fields.integer('D N', readonly=True),
        'Mi_prepare_qty': fields.integer('Mi P', readonly=True),
        'Mi_done_qty': fields.integer('Mi D'),
        'Mi_need_qty': fields.integer('Mi N', readonly=True),
        'W_prepare_qty': fields.integer('W P', readonly=True),
        'W_done_qty': fields.integer('W D'),
        'W_need_qty': fields.integer('W N', readonly=True),
        'A_prepare_qty': fields.integer('A P', readonly=True),
        'A_done_qty': fields.integer('A D'),
        'A_need_qty': fields.integer('A N', readonly=True),
        'Ct_prepare_qty': fields.integer('Ct P', readonly=True),
        'Ct_done_qty': fields.integer('Ct D'),
        'Ct_need_qty': fields.integer('Ct N', readonly=True),
        'Bt_prepare_qty': fields.integer('Bt P', readonly=True),
        'Bt_done_qty': fields.integer('Bt D'),
        'Bt_need_qty': fields.integer('Bt N', readonly=True),
        'Ps_prepare_qty': fields.integer('Ps P', readonly=True),
        'Ps_done_qty': fields.integer('Ps D'),
        'Ps_need_qty': fields.integer('Ps N', readonly=True),
        'G_prepare_qty': fields.integer('G P', readonly=True),
        'G_done_qty': fields.integer('G D'),
        'G_need_qty': fields.integer('G N', readonly=True),
        'K_prepare_qty': fields.integer('K P', readonly=True),
        'K_done_qty': fields.integer('K D'),
        'K_need_qty': fields.integer('K N', readonly=True),
        'work_steps': fields.char('Work Steps', size=128, readonly=True),
        'last_step': fields.char('Last Step', size=128, readonly=True),
        'first_step': fields.char('Last Step', size=128, readonly=True),
        'status': fields.char('Status', size=50, readonly=True),
        'part_type': fields.selection(PART_TYPE_SELECTION, string='Part Type', readonly=True),
        'item_no': fields.char('Item No.', size=50, readonly=True),
        'description': fields.char('Description', size=128, readonly=True),
        'erp_no': fields.char('ERP #', size=128, readonly=True),
        'material': fields.char('Material', size=128, readonly=True),
        'standard': fields.char('Standard', size=128, readonly=True),
        'thickness': fields.char('Thickness', size=128, readonly=True),
        'is_pdf_fixed': fields.boolean('This pdf is fixed auto', readonly=True),
        'is_dxf_fixed': fields.boolean('This dxf is fixed auto', readonly=True),
        # --- HoangTK - 11/17/2015
    }

    _defaults = {
        'state': 'draft',
        'drawing_download': 'drawing_file',
        'dxf_download': 'dxf_file',
        'is_pdf_fixed': False,
        'is_dxf_fixed': False,
        'moved_original_drawing': False,
    }

    # @staticmethod
    # def _format_file_name(file_name):
    #     file_reserved_char = ('/', '\\', '<', '>', '*', '?','&')
    #     new_file_name = file_name
    #     for char in file_reserved_char:
    #         new_file_name = new_file_name.replace(char, '-')
    #     return new_file_name

    def _empty_orignal_drawing_file_field(self, cr, uid, ids=None, context=None):
        line_ids = self.search(cr, uid, [('original_drawing_file', '!=', False),
                                         ('moved_original_drawing', '=', True),
                                         ('original_drawing', '!=', False)
                                    ], context=context)
        for i in xrange(0, len(line_ids), CHUNK_SIZE):
            self.write(cr, uid, line_ids[i:i + CHUNK_SIZE], {'original_drawing_file': False,
                                                }, context=context)
        return True

    def _move_original_drawing_file_original_drawing(self, cr, uid, ids=None, context=None):
        line_ids = self.search(cr, uid, [('original_drawing_file', '!=', False)], context=context)
        for i in xrange(0, len(line_ids), CHUNK_SIZE):
            for line in self.browse(cr, uid, line_ids[i:i + CHUNK_SIZE], context=context):
                self.write(cr, uid, [line.id], {'original_drawing': line.original_drawing_file,
                                                'moved_original_drawing': True}, context=context)
        return True

    def _search_and_fix_do_attachments(self, cr, uid, ids=None, context=None):
        attachment_obj = self.pool.get('ir.attachment')
        if ids:
            line_ids = ids
        else:
            line_ids = self.search(cr, uid, [
                ('name','!=',False),
                ('product_id','!=',False),
                ('item_no','!=',False),
                '|',
                ('dxf_file_name', '!=', False),
                ('drawing_file_name', '!=', False),
            ])
        for line_id in line_ids:
            line = self.read(cr, uid, line_id, ["id","name",
                                                  "order_id",
                                                  "drawing_file_name",
                                                  "dxf_file_name",
                                                  "product_id",
                                                  "item_no",
                                                  "part_number",
                                                  "create_date"], context=context)
            need_fix_pdf = False
            need_fix_dxf = False
            if line["drawing_file_name"]:
                file_ids = self.get_order_line_pdf_ids(cr, uid, line["id"], line["drawing_file_name"])
                if not file_ids:
                    need_fix_pdf = True
                elif file_ids:
                    attach_file = attachment_obj.file_get(cr, uid, file_ids[0], context=context)
                    if not attach_file:
                        need_fix_pdf = True
            if line["dxf_file_name"]:
                file_ids = self.get_order_line_dxf_ids(cr, uid, line["id"], line["dxf_file_name"])
                if not file_ids:
                    need_fix_dxf = True
                elif file_ids:
                    attach_file = attachment_obj.file_get(cr, uid, file_ids[0], context=context)
                    if not attach_file:
                        need_fix_dxf = True
            if need_fix_pdf:
                origin_line_ids = self.search(cr, uid, [
                    ('id','!=',line["id"]),
                    #('item_no','=',line['item_no']),
                    ('state', 'in', ['ready', 'confirmed', 'approved']),
                    ('drawing_file_name','=',line['drawing_file_name']),
                    ('part_number','=',line["part_number"]),
                    ('product_id','=',line['product_id'][0])
                ], context=context)
                attachment_ids = attachment_obj.search(cr, uid, [
                    ('res_model','=','drawing.order.line'),
                    ('res_id','in',origin_line_ids),
                    ('store_fname','!=', False),
                    #('create_date','<=',line['create_date']),
                     '|','|',
                    ('name','=','drawing_file'),
                    ('name','=',line['drawing_file_name']),
                    ('res_name','=',line['drawing_file_name'])
                ], order='create_date desc', context=context)
                if attachment_ids:
                    attachment = attachment_obj.browse(cr, uid, attachment_ids[0], context=context)
                    origin_line = self.browse(cr, uid, attachment.res_id, context=context)
                    self.write(cr, uid, [line["id"]],{
                        'drawing_file': origin_line.drawing_file,
                        'is_pdf_fixed': True,
                    })
            if need_fix_dxf:
                origin_line_ids = self.search(cr, uid, [
                    ('id','!=',line["id"]),
                    #('item_no','=',line['item_no']),
                    ('dxf_file_name','=',line['dxf_file_name']),
                    ('part_number','=',line["part_number"]),
                    ('product_id','=',line['product_id'][0])
                ], context=context)
                attachment_ids = attachment_obj.search(cr, uid, [
                    ('res_model','=','drawing.order.line'),
                    ('res_id','in',origin_line_ids),
                    ('store_fname','!=', False),
                    #('create_date','<=',line['create_date']),
                    '|', '|',
                    ('name', '=', 'dxf_file'),
                    ('name', '=', line['dxf_file_name']),
                    ('res_name', '=', line['dxf_file_name']),
                ], order='create_date desc', context=context)
                if attachment_ids:
                    attachment = attachment_obj.browse(cr, uid, attachment_ids[0], context=context)
                    origin_line = self.browse(cr, uid, attachment.res_id, context=context)
                    self.write(cr, uid, [line["id"]],{
                        'dxf_file': origin_line.dxf_file,
                        'is_dxf_fixed': True,
                    })
        return True

    def get_order_line_dxf_ids(self,cr, uid, line_ids, dxf_file_name, context=None):
        if not type(line_ids) is list:
            line_ids = [line_ids]
        attachment_obj = self.pool.get('ir.attachment')
        file_ids = attachment_obj.search(
            cr, uid, ['|', '|', ('name', '=', 'dxf_file'),
                     ('name', '=', dxf_file_name),
                     ('res_name', '=', dxf_file_name),
                     ('res_id', 'in', line_ids),
                     ('res_model', '=', 'drawing.order.line'),
                      ('file_size', '>', 0),
                      ('store_fname', '!=', False),
                      ], order='create_date desc'

        )
        return file_ids

    def get_order_line_pdf_ids(self, cr, uid, line_ids, drawing_file_name, context=None):
        if not type(line_ids) is list:
            line_ids = [line_ids]
        attachment_obj = self.pool.get('ir.attachment')
        file_ids = attachment_obj.search(
            cr, uid,
            ['|', '|', ('name', '=', 'drawing_file'),
             ('name', '=', drawing_file_name),
             ('res_name', '=', drawing_file_name),
             ('res_id', 'in', line_ids),
             ('res_model', '=', 'drawing.order.line'),
             ('file_size', '>', 0),
             ('store_fname', '!=', False),
             ], order='create_date desc'
        )
        return file_ids

    def _add_watermark(self, cr, uid, ids, context=None):
        attachment_obj = self.pool.get('ir.attachment')
        #lines = self.browse(cr, uid, ids, context=context)
        user = self.pool.get('res.users').browse(cr, uid, uid)
        user_signature_file_name = False
        if user.company_id.stamp and len(ids) > 0:
            watermark_file = tempfile.NamedTemporaryFile(delete=False)
            watermark_file_name = watermark_file.name
            watermark_file.close()
            outputStr = file(watermark_file_name, "wb")
            outputStr.write(user.company_id.stamp.decode('base64'))
            outputStr.close()
            if user.signature_image:
                user_signature_file = tempfile.NamedTemporaryFile(delete=False)
                user_signature_file_name = user_signature_file.name
                user_signature_file.close()
                outputStr = file(user_signature_file_name, "wb")
                outputStr.write(user.signature_image.decode('base64'))
                outputStr.close()
            old_width = 0
            old_height = 0
            old_confirm_date = False
            imgTemp = False
            #for line in lines:
            cr.execute("select l.order_id, l.id, o.state, l.drawing_file_name, o.confirm_date "\
                        "from drawing_order_line l "\
                        "left join drawing_order o on l.order_id = o.id "\
                        "where l.id IN %s", (tuple(ids),))
            result = cr.dictfetchall()
            for r in result:
                drawing_file_name = r['drawing_file_name']
                state = r['state']
                line_id = r['id']
                order_id = r['order_id']
                confirm_date = r['confirm_date']
                #if line.drawing_file_name and line.drawing_file_name.lower().endswith('.pdf') \
                #        and line.order_id.state in ['ready','confirmed', 'approved'] :
                if drawing_file_name and drawing_file_name.lower().endswith('.pdf') \
                    and state in ['ready','confirmed', 'approved'] :
                    # file_ids = attachment_obj.search(
                    #     cr, uid, [  # ('name', '=', 'drawing_file'),
                    #         #('res_id', '=', line.id),
                    #         ('res_id', '=', line_id),
                    #         ('res_model', '=', 'drawing.order.line')])
                    file_ids = self.get_order_line_pdf_ids(cr, uid, line_id, drawing_file_name, context=context)
                    if file_ids:
                        output = PdfFileWriter()
                        attach_file = attachment_obj.file_get(cr, uid, file_ids[0], context=context)
                        pages = []
                        try:
                            input = PdfFileReader(attach_file, strict=False)
                            pages = input.pages
                            # Test if error access page
                            for page in pages:
                                test=1
                                break
                        except:
                            raise osv.except_osv(_("Error!"), _('Can not read pdf of part %s!') % (drawing_file_name))
                        page_cnt = 0
                        for page in pages:
                            pageBox = page.mediaBox
                            width = pageBox.getLowerRight_x()
                            height = pageBox.getUpperRight_y()
                            #confirm_date = line.order_id.confirm_date
                            if width != old_width or height != old_height or confirm_date != old_confirm_date:
                                old_height = height
                                old_width = width
                                old_confirm_date = confirm_date
                                if imgTemp:
                                    imgTemp.close()
                                imgTemp = StringIO.StringIO()
                                imgDoc = canvas.Canvas(imgTemp)
                                imgDoc.setPageSize((width,
                                                    height))
                                # Draw image on Canvas and save PDF in buffer
                                imgDoc.drawImage(watermark_file_name,
                                                 float(width) - 200,
                                                 170,
                                                 110, 110, mask='auto')
                                if user_signature_file_name:
                                    imgDoc.drawImage(user_signature_file_name,
                                                     float(width) - 175,
                                                     210,
                                                     52, 25, mask='auto')
                                if confirm_date:
                                    #imgDoc.drawString(float(width) - 175, 200, line.order_id.confirm_date)
                                    #imgDoc.setStrokeColorRGB(1, 1, 1)
                                    #imgDoc.setFillColorRGB(1, 1, 1)
                                    #imgDoc.rect(float(width) - 175, 200, stringWidth(confirm_date), 20, fill=1)
                                    #imgDoc.setFillColorRGB(0, 0, 0)
                                    imgDoc.drawString(float(width) - 175, 200, confirm_date)
                                # TODO: Add drawing order name on the top left position
                                imgDoc.drawString(20, float(height)-20, 'DO%s' % order_id)
                                imgDoc.save()

                            if imgTemp:
                                # Use PyPDF to merge the image-PDF into the template
                                watermark_pdf = PdfFileReader(StringIO.StringIO(imgTemp.getvalue()), strict=False)
                                watermark_page = watermark_pdf.getPage(0)
                                try:
                                    page.mergePage(watermark_page)
                                except:
                                    raise osv.except_osv(_("Error!"), _('Can not add watermark to page %s of part %s!')%(page_cnt+1,drawing_file_name))

                            output.addPage(page)
                            page_cnt += 1
                        if page_cnt > 0:
                            temp_drawing_pdf_file = tempfile.NamedTemporaryFile(delete=False)
                            temp_drawing_pdf_file_name = temp_drawing_pdf_file.name
                            temp_drawing_pdf_file.close()
                            outputStream = file(temp_drawing_pdf_file_name, "wb")
                            output.write(outputStream)
                            outputStream.close()
                            inputStr = file(temp_drawing_pdf_file_name,'rb')
                            watermark_data = inputStr.read()
                            #super(drawing_order_line, self).write(cr, uid, [line.id],{
                            #    'original_drawing': line.drawing_file,
                            #})
                            attachment_obj.write(cr, uid, [file_ids[0]],{'datas': base64.encodestring(watermark_data)})
                            inputStr.close()
            if imgTemp:
                imgTemp.close()
        return True

    def print_pms_xls(self, cr, uid, ids, context):
        if not ids:
            raise osv.except_osv(_("Error!"), _('No PMS parts were found!'))
        if not type(ids) is list:
            ids = [ids]
        if len(ids) == 0:
            if context.get('active_model', False) == 'drawing.order.line':
                if context.get('active_ids', False):
                    ids = context.get('active_ids')
                elif context.get('active_id', False):
                    ids = [context.get('active_id')]
        drawing_order_obj = self.pool.get('drawing.order')
        cr.execute("SELECT part_number,order_id,description,bom_qty,material,thickness,sum(quantity) as quantity,work_steps "\
                   "from drawing_order_line WHERE id IN %s and part_type=%s "\
                   "group by part_number, order_id, description, bom_qty,material,thickness, work_steps "\
                   "order by part_number", (tuple(ids),'PMS'))
        result = cr.dictfetchall()
        sequence = 0
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet("PMS BOM")
        sheet.write(0, 0,
                    'CNC Requisition for __________________________________ (ID ____________________________)')
        sheet.write(1, 0, 'ITEM NO')
        sheet.write(1, 1, 'PART NUMBER')
        sheet.write(1, 2, 'DESCRIPTION')
        sheet.write(1, 3, 'QUANTITY')
        sheet.write(1, 4, 'MATERIAL')
        sheet.write(1, 5, 'THICKNESS/LENGTH')
        sheet.write(1, 6, 'TOTAL QTY')
        sheet.write(1, 7, 'FILE NAME')
        sheet.write(1, 8, 'DEPARTMENTS')
        row = 2
        for r in result:
            sequence += 1
            sheet.write(row, 0, sequence)
            sheet.write(row, 1, r['part_number'])
            sheet.write(row, 2, r['description'])
            sheet.write(row, 3, r['bom_qty'])
            sheet.write(row, 4, r['material'])
            sheet.write(row, 5, r['thickness'])
            order_id = r['order_id']
            #mo_do_qty = 1.0
            order = drawing_order_obj.browse(cr, uid, order_id, context=context)
            if order:
                mo_do_qty = drawing_order_obj.get_big_subassembly_qty(cr, uid, order)
            #quantity = mo_do_qty * r['quantity']
            quantity = r['quantity']
            sheet.write(row, 6, quantity)
            sheet.write(row, 8, r['work_steps'])
            row += 1
        if sequence:
            file_name = "PMS BOM"
            if context.get('order_name'):
                file_name = u'%s-%s.xls' % (file_name, utils._format_file_name(context.get('order_name')))
            else:
                file_name += '.xls'
            temp_xls_file = tempfile.NamedTemporaryFile(delete=False,suffix='.xls')
            temp_xls_file_name = temp_xls_file.name
            temp_xls_file.close()
            workbook.save(temp_xls_file_name)
            return {
                'type': 'ir.actions.act_url',
                # 'url': '/web/export/print_pdf?filename=%s&filedata=%s'%(file_name, filedata),
                'url': '/web/export/drawing_order_print_pdf?file_name=%s&file_data=%s' % (
                    file_name, temp_xls_file_name),
                'target': 'self',
            }
        raise osv.except_osv(_("Error!"), _('No PMS parts were found!'))

    def print_pdf_pdftk(self, cr, uid, ids, context):
        if not ids:
            raise osv.except_osv(_("Error!"), _('No PDF files were found!'))
        if not type(ids) is list:
            ids = [ids]
        if len(ids) == 0:
            if context.get('active_model',False) == 'drawing.order.line':
                if context.get('active_ids',False):
                    ids = context.get('active_ids')
                elif context.get('active_id',False):
                    ids = [context.get('active_id')]
        else:
            attachment_obj = self.pool.get('ir.attachment')
            pdf_files = []
            cr.execute("SELECT id,drawing_file_name,part_number,order_id from drawing_order_line WHERE id IN %s ORDER BY id asc", (tuple(ids),))
            result = cr.dictfetchall()
            for r in result:
                drawing_file_name = r['drawing_file_name']
                line_id = r["id"]
                if drawing_file_name and drawing_file_name.lower().endswith('.pdf'):
                    file_ids = self.get_order_line_pdf_ids(cr, uid, line_id, drawing_file_name,context=context)
                    if file_ids:
                        file_full_path = attachment_obj.file_get_full_path(cr, uid, file_ids[0], context=context)
                        if os.path.exists(file_full_path):
                            pdf_files.append(file_full_path)
            if pdf_files:
                # Copy to a new folder
                temp_dir = tempfile.mkdtemp()
                count = 1
                for pdf_file in pdf_files:
                    dst_pdf_file_name = os.path.join(temp_dir, '%s.pdf' % str(count).zfill(10))
                    copyfile(pdf_file, dst_pdf_file_name)
                    count = count + 1
                file_name = "Drawing"
                if context.get('order_name'):
                    file_name = u'%s-%s.pdf' % (file_name, utils._format_file_name(context.get('order_name')))
                else:
                    file_name += '.pdf'
                temp_merged_pdf_file = tempfile.NamedTemporaryFile(delete=False)
                temp_merged_pdf_file_name = temp_merged_pdf_file.name
                temp_merged_pdf_file.close()
#                 temp_info_file = tempfile.NamedTemporaryFile(delete=False)
#                 temp_info_file.write('''
# InfoKey: Title
# InfoValue: %s
# InfoKey: Subject
# InfoValue: %s
# InfoKey: Author
# InfoValue: %s
# InfoKey: Creator
# InfoValue: %s
#     ''' % (context.get('order_name') and context.get('order_name') or 'Drawing Order',
#            'Drawing order %s pdf all parts' % (context.get('order_name') and context.get('order_name') or ''),
#            'Metro Tow Truck',
#            'Metro ERP'))
                all_pdf_files = os.path.join(temp_dir, '*.pdf')
                pdftk_cmd = 'pdftk %s cat output %s' % (all_pdf_files,
                                                        # temp_info_file.name,
                                                        temp_merged_pdf_file_name)
                os.system(pdftk_cmd)
                # Remove all file and folder
                rmtree(temp_dir)
                return {
                    'type': 'ir.actions.act_url',
                    'url': '/web/export/drawing_order_print_pdf?file_name=%s&file_data=%s' % (
                    file_name, temp_merged_pdf_file_name),
                    'target': 'self',
                }

        raise osv.except_osv(_("Error!"), _('No PDF files were found!'))

    def print_pdf(self, cr, uid, ids, context):
        if not ids:
            raise osv.except_osv(_("Error!"), _('No PDF files were found!'))
        if not type(ids) is list:
            ids = [ids]
        if len(ids) == 0:
            if context.get('active_model',False) == 'drawing.order.line':
                if context.get('active_ids',False):
                    ids = context.get('active_ids')
                elif context.get('active_id',False):
                    ids = [context.get('active_id')]
        else:
            attachment_obj = self.pool.get('ir.attachment')
            # output = PdfFileWriter()
            page_cnt = 0
            writer = pdfrw.PdfWriter()
            #order = self.browse(cr, uid, ids[0], context=context)
            #lines = self.browse(cr, uid, ids, context=context)
            #for line in lines:
            cr.execute("SELECT id,drawing_file_name,part_number,order_id from drawing_order_line WHERE id IN %s ORDER BY id asc", (tuple(ids),))
            result = cr.dictfetchall()
            for r in result:
                drawing_file_name = r['drawing_file_name']
                line_id = r["id"]
                #if line.drawing_file_name and line.drawing_file_name.lower().endswith('.pdf'):
                if drawing_file_name and drawing_file_name.lower().endswith('.pdf'):
                    # file_ids = attachment_obj.search(
                    #     cr, uid, #[('name', '=', 'drawing_file'),
                    #              # ('res_id', '=', line_id),
                    #              # ('res_model', '=', 'drawing.order.line')]
                    #                 ['|', '|', ('name', '=', 'drawing_file'),
                    #                  ('name', '=', drawing_file_name),
                    #                  ('res_name', '=', drawing_file_name),
                    #                  ('res_id', '=', line_id),
                    #                  ('res_model', '=', 'drawng.order.line')]
                    # )
                    file_ids = self.get_order_line_pdf_ids(cr, uid, line_id, drawing_file_name,context=context)
                    if file_ids:
                        file_full_path = attachment_obj.file_get_full_path(cr, uid, file_ids[0], context=context)
                        try:
                            writer.addpages(pdfrw.PdfReader(file_full_path).pages)
                        except pdfrw.PdfParseError,e:
                            # Try to search same file in this drawing order
                            cr.execute(
                                "SELECT id,drawing_file_name from drawing_order_line WHERE order_id = %s and id != %s and part_number = %s",
                                (r["order_id"],r["id"],r["part_number"]))
                            result2 = cr.dictfetchall()
                            for r2 in result2:
                                file_ids2 = self.get_order_line_pdf_ids(cr, uid, r2["id"], r2["drawing_file_name"],
                                                                       context=context)
                                if file_ids2:
                                    file_full_path = attachment_obj.file_get_full_path(cr, uid, file_ids2[0],
                                                                                       context=context)
                                    writer.addpages(pdfrw.PdfReader(file_full_path).pages)
                                    # Update corrupted file_id:
                                    new_attach_file = attachment_obj.browse(cr, uid, file_ids2[0], context=context)
                                    attachment_obj.write(cr, uid, file_ids, {'datas':new_attach_file.datas}, context=context)
                                    break
                            #raise osv.except_osv(_('Error'), _('ERP can not read malformed file (id=%s) %s') % (file_ids[0],drawing_file_name))
                        page_cnt += 1
                        # +++ HoangTK - 2018-08-15: Try to use pdfrw instead of pypdf2
                        # attach_file = attachment_obj.file_get(cr, uid, file_ids[0], context=context)
                        # if attach_file:
                        #     try:
                        #         input = PdfFileReader(attach_file,strict=False)
                        #         for page in input.pages:
                        #             output.addPage(page)
                        #             page_cnt += 1
                        #     except PdfReadError,e:
                        #         raise osv.except_osv(_('PError'),_('ERP can not read malformed file %s')%(drawing_file_name))
                        # --- HoangTK - 2018-08-15: Try to use pdfrw instead of pypdf2


            if page_cnt > 0:
                # +++ HoangTK - 12/10/2015: Use system temp file
                file_name = "Drawing"
                if context.get('order_name'):
                    file_name = u'%s-%s.pdf' % (file_name, utils._format_file_name(context.get('order_name')))
                else:
                    file_name += '.pdf'
                temp_drawing_pdf_file = tempfile.NamedTemporaryFile(delete=False)
                temp_drawing_pdf_file_name = temp_drawing_pdf_file.name
                temp_drawing_pdf_file.close()
                # +++ HoangTK - 2018-08-15: Try to use pdfrw instead of pypdf2
                # outputStream = file(temp_drawing_pdf_file_name, "wb")
                # output.write(outputStream)
                # outputStream.close()
                # --- HoangTK - 2018-08-15: Try to use pdfrw instead of pypdf2
                #             full_path_temp = attachment_obj.full_path(cr, uid, 'temp')
                # #            file_name = utils._format_file_name(order.name)
                #             file_name = "Drawing"
                #             if context.get('order_name'):
                #                 file_name = '%s-%s'%(file_name, utils._format_file_name(context.get('order_name')))
                #             full_file_name =  '%s/%s.pdf'%(full_path_temp, file_name,)
                #             outputStream = file(full_file_name, "wb")
                #             output.write(outputStream)
                #             outputStream.close()
                #             filedata = open(full_file_name,'rb').read().encode('base64')
                #             os.remove(full_file_name)
                # --- HoangTK - 12/10/2015: Use system temp file
                # +++ HoangTK - 12/10/2015: Replace print_pdf to fix memory error when pdf is too large
                writer.trailer.Info = pdfrw.IndirectPdfDict(
                    Title= context.get('order_name') and context.get('order_name') or 'Drawing Order',
                    Author='Metro Tow Truck',
                    Subject='Drawing order %s pdf all parts'%(context.get('order_name') and context.get('order_name') or ''),
                    Creator='Metro ERP',
                )
                writer.write(temp_drawing_pdf_file_name)
                return {
                    'type': 'ir.actions.act_url',
                    # 'url': '/web/export/print_pdf?filename=%s&filedata=%s'%(file_name, filedata),
                    'url': '/web/export/drawing_order_print_pdf?file_name=%s&file_data=%s' % (
                    file_name, temp_drawing_pdf_file_name),
                    'target': 'self',
                }

                # return self.pool.get('file.down').download_data(cr, uid, "%s.pdf"%(file_name,), filedata, context)
                # --- HoangTK - 12/10/2015: Replace print_pdf to fix memory error when pdf is too large
        raise osv.except_osv(_("Error!"), _('No PDF files were found!'))

    def print_pdf_zip(self, cr, uid, ids, context):
        if not ids:
            raise osv.except_osv(_("Error!"), _('No PDF files were found!'))
        if not type(ids) is list:
            ids = [ids]
        if len(ids) == 0:
            if context.get('active_model',False) == 'drawing.order.line':
                if context.get('active_ids',False):
                    ids = context.get('active_ids')
                elif context.get('active_id',False):
                    ids = [context.get('active_id')]
        attachment_obj = self.pool.get('ir.attachment')
        file_cnt = 0
        pdf_files =[]
        pdf_file_names = []
        #for line in lines:
        cr.execute("SELECT id,drawing_file_name from drawing_order_line WHERE id IN %s ORDER BY id asc", (tuple(ids),))
        result = cr.dictfetchall()
        for r in result:
            drawing_file_name = r['drawing_file_name']
            line_id = r["id"]
            if drawing_file_name and drawing_file_name.lower().endswith('.pdf'):
                file_ids = self.get_order_line_pdf_ids(cr, uid, line_id, drawing_file_name,context=context)
                if file_ids:
                    attach_file = attachment_obj.file_get(cr, uid, file_ids[0], context=context)
                    temp_pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                    temp_pdf_file_name = temp_pdf_file.name
                    pdf_files.append(temp_pdf_file_name)
                    pdf_file_names.append(drawing_file_name)
                    temp_pdf_file.close()
                    open(temp_pdf_file_name, "wb").write(attach_file.read())
                    file_cnt += 1
        if file_cnt > 0:
            zip_file_name = "Drawing PDF.zip"
            if context.get('order_name'):
                zip_file_name = u'%s-%s.zip' % (
                zip_file_name, utils._format_file_name(context.get('order_name')))
            temp_zip_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            temp_zip_file_name = temp_zip_file.name
            temp_zip_file.close()
            zip_file = zipfile.ZipFile(temp_zip_file_name, 'w', zipfile.ZIP_DEFLATED)
            for index, pdf_file in enumerate(pdf_files):
                zip_file.write(pdf_file, pdf_file_names[index])
            zip_file.close()
            for pdf_file in pdf_files:
                if os.path.isfile(pdf_file):
                    os.remove(pdf_file)
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/export/drawing_order_print_pdf?file_name=%s&file_data=%s' % (
                    zip_file_name, temp_zip_file_name),
                'target': 'self',
            }
        raise osv.except_osv(_("Error!"), _('No PDF files were found!'))

    def print_dxf(self, cr, uid, ids, context):
        if not ids:
            raise osv.except_osv(_("Error!"), _('No DXF files were found!'))
        if not type(ids) is list:
            ids = [ids]
        if len(ids) == 0:
            if context.get('active_model', False) == 'drawing.order.line':
                if context.get('active_ids', False):
                    ids = context.get('active_ids')
                elif context.get('active_id', False):
                    ids = [context.get('active_id')]
        else:
            attachment_obj = self.pool.get('ir.attachment')
            file_cnt = 0
            dxf_files = []
            dxf_file_names = []
            cr.execute("SELECT id,dxf_file_name from drawing_order_line WHERE id IN %s", (tuple(ids),))
            result = cr.dictfetchall()
            for r in result:
                dxf_file_name = r['dxf_file_name']
                line_id = r["id"]
                if dxf_file_name and dxf_file_name.lower().endswith('.dxf'):
                    # file_ids = attachment_obj.search(
                    #     cr, uid, [  # ('name', '=', 'drawing_file'),
                    #         ('res_id', '=', line_id),
                    #         ('res_model', '=', 'drawing.order.line'),
                    #         ('name','=',dxf_file_name)])
                    file_ids = self.get_order_line_dxf_ids(cr, uid, line_id, dxf_file_name,context=context)
                    if file_ids:
                        attach_file = attachment_obj.file_get(cr, uid, file_ids[0], context=context)

                        temp_dxf_file = tempfile.NamedTemporaryFile(delete=False,suffix='.dxf')
                        temp_dxf_file_name = temp_dxf_file.name
                        dxf_files.append(temp_dxf_file_name)
                        dxf_file_names.append(dxf_file_name)
                        temp_dxf_file.close()
                        open(temp_dxf_file_name, "wb").write(attach_file.read())
                        file_cnt += 1
            if file_cnt > 0:
                zip_file_name = "Drawing DXF"
                if context.get('order_name'):
                    zip_file_name = u'%s-%s.zip' % (zip_file_name, utils._format_file_name(context.get('order_name')))
                else:
                    zip_file_name += '.zip'
                temp_zip_file = tempfile.NamedTemporaryFile(delete=False,suffix='.zip')
                temp_zip_file_name = temp_zip_file.name
                temp_zip_file.close()
                zip_file = zipfile.ZipFile(temp_zip_file_name, 'w', zipfile.ZIP_DEFLATED)
                for index,dxf_file in enumerate(dxf_files):
                    zip_file.write(dxf_file, dxf_file_names[index])
                zip_file.close()
                for dxf_file in dxf_files:
                    if os.path.isfile(dxf_file):
                        os.remove(dxf_file)
                return {
                    'type': 'ir.actions.act_url',
                    'url': '/web/export/drawing_order_print_pdf?file_name=%s&file_data=%s' % (
                        zip_file_name, temp_zip_file_name),
                    'target': 'self',
                }

        raise osv.except_osv(_("Error!"), _('No DXF files were found!'))


    def unlink(self, cr, uid, ids, context=None):
        # delete the attachments
        for id in ids:
            utils.field_set_file(self, cr, uid, id, 'drawing_file', None, {'unlink': True}, context=None)
        resu = super(drawing_order_line, self).unlink(cr, uid, ids, context=context)
        return resu

    def _check_file_name(self, cr, uid, ids, context=None):
        for record in self.browse(cr, uid, ids, context=context):
            # +++ HoangTK - 11/18/2015: Allow file name is null
            if not record.drawing_file_name:
                continue
            # --- HoangTK - 11/18/2015
            same_file_name_ids = self.search(cr, uid, [('order_id', '=', record.order_id.id), ('id', '!=', record.id),
                                                       ('drawing_file_name', '=', record.drawing_file_name)],
                                             context=context)
            if same_file_name_ids:
                # +++ HoangTK - 11/18/2015: Fix bug file_name not found in drawing_order_line
                # raise osv.except_osv(_('Error'), _('Drawring file "%s" is duplicated under same order!')% (record.file_name,))
                raise osv.except_osv(_('Error'), _('Drawing file "%s" is duplicated under same order!') % (
                record.drawing_file_name,))
                # --- HoangTK - 11/18/2015

        return True

    #_constraints = [
    #    (_check_file_name,
    #     'Drawing file name is duplicated under same order!',
    #     ['file_name'])
    #]

    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        # line_data = self.browse(cr, uid, id, context=context)
        # default.update({
        #     'create_date': line_data.create_date
        # })
        default.update({
            'drawing_file': False, # PDF and DXF will be copied in drawing.order copy function
            # 'drawing_file_name': False,
            'dxf_file': False,
            # 'dxf_file_name': False,
        })
        return super(drawing_order_line, self).copy_data(cr, uid, id, default, context)

    def create(self, cr, uid, vals, context=None):
        result = super(drawing_order_line, self).create(cr, uid, vals, context)
        order_history_obj = self.pool.get('drawing.order.history')
        if result:
            order_line = self.browse(cr, uid, result)
            order_history_obj.create(cr, uid, {
                'drawing_order_id': order_line.order_id.id,
                'user_id': uid,
                'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'content': _('Create Drawing Order Line'),
                #'vals': '%s' % vals,
            })
        return result



    def link_dxf_attachment(self, cr, uid, drawing_order_line_ids, attachment, dxf_file_name):
        attachment_obj = self.pool.get('ir.attachment')
        attachment_ids = []
        attachment_ids.append(attachment.id)
        # Copy not work
        # if len(drawing_order_line_ids) > 0:
        #     for count in range(0,len(drawing_order_line_ids)-1):
        #         copy_attachment_id = attachment_obj.copy(cr, uid, attachment.id)
        #         attachment_ids.append(copy_attachment_id)
        self.write(cr, uid, drawing_order_line_ids, {
            'dxf_file_name': dxf_file_name,
        })
        delete_attachment_ids = []
        for index,line_id in  enumerate(drawing_order_line_ids):
            # Remove old attachment if any:
            old_attachment_ids = attachment_obj.search(cr, uid, [
                ('res_id', '=', line_id),
                ('res_model', '=', 'drawing.order.line'),
                '|', '|',
                ('res_name', '=', dxf_file_name),
                ('name', '=', dxf_file_name),
                ('name', '=', 'dxf_file'),])
            delete_attachment_ids.extend(old_attachment_ids)
            attachment_obj.create(cr, uid, {
                'name': dxf_file_name,
                'res_name': dxf_file_name,
                'datas_fname': dxf_file_name,
                'res_id': line_id,
                'type': 'binary',
                'res_model': 'drawing.order.line',
                'datas': attachment.datas
            })
            # attachment_obj.write(cr, uid, [attachment_ids[index]], {
            #     'res_id': line_id,
            #     'res_model': 'drawing.order.line',
            #     'res_name': dxf_file_name,
            #     'name': dxf_file_name,
            #     'datas_fname': dxf_file_name,
            # })
        attachment_obj.unlink(cr, uid, delete_attachment_ids)
        return True

    def link_dxf_attachments_with_lines(self, cr, uid, drawing_order_line_ids, attachments):
        count = 0
        for attachment in attachments:
            if attachment.name.lower().endswith('.dxf'):
                file_parts = os.path.splitext(attachment.name)
                file_name = file_parts[0]
                file_ext = ""
                if len(file_parts) > 1:
                    file_ext = file_parts[1]
                new_file_name = file_name
                if file_ext:
                    new_file_name = new_file_name + file_ext
                line_ids = self.search(cr, uid, [('id', 'in', drawing_order_line_ids),
                                                 ('part_number', '=ilike', file_name)])
                if line_ids:
                    self.link_dxf_attachment(cr, uid, line_ids, attachment, new_file_name)
                    count += 1

        return count

    def link_pdf_attachments_with_lines(self, cr, uid, drawing_order_line_ids, attachments, watermark = True):
        count = 0
        watermark_ids = []
        for attachment in attachments:
            if attachment.name.lower().endswith('.pdf'):
                file_parts = os.path.splitext(attachment.name)
                file_name = file_parts[0]
                file_ext = ""
                if len(file_parts) > 1:
                    file_ext = file_parts[1]
                new_file_name = file_name
                if file_ext:
                    new_file_name = new_file_name + file_ext
                line_ids = self.search(cr, uid, [
                    ('id', 'in', drawing_order_line_ids),
                    ('part_number', '=ilike', file_name)
                    ])
                if line_ids:
                    self.link_pdf_attachment(cr, uid, line_ids, attachment, new_file_name)
                    if watermark:
                        watermark_ids.extend(line_ids)
                    count += 1
        self._add_watermark(cr, uid, line_ids)
        return count

    def link_pdf_attachment(self, cr, uid, drawing_order_line_ids, attachment, drawing_file_name):
        attachment_obj = self.pool.get('ir.attachment')
        attachment_ids = []
        attachment_ids.append(attachment.id)
        # Copy attachment not work
        # if len(drawing_order_line_ids) > 0:
        #     for count in range(0,len(drawing_order_line_ids)-1):
        #         copy_attachment_id = attachment_obj.copy(cr, uid, attachment.id)
        #         attachment_ids.append(copy_attachment_id)
        #Update name first
        self.write(cr, uid, drawing_order_line_ids, {
            'drawing_file_name': drawing_file_name,
            'original_drawing': False,
        })
        delete_attachment_ids = []
        for index,line_id in  enumerate(drawing_order_line_ids):
            # Remove old attachment if any:
            old_attachment_ids = attachment_obj.search(cr, uid, [
                ('res_id', '=', line_id),
                ('res_model', '=', 'drawing.order.line'),
                '|','|',
                ('res_name', '=',drawing_file_name),
                ('name', '=', drawing_file_name),
                ('name', '=', 'drawing_file')])
            delete_attachment_ids.extend(old_attachment_ids)
            #attachment_obj.unlink(cr, uid, old_attachment_ids)
            attachment_obj.create(cr, uid, {
                'name': drawing_file_name,
                'res_name': drawing_file_name,
                'datas_fname': drawing_file_name,
                'res_id': line_id,
                'type': 'binary',
                'res_model': 'drawing.order.line',
                'datas': attachment.datas
            })
        attachment_obj.unlink(cr, uid, delete_attachment_ids)
        return True

    # +++ HoangTK - 12/08/2015: Override write method to update drawing order quantity
    def write(self, cr, uid, ids, vals, context=None):
        if not isinstance(ids, list):
            ids = [ids]
        new_ids = []
        for line_id in ids:
            if line_id:
                new_ids.append(line_id)
        ids = new_ids
        result = super(drawing_order_line, self).write(cr, uid, ids, vals, context=context)
        #order_line_vals = self.read(cr, uid, ids, ['order_id'])
        #drawing_ids = []
        #for value in order_line_vals:
        #    if value['order_id'][0] not in drawing_ids:
        #        drawing_ids.append(value['order_id'][0])
        #drawing_order_obj = self.pool.get('drawing.order')
        #drawing_order_obj.update_qty(cr, uid, drawing_ids)
        #order_history_obj = self.pool.get('drawing.order.history')
        #for order_line in self.browse(cr, uid, ids):
        #    if 'drawing_file' in vals:
        #        vals['drawing_file'] = '**DRAWING FILE CONTENT**'
        #    if 'original_drawing' in vals:
        #        vals['original_drawing'] = '**DRAWING FILE CONTENT**'
        #    order_history_obj.create(cr, uid, {
        #        'drawing_order_id': order_line.order_id.id,
        #        'user_id': uid,
        #        'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        #        'content': _('Update Drawing Order Line'),
        #        'vals': '%s' % vals,
        #    })
        return result
        # --- HoangTK - 12/08/2015: Override write method to update drawing order quantity
