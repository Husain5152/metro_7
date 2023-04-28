# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST

class fix_pdf_dxf_corrupt_wizard(osv.osv_memory):
    _name='fix.pdf.dxf.corrupt.wizard'
    _description = 'Fix Pdf Dxf Corrupt Wizard'
    _columns = {
        'do_id': fields.many2one('drawing.order','Drawing Order',readonly=True, required=True),
        'corrupted_pdf_lines': fields.many2many('drawing.order.line',string='Corrupted PDF lines', readonly=True),
        'corrupted_dxf_lines': fields.many2many('drawing.order.line', string='Corrupted DXF lines',readonly=True),
        'pdf_attachment_ids': fields.many2many('ir.attachment', 'upload_fix_pdf_ir_attachments_rel',
                                           'upload_id', 'attachment_id', 'Drawings'),
        'dxf_attachment_ids': fields.many2many('ir.attachment', 'upload_fix_dxf_ir_attachments_rel',
                                               'upload_id', 'attachment_id', 'DXFs'),

    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(fix_pdf_dxf_corrupt_wizard, self).default_get(cr, uid, fields, context=context)
        active_id = context and context.get('active_id', False) or False
        active_model = context and context.get('active_model', False) or False
        order_line_obj = self.pool.get('drawing.order.line')
        if active_id and active_model == 'drawing.order':
            order_line_ids =  order_line_obj.search(cr, uid, [('order_id','=',active_id),
                                                              '|',('drawing_file_name','!=',False),
                                                              ('dxf_file_name','!=',False)],
                                                    context=context)
            results = order_line_obj.read(cr, uid,  order_line_ids,['id','pdf_valid','dxf_valid'], context=context)
            corrupted_pdf_line_ids = []
            corrupted_dxf_line_ids = []
            for line in results:
                if not line['pdf_valid']:
                    corrupted_pdf_line_ids.append(line['id'])
                if not line['dxf_valid']:
                    corrupted_dxf_line_ids.append(line['id'])
            res.update({'corrupted_pdf_lines': [[6, False, corrupted_pdf_line_ids]],
                        'corrupted_dxf_lines': [[6, False, corrupted_dxf_line_ids]],
                        'do_id': active_id,
                        })
        return res

    def do_fix(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids, context=context)[0]
        order_obj = self.pool.get('drawing.order')
        order_line_obj = self.pool.get('drawing.order.line')
        attachment_obj = self.pool.get('ir.attachment')
        fix_pdf_count = 0
        fix_dxf_count = 0
        if wizard and wizard.do_id:
            order = order_obj.browse(cr, uid, wizard.do_id.id, context=context)
            pdf_line_ids = []
            dxf_line_ids = []
            for line in wizard.corrupted_pdf_lines:
                if not line.pdf_valid:
                    pdf_line_ids.append(line.id)
            for line in wizard.corrupted_dxf_lines:
                if not line.dxf_valid:
                    dxf_line_ids.append(line.id)
            if pdf_line_ids:
                if wizard.pdf_attachment_ids:
                    if order.state in ['ready','confirmed','approved']:
                        fix_pdf_count = order_line_obj.link_pdf_attachments_with_lines(cr, uid, pdf_line_ids, wizard.pdf_attachment_ids,True)
                    else:
                        fix_pdf_count = order_line_obj.link_pdf_attachments_with_lines(cr, uid, pdf_line_ids,
                                                                                   wizard.pdf_attachment_ids)
                else:
                    # Try to search pdf in current order id
                    order_lines = order_line_obj.read(cr, uid, pdf_line_ids,
                                                              ['id', 'pdf_valid', 'drawing_file_name',
                                                               'part_number'])
                    for line in order_lines:
                        existing_line_ids = order_obj.search(cr, uid, [
                            ('order_id', '=', order.id),
                            ('id', '!=', line['id']),
                            ('part_number', '=', line['part_number']),
                            ('drawing_file_name', '!=', False),
                        ], order='create_date desc')
                        if existing_line_ids:
                            existing_line = order_line_obj.read(cr, uid, existing_line_ids[0], ['drawing_file_name'], context=context)
                            drawing_file_name = existing_line['drawing_file_name']
                            file_ids = order_line_obj.get_order_line_pdf_ids(cr, uid, existing_line_ids, drawing_file_name)
                            if file_ids:
                                attachment = attachment_obj.read(cr, uid, file_ids[0], ['res_id'], context=context)
                                reuse_id = attachment['res_id']
                                reuse_line = order_line_obj.browse(cr, uid, reuse_id, context=context)
                                new_attachment_id = attachment_obj.create(cr, uid, {
                                    'name': reuse_line.drawing_file_name,
                                    'res_name': reuse_line.drawing_file_name,
                                    'datas_fname': reuse_line.drawing_file_name,
                                    'res_id': line['id'],
                                    'type': 'binary',
                                    'res_model': 'drawing.order.line',
                                    'datas': reuse_line.drawing_file
                                })
                                order_line_obj.write(cr, uid, [line['id']],{
                                    'drawing_file_name': reuse_line.drawing_file_name,
                                    'original_drawing': reuse_line.original_drawing,
                                })
            if dxf_line_ids:
                if wizard.dxf_attachment_ids:
                    fix_dxf_count = order_line_obj.link_dxf_attachments_with_lines(cr, uid, dxf_line_ids, wizard.dxf_attachment_ids)

                else:
                    order_lines = order_line_obj.read(cr, uid, dxf_line_ids, ['id', 'dxf_valid', 'dxf_file_name',
                                                                                  'part_number'])
                    for line in order_lines:
                        # Try to search dxf in current order id
                        existing_line_ids = order_line_obj.search(cr, uid, [
                            ('order_id', '=', order.id),
                            ('id', '!=', line['id']),
                            ('part_number', '=', line['part_number']),
                            ('dxf_file_name', '!=', False),
                        ], order='create_date desc')
                        if existing_line_ids:
                            existing_line = order_line_obj.read(cr, uid, existing_line_ids[0],
                                                                        ['dxf_file_name'], context=context)
                            dxf_file_name = existing_line['dxf_file_name']
                            file_ids = order_line_obj.get_order_line_dxf_ids(cr, uid, existing_line_ids,
                                                                                     dxf_file_name)
                            if file_ids:
                                attachment = attachment_obj.read(cr, uid, file_ids[0], ['res_id'], context=context)
                                reuse_id = attachment['res_id']
                                reuse_line = order_line_obj.browse(cr, uid, reuse_id, context=context)
                                new_attachment_id = attachment_obj.create(cr, uid, {
                                    'name': reuse_line.dxf_file_name,
                                    'res_name': reuse_line.dxf_file_name,
                                    'datas_fname': reuse_line.dxf_file_name,
                                    'res_id': line['id'],
                                    'type': 'binary',
                                    'res_model': 'drawing.order.line',
                                    'datas': reuse_line.dxf_file
                                })
                                order_line_obj.write(cr, uid, [line['id']], {
                                    'dxf_file_name': reuse_line.dxf_file_name,
                                })

        return self.pool.get('warning').info(cr, uid, title='Information', message=_(
                "%s pdf files and %s dxf files has been updated to DO!")%(fix_pdf_count, fix_dxf_count))

fix_pdf_dxf_corrupt_wizard()