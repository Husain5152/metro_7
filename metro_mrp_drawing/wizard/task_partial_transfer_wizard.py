# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST

class task_partial_transfer_wizard(osv.osv_memory):
    _name='task.partial.transfer.wizard'
    _description = 'Task Partial Transfer Wizard'
    _columns = {
        'task_id': fields.many2one('project.task','Warehouse Task',readonly=True),
        'task_lines': fields.many2many('project.task.line',string='Task lines'),
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(task_partial_transfer_wizard, self).default_get(cr, uid, fields, context=context)
        active_id = context and context.get('active_id', False) or False
        active_model = context and context.get('active_model', False) or False
        task_obj = self.pool.get('project.task')
        task_line_ids = []
        if active_id and active_model == 'project.task':
            task = task_obj.browse(cr, uid, active_id, context=context)
            if task:
                for line in task.task_lines:
                    if line.transfer_qty < line.done_qty:
                        task_line_ids.append(line.id)
                res.update({'task_lines': [[6, False, task_line_ids]],
                            'task_id': active_id,
                            })
        return res

    def do_transfer(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids, context=context)[0]
        task_obj = self.pool.get('project.task')
        if wizard:
            task_line_ids = []
            for line in wizard.task_lines:
                task_line_ids.append(line.id)
            task_obj.do_partial_transfer(cr, uid, wizard.task_id.id, task_line_ids, context=context)
        return {'type': 'ir.actions.act_window_close'}

task_partial_transfer_wizard()