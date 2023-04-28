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
from openerp.addons.base_status.base_stage import base_stage
from openerp import netsvc
import time

class warehouse_task_report(osv.osv):
    _inherit = ['mail.thread']
    _name = "warehouse.task.report"
    _description = "Warehouse Task Report"

    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        result = []
        for report in self.browse(cr, user, ids, context=context):
            result.append((report.id,'[%s] %s'%(report.id , report.dept_id.name)))
        return result

    def onchange_task_id(self, cr, uid, ids, task_id, context=None):
        result = {}
        if task_id:
            task_obj = self.pool.get('project.task')
            task = task_obj.browse(cr, uid, task_id, context=context)
            mfg_ids = [mfg_id.id for mfg_id in task.mfg_ids]
            #TODO search state based on task_id
            result.update(
                {
                    'mo_id': task.production_id and task.production_id.id or False,
                    'dept_id': task.dept_id and task.dept_id.id or False,
                    'unit': task.product and task.product.id or False,
                    'big_subassembly_id': task.big_subassembly_id and task.big_subassembly_id.id or False,
                    'workorder_id': task.workorder_id and task.workorder_id.id or False,
                    'task_create_date': task.create_date,
                    'date_deadline': task.date_deadline,
                    'mfg_ids': mfg_ids,
                }
            )
            report_line_vals = []
            for line in task.task_lines:
                if line.transfer_qty < line.done_qty or line.prepare_qty < line.need_qty:
                    report_line_vals.append({
                        'task_line_id': line.id,
                        'item_no': line.item_no,
                        'product_id': line.product_id.id and line.product_id.id or False,
                        'part_number': line.part_number,
                        'order_line_id': line.order_line_id and line.order_line_id.id or False,
                        'qty_onhand': line.product_id.qty_onhand,
                        'reserved_qty': line.product_id.reserved_qty,
                        'qty_in': line.product_id.qty_in,
                        'qty_out': line.product_id.qty_out,
                        'qty_available': line.product_id.qty_available,
                        'prepare_qty': 0,
                        'done_qty': 0,
                        'need_qty': line.need_qty,
                        'current_prepare_qty': line.prepare_qty,
                        'current_done_qty': line.done_qty,
                        'state': 'draft',
                    })
            if report_line_vals:
                result.update({'report_lines': report_line_vals})
        return {'value': result}
    def _set_state(self, cr, uid, ids, state, context=None):
        self.write(cr, uid, ids, {'state': state}, context=context)
        report_line_obj = self.pool.get('warehouse.task.report.line')
        line_ids = report_line_obj.search(cr, uid, [('report_id', 'in', ids)], context=context)
        report_line_obj.write(cr, uid, line_ids, {'state': state}, context=context)
        return True

    def update_quantity_to_task(self,cr, uid, ids, context=None):
        task_line_obj = self.pool.get('project.task.line')
        task_obj = self.pool.get('project.task')
        task_ids = []
        for report in self.browse(cr, uid, ids, context=context):
            task_ids.append(report.task_id.id)
            for line in report.report_lines:
                task_line = line.task_line_id
                if task_line:
                    if line.done_qty != 0 or line.prepare_qty != 0:
                        task_line_obj.write(cr, uid, [task_line.id],{
                            'done_qty': line.done_qty,
                            'prepare_qty': line.prepare_qty
                        })
        if task_ids:
            task_obj.update_task_state(cr, uid, task_ids, True, context=context)
        return True

    def action_fill_qty_prepare(self, cr, uid, ids, context=None):
        report_line_obj = self.pool.get('warehouse.task.report.line')
        for report in self.browse(cr, uid, ids, context=context):
            for line in report.report_lines:
                if line.task_line_id:
                    if line.task_line_id.prepare_qty < line.task_line_id.need_qty:
                        report_line_obj.write(cr, uid, [line.id],
                                              {'prepare_qty':line.task_line_id.need_qty - line.task_line_id.prepare_qty},
                                              context=context)
        return True

    def action_fill_qty_transfered(self, cr, uid, ids, context=None):
        report_line_obj = self.pool.get('warehouse.task.report.line')
        for report in self.browse(cr, uid, ids, context=context):
            for line in report.report_lines:
                if line.done_qty < line.prepare_qty:
                    report_line_obj.write(cr, uid, [line.id],
                                          {
                                              'done_qty': line.prepare_qty},
                                          context=context)
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        self._set_state(cr, uid, ids, 'cancel', context)
        return True

    def action_confirm(self, cr, uid, ids, context=None):
        for report in self.browse(cr, uid, ids, context=context):
            if report.task_id.state in ['cancelled', 'done']:
                raise osv.except_osv(_('Error!'), _('Can not confirm! A task is not in working states!'))

        # Update done quantity to project task
        result = self.update_quantity_to_task(cr, uid, ids, context=context)
        if not result:
            raise osv.except_osv(_('Error!'), _('Can not confirm task report!'))
        self._set_state(cr, uid, ids, 'confirmed', context)
        return True

    def action_print_fulllist(self, cr, uid, ids, context=None):
        if not type(ids) is list:
            ids = [ids]
        task_ids = []
        for report in  self.browse(cr, uid, ids, context=context):
            task_ids.append(report.task_id.id)
        task_obj = self.pool.get('project.task')
        return task_obj.print_warehouse_selected(cr, uid, task_ids, 'fulllist', context=context)

    def action_print_missing(self, cr, uid, ids, context=None):
        if not type(ids) is list:
            ids = [ids]
        task_ids = []
        for report in  self.browse(cr, uid, ids, context=context):
            task_ids.append(report.task_id.id)
        task_obj = self.pool.get('project.task')
        return task_obj.print_warehouse_selected(cr, uid, task_ids, 'missing', context=context)

    def action_print_transfer(self, cr, uid, ids, context=None):
        if not type(ids) is list:
            ids = [ids]
        task_ids = []
        for report in  self.browse(cr, uid, ids, context=context):
            task_ids.append(report.task_id.id)
        task_obj = self.pool.get('project.task')
        return task_obj.print_warehouse_selected(cr, uid, task_ids, 'transfer', context=context)

    def action_partial_transfer(self, cr, uid, ids, context=None):
        reports = self.browse(cr, uid, ids ,context=context)
        task_id = False
        if reports:
            task_id = reports[0].task_id.id
        if task_id:
            new_context = {'active_id': task_id, 'active_model': 'project.task'}
            mod_obj = self.pool.get('ir.model.data')
            res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'view_warehouse_partial_transfer_wizard')
            res_id = res and res[1] or False
            return {
                'name': _('Warehouse Partial Transfer Wizard'),
                'view_type':'form',
                'view_mode':'form',
                'res_model':'task.partial.transfer.wizard',
                'view_id':res_id,
                'type':'ir.actions.act_window',
                'target':'new',
                'context':new_context,
            }
        return True

    def do_transfer(self, cr, uid, ids, context=None):
        mr_names = []
        task_obj = self.pool.get('project.task')
        for report_id in self.browse(cr, uid, ids, context=context):
            task_line_ids = [line.task_line_id.id for line in report_id.report_lines]
            mr_names.append(task_obj.do_partial_transfer(cr, uid, report_id.task_id.id, task_line_ids, context=context))
        if not mr_names:
            return self.pool.get('warning').info(cr, uid, title='Information',
                                                 message=_("Nothing to transfer"))
        else:
            return self.pool.get('warning').info(cr, uid, title='Information', message= _("Material Request (%s) have been created")% (','.join(mr_names),))


    def action_full_transfer(self, cr, uid, ids, context=None):
        return self.do_transfer(cr, uid, ids, context=context)

    def _check_fill_done_qty(self, cr, uid, ids, name=None, args=False, context=None):
        if context is None:
            context={}
        res = {}
        for report in self.browse(cr, uid, ids, context=context):
            res[report.id] = False
            for report_line in report.report_lines:
                if report_line.prepare_qty > 0 and report_line.prepare_qty > report_line.done_qty:
                    res[report.id] = True
                    break
        return res

    _columns = {
        'task_id': fields.many2one('project.task', 'Task',ondelete='cascade',required=True,readonly=True),
        'drawing_order_id': fields.related('task_id', "drawing_order_id",type='many2one',relation='drawing.order', string='Drawing Order',
                                           readonly=True),
        'req_id': fields.related('drawing_order_id', 'req_id', type='many2one', relation='pur.req', string='Generated PR', readonly=True),
        'req_o_id': fields.related('drawing_order_id', 'req_o_id', type='many2one', relation='pur.req', string='Generated PR-O', readonly=True),
        'dept_id': fields.related('task_id','dept_id', type='many2one', relation='hr.department', string='Department', readonly=True
                                  ),
        'workorder_id': fields.related('task_id','workorder_id', type='many2one', relation='mrp.production.workcenter.line',
                                       string='Work Order',readonly=True),
        'mo_id': fields.related('task_id','production_id',type='many2one',relation='mrp.production',
                                string='Manufacture Order',readonly=True),
        'unit': fields.related('task_id','product',type='many2one',relation='product.product',
                                string='Unit', readonly=True),
        'mfg_ids': fields.related('task_id', 'mfg_ids', type='many2many', relation='sale.product',
                                string='MFG IDs',readonly=True),
        'big_subassembly_id': fields.related('task_id', 'big_subassembly_id', type='many2one', relation='product.product',
                                string='Big Sub Assembly',readonly=True),
        'task_date_create': fields.related('task_id','create_date', type='date',string='Task Issued Date',readonly=True),

        'date_create': fields.date('Date Create', readonly=True),
        'date_deadline': fields.related('task_id', 'date_deadline', type='date', string='Task Deadline',readonly=True),
        'creator': fields.many2one('res.users','Create User',readonly=True),
        'can_fill_done_qty': fields.function(_check_fill_done_qty, type='boolean', string='Have prepare qty',
                                            readonly=True),
        'report_lines': fields.one2many('warehouse.task.report.line','report_id',string='Report Lines',
                                        readonly=True,states={'draft': [('readonly', False)]}),
        'state': fields.selection([('draft','Draft'),
                                   ('preparing','Preparing'),
                                   ('missing','Missing'),
                                   ('partial_transfered','Partial Transfered'),
                                   ('done','Done'),
                                   ('cancel','Cancelled')
                                   ],track_visibility='onchange',string='State')
    }
    _defaults = {
        'state': 'draft',
        'creator': lambda self, cr, uid, c: uid,
        'date_create': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
    }
    _order = "id desc"
