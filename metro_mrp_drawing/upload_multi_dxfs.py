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

class upload_multi_dxfs(osv.osv_memory):
    _name = "upload.multi.dxfs"
    _description = "Upload multi dxfs"

    _columns = {
        'note': fields.char('Note', size=128),
        'attachment_ids': fields.many2many('ir.attachment','upload_multi_dxfs_ir_attachments_rel','upload_dxf_id', 'attachment_id', 'DXFs'),
    }


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
        order_line = False
        if active_model == 'drawing.order':
            order = drawing_order_obj.browse(cr, uid, active_id)
        elif active_model == 'drawing.order.line':
            order_line = drawing_order_line_obj.browse(cr, uid, active_id)
            order = order_line.order_id
        else:
            return self.pool.get('warning').info(cr, uid, title='Error', message=_("No drawing order line selected."))
        #mfg_ids = []
        #for mfg_id in order.sale_product_ids:
        #    mfg_ids.append("ID" + str(mfg_id.name))
        #mfg_name = "_".join(mfg_ids)
        cant_link_attachments = []
        link_count = 0
        for attachment in data.attachment_ids:
            #file_parts = attachment.name.split('.')
            if attachment.name.lower().endswith('.dxf'):
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
                                                                     ('part_number', '=', order_line.part_number),
                                                                     ('part_type','in',['PMS','POEM'])
                                                                     ])
                        drawing_order_line_obj.link_dxf_attachment(cr, uid, drawing_line_ids, attachment, new_file_name)
                        link_count += 1
                        break
                    else:
                        cant_link_attachments.append(attachment)
                    continue
                drawing_line_ids = drawing_order_line_obj.search(cr, uid, [
                                                                     ('order_id','=',order.id),
                                                                     ('part_number', '=ilike', file_name),
                                                                     ('part_type', 'in', ['PMS', 'POEM'])
                                                                     ])
                if not drawing_line_ids:
                    cant_link_attachments.append(attachment)
                drawing_order_line_obj.link_dxf_attachment(cr, uid, drawing_line_ids, attachment, new_file_name)
                link_count += len(drawing_line_ids)
        drawing_order_obj._is_ready(cr, uid, [order.id])
        if len(cant_link_attachments):
            attachment_name = '\n'.join(file.name for file in cant_link_attachments)
            result = self.pool.get('warning').info(cr, uid, title='Warning', message= _("%s files have been updated. %s file not updated (name don't match or part don't exist): \n%s")% (link_count, len(cant_link_attachments),attachment_name,))
        else:
            result = self.pool.get('warning').info(cr, uid, title='Information', message=_("%s files have been updated.") % (link_count))
        return result
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
