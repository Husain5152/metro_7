# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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
from openerp.osv import fields,osv
from openerp.addons.base_status.base_stage import base_stage
from openerp.tools.translate import _
from lxml import etree
from openerp import netsvc
class project_project(osv.osv):
    _inherit = 'project.project'
    _columns = {
        'mfg_ids': fields.many2many('sale.product', 'project_id_rel','project_id','mfg_id',string='MFG IDs',),
        'single_mrp_prod_order': fields.boolean('Single Manufacture Order',),
        'bom_id': fields.many2one('mrp.bom', string='Bill of Material',),
        'product_id': fields.related('bom_id', 'product_id', type='many2one', relation='product.product', string='Product', readonly=True),
        'bom_components': fields.related('bom_id', 'bom_lines', type='one2many', relation='mrp.bom', fields_id='bom_id', string='Components', readonly=True),
    }
    
    _defaults = {'single_mrp_prod_order':True}
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        res = super(project_project,self).copy_data(cr, uid, id, default=default, context=context)
        if res:
            res.update({'mfg_ids':False,'bom_id':False})
        return res
    
    def set_done(self, cr, uid, ids, context=None):        
        if isinstance(ids, (int,long)):
            ids = [ids]
        if context == None:
            context = {}
        #the BOM is required when do project done
        for proj in self.browse(cr, uid, ids, context=context):
            if proj.project_type == 'engineer' and not proj.bom_id:
                raise osv.except_osv(_('Error!'), _('Project "%s", BOM is required to close to engineering Project.'%(proj.name,)))
        resu = super(project_project,self).set_done(cr, uid, ids, context)
        '''
        after project is done, trigger the 'act_button_manufacture' of the project's sale product ID
        ''' 
        wf_service = netsvc.LocalService("workflow")
        sale_prod_obj = self.pool.get('sale.product')  
        for proj in self.browse(cr, uid, ids):
            #Only the engineering project need to do this action
            if proj.project_type != 'engineer':
                continue
            vals = {'bom_id':proj.bom_id.id, 'product_id':proj.bom_id.product_id.id}
            #the date_planned for the new manufacture
            date_planned = None
            mfg_id_new_project = None
            new_mfg_prod_order_id = None
            if proj.single_mrp_prod_order:
                #generate one single mrp production order for all MFG IDs
                for mfg_id in proj.mfg_ids:
                    if not mfg_id.mrp_prod_ids:
                        #find one sale_product without mrp production order, generate one order and get the order id
                        sale_prod_obj.write(cr, uid, mfg_id.id, vals, context=context)
                        mfg_id_new_project = mfg_id.id
                        new_mfg_prod_order_id = sale_prod_obj.create_mfg_order(cr, uid, mfg_id.id, context=context)
                        date_planned = mfg_id.date_planned
                        wf_service.trg_validate(uid, 'sale.product', mfg_id.id, 'button_manufacture', cr)
                        break
                if new_mfg_prod_order_id:
                    vals.update({'mrp_prod_ids':[(4, new_mfg_prod_order_id)]})
            
            #the product quantity for the manufacture order.
            prod_cnt = 0
            for mfg_id in proj.mfg_ids:
                if mfg_id_new_project and mfg_id.id == mfg_id_new_project:
                    prod_cnt += 1
                    continue
                if not mfg_id.mrp_prod_ids:
                    sale_prod_obj.write(cr, uid, mfg_id.id, vals, context=context)
                    wf_service.trg_validate(uid, 'sale.product', mfg_id.id, 'button_manufacture', cr)
                    prod_cnt += 1
                    if not date_planned or mfg_id.date_planned < date_planned:
                        date_planned = mfg_id.date_planned
                        
            if new_mfg_prod_order_id:
                mrp_order_vals = {'origin':proj.name,'product_qty':prod_cnt, 'date_planned':date_planned}
                self.pool.get('mrp.production').write(cr, uid, [new_mfg_prod_order_id], mrp_order_vals, context=context)                    
                                
        return resu
            
class project_task(base_stage, osv.osv):
    _inherit = "project.task"

    _columns = {
        'bom_id': fields.many2one('mrp.bom', string='Bill of Material'),
        'product_id': fields.related('bom_id', 'product_id', type='many2one', relation='product.product', string='Product', readonly=True),
        'components': fields.related('bom_id', 'bom_lines', type='one2many', relation='mrp.bom', fields_id='bom_id', string='Components', readonly=True)
    }

    def action_close(self, cr, uid, ids, context=None):
        if isinstance(ids, (int,long)):
            ids = [ids]
        if context == None:
            context = {}
        '''
        #the BOM is required when do project done
        for task in self.browse(cr, uid, ids, context=context):
            #Only the engineering project,  the bom_is is required
            if task.project_id.project_type == 'engineer' and not task.bom_id:
                raise osv.except_osv(_('Error!'), _('Task "%s", BOM is required for done.'%(task.name,)))
        '''
        return super(project_task,self).action_close(cr, uid, ids, context)