# -*- encoding: utf-8 -*-
from osv import fields, osv
from datetime import datetime, time
import tools
from tools.translate import _
from openerp.addons.metro import mdb
from openerp.tools.misc import resolve_attr
from openerp.addons.metro import utils
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST
import logging

_logger = logging.getLogger(__name__)


class hr_department(osv.osv):
    _inherit = "hr.department"

    def _check_code(self, cr, uid, ids, context=None):
        for dept in self.browse(cr, uid, ids, context=context):
            #Check duplicate codes
            duplicate_dept_ids = self.search(cr, uid, [('code','=',dept.code)])
            if duplicate_dept_ids and len(duplicate_dept_ids) > 1:
                raise osv.except_osv(_('Error'), _('Department code is duplicate!'))
            #Check valid
            if dept.code not in WORK_STEP_LIST:
                raise osv.except_osv(_('Error'), _('Department code is invalid!'))
        return True

    _constraints = [
        (_check_code,
         'Code is invalid!',
         ['code'])
    ]
hr_department()