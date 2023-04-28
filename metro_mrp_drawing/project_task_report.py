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

class project_mfgtask_report(osv.osv):
    _inherit = ['mail.thread']
    _name = "project.mfgtask.report"
    _description = "Project Mfg Task Report"

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

    def _get_total_employee_kpi(self, cr, uid, ids, names, args, context=None):
        result = {}
        for report in self.browse(cr, uid, ids, context=context):
            result.update({report.id: report.emp1_kpi + report.emp2_kpi + report.emp3_kpi +
                                      report.emp4_kpi + report.emp5_kpi})

        return result

    def _set_state(self, cr, uid, ids, state, context=None):
        self.write(cr, uid, ids, {'state': state}, context=context)
        report_line_obj = self.pool.get('project.mfgtask.report.line')
        line_ids = report_line_obj.search(cr, uid, [('report_id', 'in', ids)], context=context)
        report_line_obj.write(cr, uid, line_ids, {'state': state}, context=context)
        return True

    def update_quantity_to_task(self,cr, uid, ids, context=None):
        updated_task_line_ids = []
        updated_task_ids = []
        task_line_obj = self.pool.get('project.task.line')
        project_task_obj = self.pool.get('project.task')
        for report in self.browse(cr, uid, ids, context=context):
            for line in report.report_lines:
                task_line = line.task_line_id
                task_id = task_line.task_id
                if task_line:
                    if line.done_qty != 0:
                        new_done_qty = line.done_qty + task_line.done_qty
                        if new_done_qty > task_line.prepare_qty or new_done_qty > task_line.need_qty:
                            raise osv.except_osv(_('Error!'), _('%s : done quantity is not correct !')%(task_line.name,))
                        task_line_obj.write(cr, uid, [task_line.id],{
                            'done_qty': new_done_qty,
                        })
                        updated_task_line_ids.append(task_line.id)
                updated_task_ids.append(task_id.id)
        project_task_obj.move_part_when_task_line_updated(cr, uid, updated_task_ids, updated_task_line_ids)
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        self._set_state(cr, uid, ids, 'cancel', context)
        return True

    def action_confirm(self, cr, uid, ids, context=None):
        for report in self.browse(cr, uid, ids, context=context):
            for line in report.report_lines:
                if line.task_id.state in ['draft', 'cancelled', 'done']:
                    raise osv.except_osv(_('Error!'), _('Can not confirm! A task is not in working states!'))
        # Update done quantity to project task
        result = self.update_quantity_to_task(cr, uid, ids, context=context)
        if not result:
            raise osv.except_osv(_('Error!'), _('Can not confirm task report!'))
        self._set_state(cr, uid, ids, 'confirmed', context)
        return True

    _columns = {
        'dept_id': fields.many2one('hr.department','Department',readonly=True,states={'draft': [('readonly', False)]}),
        'type': fields.selection([
            ('worker','Worker'),
            ('team','Team'),
        ], string='Type',readonly=True,states={'draft': [('readonly', False)]}),
        'date_create': fields.date('Date Create',readonly=True),
        'creator': fields.many2one('res.users','Create User',readonly=True),
        'emp1': fields.many2one('hr.employee', 'Employee #1',readonly=True,states={'draft': [('readonly', False)]}),
        'emp2': fields.many2one('hr.employee', 'Employee #2',readonly=True,states={'draft': [('readonly', False)]}),
        'emp3': fields.many2one('hr.employee', 'Employee #3',readonly=True,states={'draft': [('readonly', False)]}),
        'emp4': fields.many2one('hr.employee', 'Employee #4',readonly=True,states={'draft': [('readonly', False)]}),
        'emp5': fields.many2one('hr.employee', 'Employee #5',readonly=True,states={'draft': [('readonly', False)]}),
        'emp1_kpi': fields.float('Employee #1 KPI',readonly=True,states={'draft': [('readonly', False)]}),
        'emp2_kpi': fields.float('Employee #2 KPI',readonly=True,states={'draft': [('readonly', False)]}),
        'emp3_kpi': fields.float('Employee #3 KPI',readonly=True,states={'draft': [('readonly', False)]}),
        'emp4_kpi': fields.float('Employee #4 KPI',readonly=True,states={'draft': [('readonly', False)]}),
        'emp5_kpi': fields.float('Employee #5 KPI',readonly=True,states={'draft': [('readonly', False)]}),
        'total_kpi': fields.function(_get_total_employee_kpi,type='float',string='Total KPI'),
        'report_lines': fields.one2many('project.mfgtask.report.line','report_id',string='Report Lines',readonly=True,states={'draft': [('readonly', False)]}),
        'state': fields.selection([('draft','Draft'),
                                   ('confirmed','Confirmed'),
                                   ('cancel','Cancelled')
                                   ],track_visibility='onchange',string='State')
    }
    _defaults = {
        'state': 'draft',
        'creator': lambda self, cr, uid, c: uid,
        'date_create': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
    }

