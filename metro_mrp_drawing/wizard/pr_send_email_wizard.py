import time
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST
class pr_send_email_wizard(osv.osv_memory):
    _name = 'pr.send.email.wizard'
    _description = 'Send PR Email Wizard'
    _columns = {
        'pr_id': fields.many2one('pur.req',string='PR',readonly=True),
        'pr_lines': fields.many2many('pur.req.line',string='PR Lines'),
        'attach_pdf': fields.boolean('Attach PDF'),
        'attach_dxf': fields.boolean('Attach DXF'),
        'attach_bom_xls': fields.boolean('Attach BOM XLS'),
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(pr_send_email_wizard, self).default_get(cr, uid, fields, context=context)
        active_id = context and context.get('active_id', False) or False
        active_ids = context and context.get('active_ids', False) or False
        active_model =  context and context.get('active_model', False) or False
        if active_model == 'pur.req':
            res.update({'pr_id': active_id})
        elif active_model == 'pur.req.line' and active_ids:
            #Check if all pr line in 1 pr
            pr_ids = {}
            pr_line_obj = self.pool.get('pur.req.line')
            for pr_line in pr_line_obj.browse(cr, uid, active_ids):
                pr_ids.update({pr_line.req_id.id:True})
            if len(pr_ids.keys()) != 1:
                raise osv.except_osv(_('Warning!'), _("Selected PR lines must be in the same PR"))
            res.update({'pr_id': pr_ids.keys()[0],
                        'pr_lines': [[6, False, active_ids]]})

        return res

    def do_compose(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids, context)[0]
        req_obj = self.pool.get('pur.req')
        pr_line_ids = []
        for line in wizard.pr_lines:
            pr_line_ids.append(line.id)
        context.update({'pr_line_ids':pr_line_ids,
                        'attach_pdf': wizard.attach_pdf,
                        'attach_dxf': wizard.attach_dxf,
                        'attach_bom_xls': wizard.attach_bom_xls})
        return req_obj.send_pr_email(cr, uid, [wizard.pr_id.id], context=context)

pr_send_email_wizard()
