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

import os
from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class upload_multi_drawings(osv.osv_memory):
    _name = "upload.multi.drawings"
    _description = "Upload multi drawings"

    _columns = {
        'product_id': fields.many2one('product.product','Product'),
        'step_ids': fields.many2many('drawing.step', string='Working Steps'),
        'attachment_ids': fields.many2many('ir.attachment','upload_multi_drawings_ir_attachments_rel','upload_drawing_id', 'attachment_id', 'Drawings'),
        'note': fields.char('Note',size=128),
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(upload_multi_drawings, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        if record_id:
            drawing_order_obj = self.pool.get('drawing.order')
            if drawing_order_obj.can_reuse_drawing_file(cr, uid, record_id):
                res.update({'note': 'There are existing drawing PDFs. Consider reuse them before upload!'})
        return res

    def do_add(self, cr, uid, ids, context=None):
        """ To create drawings lines
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: the ID or list of IDs if we want more than one
        @param context: A standard dictionary
        @return:
        """
        if context is None:
            context = {}
        active_id = context.get('active_id')
        if not active_id:
            return False
        data = self.browse(cr, uid, ids[0], context=context)
        active_model = context.get('active_model')
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        order = False
        order_line = False
        if active_model == 'drawing.order':
            order = drawing_order_obj.browse(cr, uid, active_id)
        elif active_model == 'drawing.order.line':
            order_line = drawing_order_line_obj.browse(cr, uid, active_id)
            order = order_line.order_id
        else:
            return False
        #mfg_ids = []
        #for mfg_id in order.sale_product_ids:
        #    mfg_ids.append("ID" + str(mfg_id.name))
        #mfg_name = "_".join(mfg_ids)
        cant_link_attachments = []
        link_count = 0
        for attachment in data.attachment_ids:
            if attachment.name.lower().endswith('.pdf'):
                file_parts = os.path.splitext(attachment.name)
                file_name = file_parts[0]
                file_ext = ""
                if len(file_parts) > 1:
                    file_ext = file_parts[1]
                #new_file_name = file_name + "-" + mfg_name
                new_file_name = file_name
                if file_ext:
                    new_file_name = new_file_name + file_ext
                if order_line and order_line.part_number:
                    if order_line.part_number.lower() == file_name.lower():
                        drawing_line_ids = drawing_order_line_obj.search(cr, uid, [
                                                                     ('order_id','=',order.id),
                                                                     ('part_number', '=', order_line.part_number)
                                                                     ])
                        drawing_order_line_obj.link_pdf_attachment(cr, uid, drawing_line_ids, attachment, new_file_name)
                        link_count += 1
                        break
                    else:
                        cant_link_attachments.append(attachment)
                    continue
                drawing_line_ids = drawing_order_line_obj.search(cr, uid, [
                                                                     ('order_id','=',order.id),
                                                                     ('part_number', '=ilike', file_name)
                                                                     ])
                if not drawing_line_ids:
                    cant_link_attachments.append(attachment)
                drawing_order_line_obj.link_pdf_attachment(cr, uid, drawing_line_ids, attachment, new_file_name)
                link_count += len(drawing_line_ids)
        if link_count > 0 and order.state in ['draft','bom_uploaded']:
            drawing_order_obj.write(cr, uid, [order.id], {
                'state': 'pdf_uploaded'
            })
        drawing_order_obj._is_ready(cr, uid, [order.id])
        if len(cant_link_attachments):
            attachment_name = '\n'.join(file.name for file in cant_link_attachments)
            result = self.pool.get('warning').info(cr, uid, title='Warning', message= _("The file names don't match or part lines don't exist: \n%s")% (attachment_name,))
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
