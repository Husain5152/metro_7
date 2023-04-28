# -*- encoding: utf-8 -*-
'''
Created on 24-11-2015

@author: Khai Hoang
'''
from openerp.osv import osv, fields
from openerp.tools.translate import _
from lxml import etree
from openerp.addons.metro import utils
from datetime import datetime
from openerp import tools
from openerp import tools, SUPERUSER_ID
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST
from openerp.addons.metro_mrp_drawing.pur_req import PR_TYPES
import xlwt
import tempfile
import xlwt
import tempfile

SHIPPING_XLS_COLS_WIDTH = [50,100,100,300,300,300,120,120,120,120,120]
SHIPPING_XLS_COLS_SIZE = 11
class purchase_order(osv.osv):
    _inherit = "purchase.order"

    def get_mfg_ids(self, order_lines):
        mfg_ids = {}
        for line in order_lines:
            for mfg_id in line.mfg_ids:
                mfg_ids[mfg_id.name] = True
        return mfg_ids.keys()

    def get_mfg_name(self, order_lines):
        mfg_ids = self.get_mfg_ids(order_lines)
        return ','.join(mfg_ids)

    def get_do_ids(self, order_lines):
        do_ids = {}
        for line in order_lines:
            if line.drawing_order_id:
                if line.drawing_order_id.id not in do_ids:
                    do_ids[line.drawing_order_id.id] = {'id': line.drawing_order_id.id,
                                                        'name': line.drawing_order_id.name,
                                                        'big_subassembly': line.drawing_order_id.product_id.name}
        return do_ids

    def get_do_mfg_id_list(self, order_lines):
        result = {}
        for line in order_lines:
            if line.mfg_ids:
                for mfg_id in line.mfg_ids:
                    if line.drawing_order_id:
                        key = '%s-%s'%(mfg_id, line.drawing_order_id.id)
                    else:
                        key = '%s' % (mfg_id)
                    if key in result:
                        result[key]['items'] += 1
                        result[key]['pieces'] += line.product_qty
                    else:
                        result[key] = {
                            'items': 1,
                            'pieces': line.product_qty,
                            'mfg_id': mfg_id.name,

                        }
                        if line.drawing_order_id:
                            result[key].update({
                                'do_id': line.drawing_order_id.id,
                                'do_name': line.drawing_order_id.name,
                                'big_subassembly': line.drawing_order_id.product_id.name,
                            })
                        else:
                            result[key].update({
                                'do_id': '',
                                'do_name': '',
                                'big_subassembly': '',
                            })

        return result

    def print_shipping_list(self, cr, uid, ids, break_do=False, break_id= False, report_type='xls', chinese=False, context=None):
        if not ids:
            raise osv.except_osv(_("Error!"), _('Invalid Purchase Order!'))
        if not type(ids) is list:
            ids = [ids]
        if report_type == 'xls':
            workbook = xlwt.Workbook()
            style_string = "font: bold on,height 240"
            style = xlwt.easyxf(style_string)
            po_names = []
            for po in self.browse(cr, uid, ids, context=context):
                po_names.append(po.name)
                delivery_date = ''
                if po.delivery_date:
                    delivery_date = datetime.strptime(po.delivery_date, DEFAULT_SERVER_DATE_FORMAT).strftime("%Y-%m-%d")

                mfg_name = self.get_mfg_name(po.order_line)
                sheet = workbook.add_sheet(po.name)
                for col in range(SHIPPING_XLS_COLS_SIZE):
                    sheet.col(col).width = SHIPPING_XLS_COLS_WIDTH[col] * 20
                row = 0
                if chinese:
                    sheet.write(row, 0, _('货单 SHIPPING LIST FOR:'), style)
                else:
                    sheet.write(row, 0, _('SHIPPING LIST FOR:'), style)
                sheet.write(row, 6, _('MFG IDS:'), style)
                sheet.write(row, 8, mfg_name, style)
                row += 1
                sheet.write(row, 0, po.name, style)
                if chinese:
                    sheet.write(row, 6, _('邮寄日期 Delivery Date (YYYY/MM/DD):'), style)
                else:
                    sheet.write(row, 6, _('Delivery Date (YYYY/MM/DD):'), style)
                sheet.write(row, 8, delivery_date, style)
                row += 1
                do_mfg_id_list = self.get_do_mfg_id_list(po.order_line)
                set_no = len(do_mfg_id_list)
                if chinese:
                    sheet.row(row).height_mismatch = True
                    sheet.row(row).height = 84 * 20
                    sheet.write(row, 1, _('笔记:'), style)
                    sheet.write(row, 2, _('1. 包装成套(套件).  此PO包含8个不同的集合. \n' \
                                          '   Pack this PO in sets (kits). This PO contains %s differents sets.\n' \
                                          '2. 每个包装必须有以下列出的特殊标记\n' \
                                          '   Each package must have special markings that are listed below\n' \
                                          '3. 如果1套装/套装有1个以上的包装，则必须显示包装总量，例如：3个包装盒中的1个\n' \
                                          '   If there is more than 1  package for 1 set/kit, total amount of packages must be shown, eg.: 1 of 3 boxes') % set_no)
                else:
                    sheet.row(row).height_mismatch = True
                    sheet.row(row).height = 42 * 20
                    sheet.write(row, 1, _('Notes:'), style)
                    sheet.write(row, 2, _('1. Pack this PO in sets (kits). This PO contains %s differents sets.\n'\
    '2. Each package must have special markings that are listed below\n'\
    '3. If there is more than 1  package for 1 set/kit, total amount of packages must be shown, eg.: 1 of 3 boxes') % set_no)
                row += 1
                if break_id:
                    sheet.write(row, 0, _('%s sets (kits) coming with this PO. Each set must have following Markings:')%set_no, style)
                    row += 1
                    sequence = 1
                    for key in do_mfg_id_list:
                        do_id_set = do_mfg_id_list[key]
                        sheet.write(row, 2, '#%s' % sequence)
                        if chinese:
                            sheet.write_merge(row, row, 3, 5,
                                              _('%s\n%s\n%s\n%s 项目 items,%s 件 pieces,') % (po.name, do_id_set['mfg_id'],
                                                                                      do_id_set['big_subassembly'],
                                                                                      do_id_set['items'],
                                                                                      do_id_set['pieces']))
                            sheet.write(row, 6, '1 set(kit)' \
                                        '1套')
                        else:
                            sheet.write_merge(row, row, 3, 5, _('%s\n%s\n%s\n%s items,%s pieces,')%(po.name, do_id_set['mfg_id'],
                                                                do_id_set['big_subassembly'],
                                                                do_id_set['items'],
                                                                do_id_set['pieces']))
                            sheet.write(row, 6, '1 set(kit)')
                        sequence += 1
                        row += 1
                row += 2
                sheet.write(row, 0, '#', style)
                if chinese:
                    sheet.write(row, 1, _('Level in BOM'), style)
                    sheet.write(row, 2, _('ERP #'), style)
                    sheet.write(row, 3, _('ERP项目' \
                                          'ERP Item'), style)
                    sheet.write(row, 4, _('零件号' \
                                          'Part Number'), style)
                    sheet.write(row, 5, _('描述' \
                                          'Description'), style)
                    sheet.write(row, 6, _('厚度' \
                                          'Thickness'), style)
                    sheet.write(row, 7, _('材料' \
                                          'Material'), style)
                    sheet.write(row, 8, _('重量' \
                                          'Weight'), style)
                    sheet.write(row, 9, _('BOM Qty for 1 机Unit'), style)
                    sheet.write(row, 10, _('Total Quantity'), style)
                else:
                    sheet.write(row, 1, _('Level in BOM'), style)
                    sheet.write(row, 2, _('ERP #'), style)
                    sheet.write(row, 3, _('ERP Item'), style)
                    sheet.write(row, 4, _('Part Number'), style)
                    sheet.write(row, 5, _('Description'), style)
                    sheet.write(row, 6, _('Thickness'), style)
                    sheet.write(row, 7, _('Material'), style)
                    sheet.write(row, 8, _('Weight'), style)
                    sheet.write(row, 9, _('BOM Qty/Qty for 1 Unit'), style)
                    sheet.write(row, 10, _('Total Quantity'), style)
                row += 1
                sequence = 0
                if not break_do:
                    for line in po.order_line:
                        sequence += 1
                        sheet.write(row, 0, sequence)
                        if line.bom_level:
                            sheet.write(row, 1, "%s" % line.bom_level)
                        if line.product_id:
                            sheet.write(row, 2, line.product_id.default_code)
                            sheet.write(row, 3, line.product_id.name)
                        if line.part_number:
                            sheet.write(row, 4, line.part_number)
                        sheet.write(row, 5, line.name)
                        if line.thickness:
                            sheet.write(row, 6, line.thickness)
                        if line.material:
                            sheet.write(row, 7, line.material)
                        #sheet.write(row, 8, line.weight)
                        if line.bom_qty:
                            sheet.write(row, 9, line.bom_qty)
                        sheet.write(row, 10, line.product_qty)
                        row = row + 1
                else:
                    po_line_obj = self.pool.get('purchase.order.line')
                    line_dicts = {}
                    for line in po.order_line:
                        if line.drawing_order_id:
                            if line.drawing_order_id.id not in line_dicts:
                                line_dicts.update({line.drawing_order_id.id: [line.id]})
                            else:
                                line_dicts[line.drawing_order_id.id].append(line.id)
                    for drawing_order_id, line_ids in line_dicts.iteritems():
                        previous_drawing_order_id = False
                        #total_weight = 0
                        total_bom_qty = 0
                        total_qty = 0
                        for line in po_line_obj.browse(cr, uid, line_ids, context=context):
                            mfg_name = ','.join([mfg_id.name for mfg_id in line.mfg_ids])
                            if not previous_drawing_order_id:
                                sheet.write(row, 0, _('Markings for this set:'),style)
                                sheet.write(row, 4, '%s\n%s\n%s'%(po.name, mfg_name, line.bigsubassembly_id.name),style)
                                row += 1
                                sheet.write(row, 0, _('DO#: [%s]%s')%(drawing_order_id, line.drawing_order_id.name), style)
                                row += 1
                            elif previous_drawing_order_id != drawing_order_id:
                                sheet.write(row, 7, _('TOTAL'), style)
                                #sheet.write(row, 8, total_weight, style)
                                sheet.write(row, 9, total_bom_qty, style)
                                sheet.write(row, 10, total_qty, style)
                                row += 1
                                #total_weight = 0
                                total_bom_qty = 0
                                total_qty = 0
                                sheet.write(row, 0, _('Markings for this set:'), style)
                                sheet.write(row, 4, '%s\n%s\n%s' % (po.name, mfg_name, line.bigsubassembly_id.name),
                                            style)
                                row += 1
                                sheet.write(row, 0, _('DO#: [%s]%s') % (drawing_order_id, line.drawing_order_id.name),
                                            style)
                                row += 1
                                sequence = 0
                            sequence += 1
                            sheet.write(row, 0, sequence)
                            if line.bom_level:
                                sheet.write(row, 1, "%s" % line.bom_level)
                            if line.product_id:
                                sheet.write(row, 2, line.product_id.default_code)
                                sheet.write(row, 3, line.product_id.name)
                            if line.part_number:
                                sheet.write(row, 4, line.part_number)
                            sheet.write(row, 5, line.name)
                            if line.thickness:
                                sheet.write(row, 6, line.thickness)
                            if line.material:
                                sheet.write(row, 7, line.material)
                            #sheet.write(row, 8, line.weight)
                            if line.bom_qty:
                                sheet.write(row, 9, line.bom_qty)
                            sheet.write(row, 10, line.product_qty)
                            total_qty += line.product_qty
                            total_bom_qty += line.bom_qty
                            row = row + 1
                            if line.drawing_order_id:
                                previous_drawing_order_id = drawing_order_id
                        if previous_drawing_order_id:
                            sheet.write(row, 7, _('TOTAL'), style)
                            #sheet.write(row, 8, total_weight, style)
                            sheet.write(row, 9, total_bom_qty, style)
                            sheet.write(row, 10, total_qty, style)
            file_name = u'Shipping-List-%s.xls' % ('-'.join(po_names))
            temp_xls_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xls')
            temp_xls_file_name = temp_xls_file.name
            temp_xls_file.close()
            workbook.save(temp_xls_file_name)
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/export/drawing_order_print_pdf?file_name=%s&file_data=%s' % (
                    file_name, temp_xls_file_name),
                'target': 'self',
            }
        elif report_type == 'pdf':
            datas = {
                'model': 'purchase.order',
                'ids': ids,
            }
            if break_do:
                if break_id:
                    return {
                        'type': 'ir.actions.report.xml',
                        'report_name': 'purchase.order.shipping_break_break_id',
                        'datas': datas,
                        'nodestroy': True,
                        'context': context
                    }
                return {
                    'type': 'ir.actions.report.xml',
                    'report_name': 'purchase.order.shipping_break',
                    'datas': datas,
                    'nodestroy': True,
                    'context': context
                }
            else:
                if break_id:
                    return {
                        'type': 'ir.actions.report.xml',
                        'report_name': 'purchase.order.shipping_normal_break_id',
                        'datas': datas,
                        'nodestroy': True,
                        'context': context
                    }
                return {
                    'type': 'ir.actions.report.xml',
                    'report_name': 'purchase.order.shipping_normal',
                    'datas': datas,
                    'nodestroy': True,
                    'context': context
                }
        return {'type': 'ir.actions.act_window_close'}

    def update_product_price(self, cr, uid, ids, context=None):
        req_obj = self.pool.get('pur.req')
        po_line_obj = self.pool.get('purchase.order.line')
        for po in self.browse(cr, uid, ids, context=context):
            if po.state == 'draft':
                for line in po.order_line:
                    if line.product_id and line.price_unit == 0.0:
                        price = req_obj.get_product_purchase_price(cr, uid, line.product_id, line.product_id.part_type,search_purchase_order=True)
                        if price > 0.0:
                            po_line_obj.write(cr, uid, [line.id],{'price_unit': price},context=context)

        return True

    def send_po_email(self, cr, uid, ids, context=None):
        if not type(ids) is list:
            ids = [ids]
        ir_model_data = self.pool.get('ir.model.data')
        template_id = False
        show_price = False
        try:
            if ids:
                po = self.browse(cr, uid, ids[0], context=context)
                if po.state in ['draft','sent']:
                    template_id = ir_model_data.get_object_reference(cr, uid, 'purchase', 'email_template_edi_purchase')[1]
                elif po.state in ['confirmed','approved']:
                    show_price = True
                    template_id = ir_model_data.get_object_reference(cr, uid, 'metro_mrp_drawing', 'email_template_purchase_confirm')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference(cr, uid, 'mail', 'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        ctx = dict(context)
        ctx.update({
            'default_model': 'purchase.order',
            'default_res_id': ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'show_price': show_price,
        })
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'name': 'Send Purchase Order Email',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    def po_email_wizard(self, cr, uid, ids, context=None):
        # mod_obj = self.pool.get('ir.model.data')
        # res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'view_pr_send_email_wizard')
        # res_id = res and res[1] or False
        return {
            'name': 'PO Email Wizard',
            'res_model': 'po.send.email.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            # 'view_id': [res_id],
            'target': 'new',
            'context': context,
        }

    def link_pr_wizard(self, cr, uid, ids, context=None):
        return {
            'name': 'Link PR Wizard',
            'res_model': 'link.po.to.pr.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            # 'view_id': [res_id],
            'target': 'new',
            'context': context,
        }

    # def write(self, cr, uid, ids, vals, context=None):
    #     if not type(ids) is list:
    #         ids = [ids]
    #     result = super(purchase_order, self).write(cr, uid, ids, vals, context=context)
    #     pur_req_obj = self.pool.get('pur.req')
    #     pur_req_obj.update_move_lines(cr, uid, ids, context=context)
    #     return result
    #
    # def create(self, cr, uid, vals, context=None):
    #     result = super(purchase_order, self).create(cr, uid, vals, context=context)
    #     if result:
    #         order = self.browse(cr, uid, result, context=context)
    #         # if order.req_id:
    #         #     req_history_obj = self.pool.get('pur.req.history')
    #         #     req_history_obj.create(cr, uid, {
    #         #         'pur_req_id': order.req_id.id,
    #         #         'user_id': uid,
    #         #         'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
    #         #         'content': _('Create Purchase Order %s' % order.name),
    #         #         'vals': '%s' % (vals),
    #         #     })
    #         pur_req_obj = self.pool.get('pur.req')
    #         pur_req_obj.update_move_lines(cr, uid, [result], context=context)
    #     return result
    #
    # def unlink(self, cr, uid, ids, context=None):
    #     req_ids = []
    #     for order in self.browse(cr, uid, ids, context=context):
    #         if order.req_id:
    #             req_ids.append(order.req_id.id)
    #     result = super(purchase_order, self).unlink(cr, uid, ids, context=context)
    #     pur_req_obj = self.pool.get('pur.req')
    #     pur_req_obj.update_move_lines_req(cr, uid, req_ids, context=context)
    #     return result

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #Add search support for MFG IDs
        for arg in args:
            if arg[0] == 'sale_product_ids':
                po_dict = {}
                ids = super(purchase_order,self).search(cr, user, [(arg[0],arg[1], arg[2])],context=context)
                for po_id in ids:
                    po_dict[po_id] = True
                po_line_obj = self.pool.get('purchase.order.line')
                line_ids = po_line_obj.search(cr, user, [('mfg_ids',arg[1], arg[2])], context=context)
                rows = po_line_obj.read(cr, user, line_ids, ['order_id'], context=context)
                for row in rows:
                    po_dict[row['order_id'][0]] = True
                arg[0] = 'id'
                arg[1] = 'in'
                arg[2] = po_dict.keys()
        return super(purchase_order,self).search(cr, user, args, offset, limit, order, context, count)

    def _get_drawing_order_line_ids(self, cr, uid, ids, context=None):
        pur_req_line_obj = self.pool.get('purchase.order.line')
        line_ids = pur_req_line_obj.search(cr, uid, [('order_id', 'in', ids), ('order_line_id', '!=', False)],
                                           context=context)
        line_datas = pur_req_line_obj.read(cr, uid, line_ids, ['order_line_id'], context=context)
        order_line_ids = [line['order_line_id'][0] for line in line_datas]
        return order_line_ids

    def print_pdf_zip(self, cr, uid, ids, context=None):
        order_line_ids = self._get_drawing_order_line_ids(cr, uid, ids, context=None)
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        return drawing_order_line_obj.print_pdf_zip(cr, uid, order_line_ids, context=context)

    def print_dxf(self, cr, uid, ids, context):
        order_line_ids = self._get_drawing_order_line_ids(cr, uid, ids, context=None)
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        return drawing_order_line_obj.print_dxf(cr, uid, order_line_ids, context=context)

    def action_po_report(self, cr, uid, ids, context=None):
        workbook = xlwt.Workbook()
        row = 0
        sheet = workbook.add_sheet('PO Database')
        REPORT_HEADERS = {
            'Sr.No' : 0,
            'Status' : 1,
            'PO NO' : 2,
            'PO Req Dt' : 3,
            'PO Approval Date' : 4,
            'Department' : 5,
            'PO approved By' : 6,
            'SKU Code' : 7,
            'Products': 8,
            'Qty' : 9,
            'Unit Rate' : 10,
            'Amount' : 11,
            'Expected Date' : 12,
            'Payment Status	Supplier' : 13,
            'Supplier':  14,
            'Supplier Product code' : 15,
            'Delivered Qty' : 16,
            'Supl. Unit Rate' : 17,
            'Supl. Amount' : 18,
            'Delivery Date' : 19,
            'Shipping Method' : 20,
            'Delivery Challan no' : 21,
            'Remarks' : 22
        }
        REPORT_HEADERS_NAMES = REPORT_HEADERS.keys()
        for header_name in REPORT_HEADERS_NAMES:
            sheet.write(row, REPORT_HEADERS[header_name], header_name)
        row += 1
        po_ids = self.search(cr, uid, [('state','not in', ['draft','rejected'])], context=context)
        sequence = 1
        for po in self.browse(cr, uid, po_ids, context=context):
            for line in po.order_line:
                sheet.write(row, REPORT_HEADERS['Sr.No'], sequence)
                sheet.write(row, REPORT_HEADERS['Status'], po.state)
                sheet.write(row, REPORT_HEADERS['PO NO'], po.name)
                sheet.write(row, REPORT_HEADERS['PO Req Dt'], po.date_order and po.date_order or '')
                sheet.write(row, REPORT_HEADERS['PO Approval Date'], po.date_approve and po.date_approve or '')
                sheet.write(row, REPORT_HEADERS['PO approved By'], po.validator.name)
                sheet.write(row, REPORT_HEADERS['Products'], line.product_id.name)
                sheet.write(row, REPORT_HEADERS['Qty'], line.product_qty)
                sheet.write(row, REPORT_HEADERS['Unit Rate'], line.price_unit)
                sheet.write(row, REPORT_HEADERS['Amount'], line.price_subtotal)
                sheet.write(row, REPORT_HEADERS['Expected Date'], line.date_planned and line.date_planned or '')
                sheet.write(row, REPORT_HEADERS['Supplier'], po.partner_id.name)
                sheet.write(row, REPORT_HEADERS['Supplier Product code'], line.supplier_prod_code)
                if line.move_ids:
                    delivery_qty = 0.0
                    delivery_date = ''
                    for move in line.move_ids:
                        if not delivery_date:
                            delivery_date = move.date
                        elif delivery_date < move.date:
                            delivery_date = move.date
                        delivery_qty += move.product_qty - move.return_qty
                    sheet.write(row, REPORT_HEADERS['Delivered Qty'], delivery_qty)
                    sheet.write(row, REPORT_HEADERS['Delivery Date'], delivery_date)
                row += 1
                sequence += 1
        file_name = u'PO Database-%s.xls' % datetime.utcnow()
        temp_xls_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xls')
        temp_xls_file_name = temp_xls_file.name
        temp_xls_file.close()
        workbook.save(temp_xls_file_name)

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/export/drawing_order_print_pdf?file_name=%s&file_data=%s' % (
                file_name, temp_xls_file_name),
            'target': 'self',
        }
    _columns = {
        'mo_id': fields.many2one('mrp.production', 'Manufacturer Order'),
        'unit': fields.related('mo_id', 'product_id', type='many2one', relation='product.product', string='Unit',
                               readonly=True,store=True),
        'sale_product_ids': fields.related('mo_id', 'mfg_ids', type="many2many", relation="sale.product",
                                           string="Unit IDs"),
        'bigsubassembly_id': fields.related('req_id','bigsubassembly_id',type='many2one',relation='product.product',
        string = 'Big Sub Assembly', readonly = True, store = True),
        'pr_type': fields.related('req_id','pr_type', type='selection', selection=PR_TYPES, string='PR Type',store=True),
        'description': fields.char('Description', size=128),
        'pr_created_date': fields.related('req_id','date_create', type='date', string='PR Created Date'),
        'pr_requested_date': fields.related('req_id', 'date_request', type='date', string='PR Requested Date'),
        'request_date': fields.date('Requested Date', help='Date, when goods need to arrive in our warehouse. filled by Requester'),
        'delivery_date': fields.date('Delivery date (ETA)', help='Date, when goods plan to arrive in our warehouse. filled by Purchaser'),
    }
