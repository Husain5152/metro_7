import time
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST
class po_send_email_wizard(osv.osv_memory):
    _name = 'po.send.email.wizard'
    _description = 'Send PO Email Wizard'
    _columns = {
        'po_id': fields.many2one('purchase.order',string='PO',readonly=True),
        'attach_pdf': fields.boolean('Attach PDF?'),
        'attach_dxf': fields.boolean('Attach DXF?'),
        'attach_bom_xls': fields.boolean('Attach BOM XLS'),
        'add_watermark': fields.boolean('Add watermark?'),
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(po_send_email_wizard, self).default_get(cr, uid, fields, context=context)
        active_id = context and context.get('active_id', False) or False
        active_model =  context and context.get('active_model', False) or False
        if active_model == 'purchase.order' and active_id:
            res.update({'po_id': active_id})
        return res

    def do_compose(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        wizard = self.browse(cr, uid, ids, context)[0]
        if wizard.po_id:
            purchase_obj = self.pool.get('purchase.order')
            context.update({'attach_pdf': wizard.attach_pdf,
                            'attach_dxf': wizard.attach_dxf,
                            'attach_bom_xls': wizard.attach_bom_xls,
                            'add_watermark': wizard.add_watermark})
            return purchase_obj.send_po_email(cr, uid, [wizard.po_id.id], context=context)
        return True

po_send_email_wizard()