class warehouse_task_report_line(osv.osv):
    _name = "warehouse.task.report.line"
    _description = "Warehouse Task Report Line"

    def update_task_state(self, cr, uid, ids, context=None):

        return True

    def write(self, cr, uid, ids, vals, context=None):
        if not type(ids) is list:
            ids = [ids]
        report_ids = {}
        if 'prepare_qty' in vals:
            prepare_qty = vals['prepare_qty']
            for line in self.browse(cr, uid, ids):
                report_ids.update({line.report_id.id : True})
                if prepare_qty > line.need_qty:
                    raise osv.except_osv(_('Error!'),
                                         _('%s : prepare quantity must <= need quantity!') % (line.task_line_id.name,))
                if line.transfer_qty > 0 and line.transfer_qty < prepare_qty:
                    raise osv.except_osv(_('Error!'),
                                         _('%s : prepare quantity must >= transfered quantity!') % (line.task_line_id.name,))
        if 'done_qty' in vals:
            done_qty = vals['done_qty']
            for line in self.browse(cr, uid, ids):
                report_ids.update({line.report_id.id: True})
                prepare_qty = line.prepare_qty
                if 'prepare_qty' in vals:
                    prepare_qty = vals['prepare_qty']
                if done_qty > line.need_qty:
                    raise osv.except_osv(_('Error!'), _('%s : done quantity must <= need quantity!')%(line.task_line_id.name,))
                if done_qty > prepare_qty:
                    raise osv.except_osv(_('Error!'),
                                         _('%s : done quantity must <= prepare_qty quantity!') % (line.task_line_id.name,))
                if line.transfer_qty > 0 and line.transfer_qty > done_qty:
                    raise osv.except_osv(_('Error!'),
                                         _('%s : done quantity must >= transfered quantity!') % (line.task_line_id.name,))

        result = super(warehouse_task_report_line,self).write(cr, uid, ids, vals, context=context)
        #Update task quantity
        report_obj = self.pool.get('warehouse.task.report')
        report_obj.update_quantity_to_task(cr, uid, report_ids.keys(), context=context)
        #report_obj.update_task_state(cr, uid, report_ids.keys(), context=context)
        return result

    def create(self, cr, uid, vals, context=None):
        created_id = super(warehouse_task_report_line, self).create(cr, uid, vals, context=context)
        line = self.browse(cr, uid, created_id, context=context)
        if line.report_id:
            sequence = 1
            cr.execute('SELECT  COALESCE(MAX(sequence),0) as sequence FROM warehouse_task_report_line WHERE report_id = %s',(line.report_id.id,))
            result = cr.dictfetchall()
            if result:
                sequence = result[0]["sequence"] + 1
            self.write(cr, uid, [created_id],{'sequence': sequence})
        return created_id

    def _get_stock_level(self, cr, uid, ids, name=None, args=False, context=None):
        result = {}
        for line in self.browse(cr, uid, ids, context=context):
            result.update({line.id: line.qty_available - line.need_qty})
        return result

    def _get_po_infor(self, cr, uid, ids, name=None, args=False, context=None):
        if context is None:
            context={}
        res = {}
        po_line_obj = self.pool.get('purchase.order.line')
        for report_line in self.browse(cr, uid, ids, context=context):
            order_infors = []
            if report_line.order_line_id:
                po_line_ids = po_line_obj.search(cr, uid, [('order_line_id', '=', report_line.order_line_id.id)],
                                                 context=context)
                po_lines = po_line_obj.browse(cr, uid, po_line_ids, context=context)
                for po_line in po_lines:
                    order_infors.append('%s@%s'%(po_line.product_qty, po_line.order_id.name))
            res[report_line.id] = ';'.join(order_infors)

        return res

    # def _get_po_ids(self, cr, uid, ids, name=None, args=False, context=None):
    #     if context is None:
    #         context = {}
    #     res = {}
    #     for id in ids:
    #         res[id] = []
    #
    #     po_line_obj = self.pool.get('purchase.order.line')
    #     for report_line in self.browse(cr, uid, ids, context=context):
    #         po_line_ids = po_line_obj.search(cr, uid, [('order_line_id','=',report_line.order_line_id.id)], context=context)
    #         po_lines = po_line_obj.read(cr, uid, po_line_ids, ['order_id'], context=context)
    #         order_ids = {}
    #         for po_line in po_lines:
    #             order_ids.update({po_line['order_id']: True})
    #         for order_id in order_ids.keys():
    #             res[report_line.id].append(order_id)
    #
    #     return res

    def _get_color(self, cr, uid, ids, name=None, args=False, context=None):
        result = {}
        for line in self.browse(cr, uid, ids, context=context):
            color = 'black'
            if line.transfer_qty > 0:
                if line.transfer_qty == line.done_qty:
                    color = 'green'
                else:
                    color = 'yellow'
            elif line.qty_available < line.need_qty:
                color = 'red'
            result.update({line.id : color})
        return result

    def reserved_infor(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        product_ids = []
        for report_line in self.browse(cr, uid, ids, context=context):
            product_ids.append(report_line.product_id.id)
        if product_ids:
            pr_reserved_obj = self.pool.get('pur.req.reserve')
            return pr_reserved_obj.view_reserved_infor_products(cr, uid, ids, context=context)
        return False

    _columns = {
        'report_id': fields.many2one('warehouse.task.report',ondelete='cascade',string='Warehouse Task Report'),
        'sequence': fields.integer('#',readonly=True),
        'task_line_id': fields.many2one('project.task.line','Task line',readonly=True),
        'employee': fields.many2one('hr.employee', 'Employee'),
        'item_no': fields.related('task_line_id','item_no',type='char',readonly=True,string='Item No'),
        'part_type': fields.related('task_line_id','part_type',type='char',readonly=True,string="Part Type"),
        'erp_no': fields.related('task_line_id','erp_no',type='char',readonly=True,string="ERP #"),
        'product_id': fields.related('task_line_id', 'product_id', type='many2one', relation='product.product',
                                      string='Product'),
        'storage_cell': fields.related('product_id','loc_pos_code',type='char', size=16, string='Storage Cell', readonly=True),
        'part_number': fields.related('task_line_id', 'part_number', type='char', readonly=True, string='Part Number'),
        'order_line_id': fields.related('task_line_id', 'order_line_id', type='many2one', relation='drawing.order.line',
                                        string='Drawing Order Line',readonly=True),
        'drawing_file_name': fields.related('order_line_id','drawing_file_name',string='Drawing PDF Name', type='char', size=128, readonly=True),
        'drawing_file': fields.related('order_line_id','drawing_file', string="Drawing PDF", type="binary",readonly=True),
        'drawing_download': fields.char('Drawing PDF', size=128, readonly=True),
        'qty_onhand': fields.related('product_id','qty_onhand',type='float',string='Onhand Qty',readonly=True),
        'reserved_qty': fields.related('product_id', 'reserved_qty', type='float', string='Reserved Qty', readonly=True),
        'qty_in': fields.related('product_id', 'qty_in', type='float', string='Incoming', readonly=True),
        'qty_out': fields.related('product_id', 'qty_out', type='float', string='Outgoing', readonly=True),
        'qty_available': fields.related('product_id', 'qty_available', type='float', string='Available Qty', readonly=True),
        'prepare_qty': fields.integer('Prepare Qty'),
        'done_qty': fields.integer('Transfer Qty'),
        'transfer_qty': fields.related('task_line_id','transfer_qty',type='integer',string='Transfered Qty',readonly=True),
        'need_qty': fields.related('task_line_id','need_qty',type='integer',string='Need Qty',readonly=True),
        'current_prepare_qty': fields.related('task_line_id', 'prepare_qty', type='integer', string='Current Prepare Qty'),
        'current_done_qty': fields.related('task_line_id','done_qty',type='integer',string='Current Done Qty'),
        'stock_level': fields.function(_get_stock_level,type='float',string='Stock Level',readonly=True),
        'color': fields.function(_get_color, type='char', size=50, string='Color', readonly=True),
        #'po_ids': fields.function(_get_po_ids, type='many2many', relation='purchase.order', readonly=True),
        'po_info': fields.function(_get_po_infor, type='char', string='PO Quantity',size=128, readonly=True),

        'state': fields.selection([('draft','Draft'),
                                   ('preparing','Preparing'),
                                   ('missing','Missing'),
                                   ('partial_transfered','Partial Transfered'),
                                   ('done','Done'),
                                   ('cancel','Cancelled')
                                   ],track_visibility='onchange',string='State',readonly=True)
    }

    _defaults = {
        'state': 'draft',
        'sequence': 0,
        'drawing_download': 'drawing_file',
    }
    _order = "sequence"