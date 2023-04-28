# -*- coding: utf-8 -*-
import time
from openerp.report import report_sxw
from openerp.osv import osv, fields
from openerp.osv import osv
from datetime import datetime
import openerp.tools as tools
from datetime import timedelta

class shipping_list_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(shipping_list_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_drawing_order_ids': self._get_drawing_order_ids,
            'get_drawing_order_info': self._get_drawing_order_info,
            'get_purchase_lines': self._get_purchase_lines,
            'get_all_purchase_lines': self._get_all_purchase_lines,
            'get_total_qty': self._get_total_qty,
            'get_mfg_name': self._get_mfg_name,
            'get_total_set': self._get_total_set,
            'get_do_mfg_id_list': self._get_do_mfg_id_list,
        })

    def _get_do_mfg_id_list(self, po):
        po_obj = self.pool.get('purchase.order')
        result = po_obj.get_do_mfg_id_list(po.order_line)
        sequence = 1
        for key in result:
            result[key]['id'] = sequence
            sequence += 1
        return result.values()

    def _get_total_set(self, po):
        return len(self._get_do_mfg_id_list(po.order_line))

    def _get_mfg_name(self, po):
        po_obj = self.pool.get('purchase.order')
        return po_obj.get_mfg_name(po.order_line)

    def _get_drawing_order_info(self, drawing_order_id):
        result = {'name': '',
                  'do_no': '',
                  'mfg_name': '',
                  'bigsubassembly_name': ''}
        do_obj = self.pool.get('drawing.order')
        do = do_obj.browse(self.cr, self.uid, drawing_order_id)
        if do:
            result['name'] = do.name
            result['do_no'] = drawing_order_id
            mfg_name = ','.join([mfg_id.name for mfg_id in do.mfg_ids])
            result['mfg_name'] = mfg_name
            result['bigsubassembly_name'] = do.product_id.name
        return result

    def _get_total_qty(self, po, drawing_order_id, column_name):
        result = 0
        if column_name in ['do_bom_qty','do_qty','bom_qty', 'qty']:
            if column_name in ['do_bom_qty','do_qty']:
                lines = self._get_purchase_lines(po, drawing_order_id)
            else:
                lines = self._get_all_purchase_lines(po)
            for line in lines:
                if column_name in ['do_bom_qty', 'bom_qty']:
                    if line['bom_qty']:
                        result += line['bom_qty']
                else:
                    result += line['quantity']
        return result

    def _get_purchase_lines(self, po, drawing_order_id):
        line_ids = []
        for line in po.order_line:
            if line.drawing_order_id:
                if line.drawing_order_id.id == drawing_order_id:
                    line_ids.append(line.id)

        result = []
        if line_ids:
            po_line_obj = self.pool.get('purchase.order.line')
            order_lines = po_line_obj.browse(self.cr, self.uid, line_ids)
            sequence = 1
            for line in order_lines:
                po_line = self._get_report_values(line)
                po_line['id'] = sequence
                result.append(po_line)
                sequence += 1
        return result

    def _get_drawing_order_ids(self, po):
        line_dicts = {}
        for line in po.order_line:
            if line.drawing_order_id:
                line_dicts.update({line.drawing_order_id.id: True})
        return line_dicts.keys()

    def _get_all_purchase_lines(self, po):
        result = []
        sequence = 1
        for line in po.order_line:
            po_line = self._get_report_values(line)
            po_line['id'] = sequence
            result.append(po_line)
            sequence += 1
        return result

    def _get_report_values(self, line):
        result = {
            'bom_level': '',
            'erp_no': '',
            'name': '',
            'part_number': '',
            'description': '',
            'bom_qty': '',
            'quantity': 0,
            'thickness': '',
            'material': '',
        }
        if line.bom_level:
            result['bom_level'] = line.bom_level
        if line.product_id:
            result['erp_no'] = line.product_id.default_code
            result['name'] = line.product_id.name
        if line.part_number:
            result['part_number'] = line.part_number
        result['description'] = line.name
        if line.bom_qty:
            result['bom_qty'] = line.bom_qty
        result['quantity'] = line.product_qty
        if line.thickness:
            result['thickness'] = line.thickness
        if line.material:
            result['material'] = line.material
        return result

report_sxw.report_sxw('report.purchase.order.shipping_normal','purchase.order','addons/metro_mrp_drawing/report/shipping_list_normal.rml',
                      parser=shipping_list_parser, header='internal landscape')
report_sxw.report_sxw('report.purchase.order.shipping_break','purchase.order','addons/metro_mrp_drawing/report/shipping_list_break.rml',
                      parser=shipping_list_parser, header='internal landscape')
report_sxw.report_sxw('report.purchase.order.shipping_normal_break_id','purchase.order','addons/metro_mrp_drawing/report/shipping_list_normal_break_id.rml',
                      parser=shipping_list_parser, header='internal landscape')
report_sxw.report_sxw('report.purchase.order.shipping_break_break_id','purchase.order','addons/metro_mrp_drawing/report/shipping_list_break_break_id.rml',
                      parser=shipping_list_parser, header='internal landscape')

