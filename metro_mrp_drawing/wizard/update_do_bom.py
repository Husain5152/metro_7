# -*- coding: utf-8 -*-
import time
import os
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro import utils
from openerp.addons.metro_mrp_drawing.drawing_order import PART_TYPE_SELECTION
import xlrd
import StringIO

class update_do_bom(osv.osv_memory):
    _name = 'update.do.bom'
    _description = 'Update DO BOM'
    _columns = {
        'do_id': fields.many2one('drawing.order','Drawing Order',required=True),
        'bom_file_name': fields.char('BOM File Name', size=64),
        'bom_file': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file, string="BOM File", type="binary", multi="_get_file",required=True),
    }
    def read_bom_lines_from_files(self, bom_file):
        bom_lines =  []
        drawing_order_obj = self.pool.get('drawing.order')
        inputStr = StringIO.StringIO()
        inputStr.write(bom_file.decode('base64'))
        workbook = xlrd.open_workbook(file_contents=inputStr.getvalue())
        worksheet = workbook.sheet_by_index(0)
        row = 2
        while row < worksheet.nrows:
            bom_line = drawing_order_obj.read_bom_line(worksheet=worksheet, row=row)
            if bom_line['part_name']:
                item_no = bom_line['item_no']
                erp_no = bom_line['erp_no']
                part_name = bom_line['part_name']
                bom_qty = int(bom_line['bom_qty'])
                part_type = bom_line['part_type']
                work_steps = bom_line['work_steps']
                bom_lines.append({
                    'item_no': item_no,
                    'erp_no': erp_no,
                    'part_name': part_name,
                    'part_type': part_type,
                    'work_steps': work_steps,
                    'bom_qty': bom_qty,
                })
            row += 1
        return bom_lines

    def do_update(self, cr, uid, ids, context=None):
        update_do_bom = self.browse(cr, uid, ids, context)[0]
        #1. Check if can update this bom file
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        task_obj = self.pool.get('project.task')
        task_line_obj = self.pool.get('project.task.line')
        order = update_do_bom.do_id
        if order.state in ['draft','cancel']:
            raise osv.except_osv(_('Error!'), _('Drawing order is in draft or cancel state. Please edit it to update BOM File!.'))
        #new_name = update_do_bom.bom_file_name.split('.')[0]
        new_name = os.path.splitext(update_do_bom.bom_file_name)[0]
        error_logs = drawing_order_obj.check_bom_file_content(cr, uid, order.name, new_name,
                                                              update_do_bom.bom_file)
        if len(error_logs) > 0:
            raise osv.except_osv(_('Error!'),
                                 _('BOM File error, please check bom file!.'))
        modify_value_keys = []
        old_bom_values = self.read_bom_lines_from_files(order.bom_file)
        new_bom_values = self.read_bom_lines_from_files(update_do_bom.bom_file)
        if len(old_bom_values) != len(new_bom_values):
            raise osv.except_osv(_("Error!"), _('You are not allow to add/remove new part: %s to bom!'))
        for key in range(0,len(old_bom_values)):
            old_value = old_bom_values[key]
            new_value = new_bom_values[key]
            if old_value['part_name'] != new_value['part_name']:
                raise osv.except_osv(_("Error!"),
                                     _('Part number %s not match the old one') % new_value['part_name'])
            if old_value['part_type'] != new_value['part_type']:
                raise osv.except_osv(_("Error!"),
                                     _('Part type of part %s not match the old one') % new_value['part_name'])
            if old_value['work_steps'] != new_value['work_steps']:
                raise osv.except_osv(_("Error!"),
                                     _('Work steps of part %s not match the old one') % new_value['part_name'])
            if  new_value['bom_qty'] < old_value['bom_qty']:
                raise osv.except_osv(_("Error!"),
                                     _('You are not allow to decrease the quantity of part: %s') % new_value['part_name'])
            elif new_value['bom_qty'] > old_value['bom_qty']:
                modify_value_keys.append(key)
        #2. Update this bom file to DO
        big_assembly_qty = drawing_order_obj.get_big_subassembly_qty(cr, uid, order)
        for key in modify_value_keys:
            new_value = new_bom_values[key]
            old_value = old_bom_values[key]
            new_bom_qty = new_value['bom_qty']
            work_steps = new_value['work_steps']
            need_qty = new_bom_qty * big_assembly_qty
            steps = drawing_order_obj.split_work_steps(work_steps)
            vals = {'status': _('On Working')}
            for step in steps:
                vals.update({'%s_need_qty' % step : need_qty})
            vals.update({'%s_prepare_qty' % step[0]: need_qty})
            drawing_order_line_obj.write(cr, uid, [old_value['line_id']], vals)
            task_ids = task_obj.search(cr, uid, [('drawing_order_id','=',order.id),
                                                 ('dept_code','in',steps)])
            task_line_ids = task_line_obj.search(cr, uid, [('task_id','in',task_ids),
                                                           ('product_id','=', old_value['product_id'])])
            task_line_obj.write(cr, uid, task_line_ids, {
                'need_qty': need_qty,
            })
            first_step_task_ids = task_obj.search(cr, uid, [('drawing_order_id','=',order.id),
                                                 ('dept_code','=',steps[0])])
            first_step_task_line_ids = task_line_obj.search(cr, uid, [('task_id','in',first_step_task_ids),
                                                           ('product_id','=',old_value['product_id'])])
            task_line_obj.write(cr, uid, first_step_task_line_ids, {
                'prepare_qty': need_qty,
            })
            task_obj.update_task_state(cr, uid, task_ids, open_task=True)
        drawing_order_obj.write(cr, uid, [order.id],{
            'bom_file': update_do_bom.bom_file
        })
        return True
update_do_bom()