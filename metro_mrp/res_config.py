# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (C) 2004-2012 OpenERP S.A. (<http://openerp.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, osv
from openerp import pooler
from openerp.tools.translate import _

class mrp_config_settings(osv.osv_memory):
    _inherit = 'mrp.config.settings'

    _columns = {
        'cnc_task_required': fields.boolean("Task is mandatory for CNC work order",
            help="""If checked this, then the manufacture task is required when do CNC work order confirmation."""),
        'mrp_cnc_wo_group_confirm': fields.many2one("res.groups", string="Group that confirm CNC work order",),
        'mrp_cnc_wo_group_approve': fields.many2one("res.groups", string="Group that approve CNC work order",),
        'mrp_cnc_wo_group_cnc_mgr': fields.many2one("res.groups", string="Group that working on CNC work order",),
    }
    def set_metro_defaults(self, cr, uid, ids, context=None):
        conf = self.browse(cr, uid, ids)[0]
        #deal the cnc_task_required parameter
        cnc_task_required = conf.cnc_task_required and '1' or '0'
        self.pool.get('ir.config_parameter').set_param(cr, uid, 'mrp.cnc.task.reuqired', cnc_task_required, context=context)
        #deal the cnc wo confirm/approve group id
        self.pool.get('ir.config_parameter').set_param(cr, uid, 'mrp_cnc_wo_group_confirm', conf.mrp_cnc_wo_group_confirm.id, context=context)
        self.pool.get('ir.config_parameter').set_param(cr, uid, 'mrp_cnc_wo_group_approve', conf.mrp_cnc_wo_group_approve.id, context=context)
        self.pool.get('ir.config_parameter').set_param(cr, uid, 'mrp_cnc_wo_group_cnc_mgr', conf.mrp_cnc_wo_group_cnc_mgr.id, context=context)
        return {}   
     
    def get_default_metro(self, cr,uid,fields,context):
        res = {}
        cnc_task_required = self.pool.get('ir.config_parameter').get_param(cr, uid, 'mrp.cnc.task.reuqired', '0', context=context)
        mrp_cnc_wo_group_confirm = self.pool.get('ir.config_parameter').get_param(cr, uid, 'mrp_cnc_wo_group_confirm', context=context)
        mrp_cnc_wo_group_approve = self.pool.get('ir.config_parameter').get_param(cr, uid, 'mrp_cnc_wo_group_approve', context=context)
        mrp_cnc_wo_group_cnc_mgr = self.pool.get('ir.config_parameter').get_param(cr, uid, 'mrp_cnc_wo_group_cnc_mgr', context=context)
        
        res.update({'cnc_task_required':cnc_task_required=="1" and True or False,
                    'mrp_cnc_wo_group_confirm':mrp_cnc_wo_group_confirm and long(mrp_cnc_wo_group_confirm) or None,
                    'mrp_cnc_wo_group_approve':mrp_cnc_wo_group_approve and long(mrp_cnc_wo_group_approve) or None,
                    'mrp_cnc_wo_group_cnc_mgr':mrp_cnc_wo_group_cnc_mgr and long(mrp_cnc_wo_group_cnc_mgr) or None})
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
