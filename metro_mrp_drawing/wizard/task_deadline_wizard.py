import time
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
class task_deadline_wizard(osv.osv_memory):
    _name = 'task.deadline.wizard'
    _description = 'Task Deadline Wizard'
    _columns = {
        'task_ids': fields.many2many('project.task',string= 'Tasks'),
        'date_deadline': fields.date('Deadline',required=True),
    }
    def default_get(self, cr, uid, fields_list, context=None):
        result = super(task_deadline_wizard, self).default_get(cr, uid, fields_list, context=context)
        active_model = context and context.get('active_model',False) or False
        active_ids = context and context.get('active_ids',False) or False
        if active_model == 'project.task' and active_ids:
            result.update({'task_ids': [(6,0,active_ids)]})
        return result

    def do_set(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids, context)[0]
        task_ids = [task.id for task in wizard.task_ids]
        task_obj = self.pool.get('project.task')
        task_obj.write(cr, uid, task_ids, {'date_deadline': wizard.date_deadline})
        return True

task_deadline_wizard()