purchase_order()

class purchase_order_line(osv.osv):
    _inherit = "purchase.order.line"

    # def write(self, cr, uid, ids, vals, context=None):
    #     if not type(ids) is list:
    #         ids = [ids]
    #     result = super(purchase_order_line, self).write(cr, uid, ids, vals, context=context)
    #     pur_req_obj = self.pool.get('pur.req')
    #     po_ids = []
    #     for line in self.browse(cr, uid, ids,context=context):
    #         if not line.order_id.id in po_ids:
    #             po_ids.append(line.order_id.id)
    #     pur_req_obj.update_move_lines(cr, uid, po_ids, context=context)
    #     return result
    #
    # def create(self, cr, uid, vals, context=None):
    #     result = super(purchase_order_line, self).create(cr, uid, vals, context=context)
    #     pur_req_obj = self.pool.get('pur.req')
    #     if result:
    #         line =  self.browse(cr, uid, result, context=context)
    #         po_ids = [line.order_id.id]
    #         pur_req_obj.update_move_lines(cr, uid, po_ids, context=context)
    #     return result
    #
    # def unlink(self, cr, uid, ids, context=None):
    #     po_ids = []
    #     for line in self.browse(cr, uid, ids, context=context):
    #         if not line.order_id.id in po_ids:
    #             po_ids.append(line.order_id.id)
    #     result = super(purchase_order_line, self).unlink(cr, uid, ids, context=context)
    #     pur_req_obj = self.pool.get('pur.req')
    #     pur_req_obj.update_move_lines(cr, uid, po_ids, context=context)
    #     return result

    def move_po_lines(self, cr, uid, ids, context=None):
        return {
            'name': 'Move PO Lines Wizard',
            'res_model': 'move.po.line.wizard',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }
    def onchange_lead(self, cr, uid, ids, change_type, changes_value, date_order, context=None):
        res = super(purchase_order_line, self).onchange_lead(cr, uid, ids, change_type, changes_value, date_order, context=context)
        if change_type == 'date_planned':
            expected_date = changes_value
            lines = self.browse(cr, uid, ids, context=context)
            pur_req_line_obj = self.pool.get('pur.req.line')
            for line in lines:
                if line.req_line_id:
                    if not line.req_line_id.expected_date:
                        pur_req_line_obj.write(cr, uid, [line.req_line_id.id],{'expected_date': expected_date})
                    else:
                        pur_req_line_obj.write(cr, uid, [line.req_line_id.id], {'expected_date': max(expected_date, line.req_line_id.expected_date)})
        return res

    def _has_pdf_dxf(self, cr, uid, ids, field_names=None, arg=False, context=None):
        if not field_names:
            field_names = []
        if context is None:
            context = {}
        result = {}
        for id in ids:
            result[id] = {}.fromkeys(field_names, 0)
        for order_line in self.browse(cr, uid, ids):
            if order_line.drawing_file_name:
                result[order_line.id].update({'has_pdf': True,
                                       })
            if order_line.dxf_file_name:
                result[order_line.id].update({'has_dxf': True,
                                       })
        return result

    _columns = {
        'thickness': fields.related('product_id','thickness',string='Thickness',type='char',size=128,readonly=True),
        "order_line_id": fields.many2one('drawing.order.line', string='Drawing Order Line', readonly=True),
        'drawing_file_name': fields.related('order_line_id', 'drawing_file_name', string='Drawing PDF Name',
                                            type='char', size=64, readonly=True),
        'drawing_file': fields.related('order_line_id', 'drawing_file', string="Drawing PDF", type="binary",
                                       readonly=True),
        'has_pdf': fields.function(_has_pdf_dxf, string='PDF?', type='boolean', readonly=True, multi="pdf_dxf"),

        'dxf_file_name': fields.related('order_line_id', 'dxf_file_name', string='Drawing DXF Name',
                                        type='char', size=64, readonly=True),
        'drawing_download': fields.char('Drawing PDF', size=128, readonly=True),
        'dxf_file': fields.related('order_line_id', 'dxf_file', string="Drawing DXF", type="binary",
                                   readonly=True),
        'has_dxf': fields.function(_has_pdf_dxf, string='DXF?', type='boolean', readonly=True, multi="pdf_dxf"),
        'part_number': fields.related('order_line_id','part_number', string='Part Number', type='char', size=128, readonly=True),
        "material": fields.related('order_line_id', 'material', string="Material", type='char', size=128, readonly=True),
        "standard": fields.related('order_line_id','standard', string="Standard", type='char', size=128, readonly=True),
        'drawing_order_id': fields.related('order_line_id', 'order_id', type="many2one", relation="drawing.order",
                                           string="Drawing Order", readonly=True),
        'bigsubassembly_id': fields.related('drawing_order_id', 'product_id', type="many2one", relation="product.product",
                                            string= 'Big Sub Assembly',readonly=True),
        'bom_qty': fields.related('order_line_id', 'bom_qty', string="Bom Qty", type='integer', readonly=True),
        'bom_level': fields.related('order_line_id', 'item_no', string="Bom Level", type='char', size=50, readonly=True),
    }
    _defaults = {
        'drawing_download': 'drawing_file',
    }
purchase_order_line()