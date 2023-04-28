# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp.tools.translate import _
from openerp import netsvc
import time
import datetime
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.report.PyPDF2 import PdfFileWriter, PdfFileReader
from openerp.addons.metro import utils
import zipfile
import random
import os
import re
from openerp import SUPERUSER_ID
import tempfile


class work_order_cnc(osv.osv):
    _name = "work.order.cnc"
    _inherit = "work.order.cnc"

    def onchange_drawing_order(self, cr, uid, ids, drawing_order_id, context=None):
        vals = {}
        if drawing_order_id:
            drawing_order_obj = self.pool.get('drawing.order')
            order = drawing_order_obj.browse(cr, uid, drawing_order_id, context=context)
            vals.update({
                'name': order.name,
            })
            order_line_ids = []
            cr.execute("SELECT id from drawing_order_line WHERE order_id = %s AND dxf_file_name is not null", (drawing_order_id,))
            result = cr.dictfetchall()
            for r in result:
                order_line_ids.append(r["id"])
            if order_line_ids:
                vals.update({
                            'drawing_order_lines': [[6, False, order_line_ids]]
                         })
        return {'value': vals}

    def write(self, cr, uid, ids, vals, context=None):
        if not type(ids) is list:
            ids = [ids]
        res = super(work_order_cnc, self).write(cr, uid, ids, vals, context=context)
        if ids and vals.get('drawing_order_id', False):
            drawing_order_obj = self.pool.get('drawing.order')
            drawing_order_obj.write(cr, uid, vals.get('drawing_order_id'), {'cnc_workorder_id': ids[0]})
        return res

    def _get_cnc_code(self, material, thickness, cnc_code):
        result = '%s %s' % (material, thickness)
        if cnc_code:
            result = cnc_code
        elif not material and thickness:
            result = 'Unknown Material %s'%thickness
        elif material and not thickness:
            result = '%s Unknown Thickness'%material
        return utils._format_file_name(result)

    def print_dxf(self, cr, uid, ids, context=None):
        if not type(ids) is list:
            ids = [ids]
        attachment_obj = self.pool.get('ir.attachment')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        if len(ids) > 0:
            dxf_temp_file_names = []
            zip_file_name = "DXF"
            temp_zip_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            temp_zip_file_name = temp_zip_file.name
            temp_zip_file.close()
            zip_file = zipfile.ZipFile(temp_zip_file_name, 'w', zipfile.ZIP_DEFLATED)
            file_name_dicts = dict()
            for cnc_wo in self.browse(cr, uid, ids, context=context):
                #Group dxf based on thickness and material
                zip_file_name += '-' + utils._format_file_name(cnc_wo.name)
                for order_line in cnc_wo.drawing_order_lines:
                    directory_name = self._get_cnc_code(order_line.material,
                                                        order_line.thickness,
                                                        order_line.product_id and order_line.product_id.cnc_code or False)
                    exist_dxf_name = file_name_dicts.setdefault((directory_name, order_line.dxf_file_name), False)
                    if not exist_dxf_name:
                        # file_ids = attachment_obj.search(
                        #     cr, uid, [  # ('name', '=', 'drawing_file'),
                        #         ('res_id', '=', order_line),
                        #         ('res_model', '=', 'drawing.order.line'),
                        #         ('name', '=', order_line.dxf_file_name)])
                        file_ids = drawing_order_line_obj.get_order_line_dxf_ids(cr, uid, order_line.id,order_line.dxf_file_name)
                        if file_ids:
                            attach_file = attachment_obj.file_get(cr, uid, file_ids[0], context=context)

                            temp_dxf_file = tempfile.NamedTemporaryFile(delete=False, suffix='.dxf')
                            temp_dxf_file_name = temp_dxf_file.name
                            dxf_temp_file_names.append(temp_dxf_file_name)
                            temp_dxf_file.close()
                            open(temp_dxf_file_name, "wb").write(attach_file.read())
                            zip_file.write(temp_dxf_file_name, '%s//%s'%(directory_name,order_line.dxf_file_name))
                            file_name_dicts.update({(directory_name, order_line.dxf_file_name): True})
            for temp_dxf_file_name in dxf_temp_file_names:
                if os.path.isfile(temp_dxf_file_name):
                    os.remove(temp_dxf_file_name)
            zip_file_name += ".zip"
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/export/drawing_order_print_pdf?file_name=%s&file_data=%s' % (
                    zip_file_name, temp_zip_file_name),
                'target': 'self',
            }
        raise osv.except_osv(_("Error!"), _('No DXF files were found!'))

    _columns = {
        'drawing_order_id': fields.many2one('drawing.order', 'Drawing Order'),
        'drawing_order_lines': fields.many2many('drawing.order.line',string = 'Drawing Order Lines'),
    }


class work_order_cnc_line(osv.osv):
    _name = "work.order.cnc.line"
    _inherit = "work.order.cnc.line"
    _columns = {
        'drawing_order_id': fields.related('order_id', 'drawing_order_id', type='many2one', relation="drawing.order",
                                           string="Drawing Order", readonly=True)
    }