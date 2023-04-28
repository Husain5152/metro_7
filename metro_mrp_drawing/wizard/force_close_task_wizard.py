# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST

class force_close_task_wizard(osv.osv_memory):
    _name = 'force.close.task.wizard'
    _description = 'Force Close Task Wizard'
    _columns = {
        'mfg_ids': fields.many2many('sale.product',string='MFG IDS',required=True),
        'close_task': fields.boolean('Close Task?'),
        'close_mo': fields.boolean('Close MO?'),
        'mo_ids': fields.many2many('mrp.production', string='Manufacturer Orders'),
    }

    _defaults = {
        'close_task': True,
        'close_mo': True,
    }

    def onchange_mfg_ids(self, cr, uid, ids, mfg_ids, context=None):
        mo_obj = self.pool.get('mrp.production')
        mo_ids = mo_obj.search(cr, uid, [('mfg_ids','in', mfg_ids[0][2])], context=context)
        return {'value':{'mo_ids': mo_ids}}

    def do_close(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids, context)[0]
        task_obj = self.pool.get('project.task')
        mo_obj = self.pool.get('mrp.production')
        wo_obj = self.pool.get('mrp.production.workcenter.line')
        closed_task_ids = []
        for mfg_id in wizard.mfg_ids:
            #TODO: Close task
            task_ids = task_obj.search(cr, uid, [('state','!=','done'),
                                                 ('mfg_ids','in',[mfg_id.id])])
            if task_ids:
                closed_task_ids.extend(task_ids)
        task_obj.force_close(cr, uid, closed_task_ids, context=context)
        #TODO: Try to close MO
        mo_ids = []
        for mo in wizard.mo_ids:
            mo_ids.append(mo.id)
            for wo in mo.workcenter_lines:
                wo_obj.write(cr, uid, [wo.id], {'state': 'done'}, context=context)
        mo_obj.write(cr, uid, mo_ids, {'state': 'done'},context = context)

        return True

force_close_task_wizard()