class project_mfgtask_report_line(osv.osv):
    _name = "project.mfgtask.report.line"
    _description = "Project Mfg Task Report Line"

    def onchange_task_line_id(self, cr, uid, ids, task_line_id, context=None):
        vals = {}
        if task_line_id:
            task_line = self.pool.get('project.task.line').browse(cr, uid, task_line_id)
            vals.update({'prepare_qty':task_line.prepare_qty,
                         'need_qty': task_line.need_qty,
                         'current_done_qty': task_line.done_qty})
        return {'value': vals}

    def onchange_mfg_id(self, cr, uid, ids, mfg_id, context=None):
        vals = {}
        if mfg_id:
            mfg = self.pool.get('sale.product').browse(cr, uid, mfg_id)
            vals.update({'unit':mfg.product_id.id})
        return {'value': vals}

    def _get_time_spent(self, cr, uid, ids, name, args, context=None):
        result = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.time_start and line.time_end:
                delta = datetime.strptime(line.time_end, DEFAULT_SERVER_DATETIME_FORMAT) - \
                        datetime.strptime(line.time_start, DEFAULT_SERVER_DATETIME_FORMAT)
                result.update({line.id: str(delta)})
        return result


    def write(self, cr, uid, ids, vals, context=None):
        if not type(ids) is list:
            ids = [ids]
        if 'done_qty' in vals:
            for line in self.browse(cr, uid, ids):
                if line.task_line_id:
                    new_done_qty = vals['done_qty'] + line.task_line_id.done_qty
                    if new_done_qty > line.task_line_id.need_qty:
                        raise osv.except_osv(_('Error!'), _('%s : done quantity must <= need quantity!')%(line.task_line_id.name,))
        result = super(project_mfgtask_report_line,self).write(cr, uid, ids, vals, context=context)
        return result

    def create(self, cr, uid, vals, context=None):
        created_id = super(project_mfgtask_report_line, self).create(cr, uid, vals, context=context)
        line = self.browse(cr, uid, created_id, context=context)
        if line.report_id:
            sequence = 1
            cr.execute('SELECT  COALESCE(MAX(sequence),0) as sequence FROM project_mfgtask_report_line WHERE report_id = %s',(line.report_id.id,))
            result = cr.dictfetchall()
            if result:
                sequence = result[0]["sequence"] + 1
            self.write(cr, uid, [created_id],{'sequence': sequence})
        return created_id

    _columns = {
        'report_id': fields.many2one('project.mfgtask.report','Project Task Report'),
        'sequence': fields.integer('#',readonly=True),
        'date_create': fields.date('Date',readonly=True),
        'mfg_id': fields.many2one('sale.product','MFG ID',readonly=True,states={'draft': [('readonly', False)]}),
        'unit': fields.related('mfg_id','product_id',type='many2one',relation='product.product',string='Unit'),
        'mo_id': fields.many2one('mrp.production','MO',readonly=True,states={'draft': [('readonly', False)]}),
        'workorder_id': fields.many2one('mrp.production.workcenter.line','Work Order',readonly=True,states={'draft': [('readonly', False)]}),
        'drawing_order_id': fields.many2one('drawing.order','Drawing Order',readonly=True,states={'draft': [('readonly', False)]}),
        'task_id': fields.many2one('project.task','Task',readonly=True,states={'draft': [('readonly', False)]}),
        'task_line_id': fields.many2one('project.task.line','Task line',readonly=True,states={'draft': [('readonly', False)]}),
        'operation_code': fields.char('Operation code', size=128,readonly=True,states={'draft': [('readonly', False)]}),
        'prepare_qty': fields.related('task_line_id','prepare_qty',type='integer',string='Prepare Qty'),
        'done_qty': fields.integer('Done Qty',readonly=True,states={'draft': [('readonly', False)]}),
        'need_qty': fields.related('task_line_id','need_qty',type='integer',string='Need Qty'),
        'current_done_qty': fields.related('task_line_id','done_qty',type='integer',string='Current Done Qty'),
        'time_start': fields.datetime('Time Start',readonly=True,states={'draft': [('readonly', False)]}),
        'time_end': fields.datetime('Time Finish',readonly=True,states={'draft': [('readonly', False)]}),
        'time_spent': fields.function(_get_time_spent,string='Time Spent',type='char',size=50),
        'serial_no': fields.char('Serial #', size=50,readonly=True,states={'draft': [('readonly', False)]}),
        'qc_passed': fields.many2one('hr.employee','QC Passed',readonly=True,states={'draft': [('readonly', False)]}),
        'dispatcher': fields.many2one('res.users','Dispatcher Received',readonly=True),
        'state': fields.selection([('draft', 'Draft'),
                                   ('confirmed', 'Confirmed'),
                                   ('cancel','Cancelled')
                                   ],track_visibility='onchange', string='Status')
    }

    _defaults = {
        'state': 'draft',
        'dispatcher': lambda self, cr, uid, c: uid,
        'date_create': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
    }