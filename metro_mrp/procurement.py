# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp.osv import fields
from openerp.osv import osv
from openerp.tools.translate import _
from openerp import netsvc

class procurement_order(osv.osv):
    _inherit = 'procurement.order'
    _columns = {
#        'mfg_id': fields.many2one('sale.product', string='MFG ID'),
        'mfg_ids': fields.many2many('sale.product', 'proc_mfg_id_rel','proc_id','mfg_id',string='MFG IDs',),
    }
    
    def make_mo(self, cr, uid, ids, context=None):
        """ Make Manufacturing(production) order from procurement
        @return: New created Production Orders procurement wise 
        """
        res = {}
        company = self.pool.get('res.users').browse(cr, uid, uid, context).company_id
        production_obj = self.pool.get('mrp.production')
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")
        procurement_obj = self.pool.get('procurement.order')
        for procurement in procurement_obj.browse(cr, uid, ids, context=context):
            res_id = procurement.move_id.id
            newdate = datetime.strptime(procurement.date_planned, '%Y-%m-%d %H:%M:%S') - relativedelta(days=procurement.product_id.produce_delay or 0.0)
            newdate = newdate - relativedelta(days=company.manufacturing_lead)
            #get the bom_id and routing id, johnw, 08/04/2014
            #begin
            bom_id = procurement.bom_id and procurement.bom_id.id or False
            if not bom_id:
                props = procurement.property_ids and [prop.id for prop in procurement.property_ids] or None
                bom_id = self.pool.get('mrp.bom')._bom_find(cr, uid, procurement.product_id.id, procurement.product_uom.id, props)
            routing_id = bom_id and self.pool.get('mrp.bom').browse(cr,uid,bom_id,context=context).routing_id.id or False
            #end
            
            produce_id = production_obj.create(cr, uid, {
                'origin': procurement.origin,
                'product_id': procurement.product_id.id,
                'product_qty': procurement.product_qty,
                'product_uom': procurement.product_uom.id,
                'product_uos_qty': procurement.product_uos and procurement.product_uos_qty or False,
                'product_uos': procurement.product_uos and procurement.product_uos.id or False,
                'location_src_id': procurement.location_id.id,
                'location_dest_id': procurement.location_id.id,
#                'bom_id': procurement.bom_id and procurement.bom_id.id or False,
                'bom_id': bom_id,
                'date_planned': newdate.strftime('%Y-%m-%d %H:%M:%S'),
                'move_prod_id': res_id,
                'company_id': procurement.company_id.id,
                #add the mfg_ids, johnw@07/14/2014
                'mfg_ids': procurement.mfg_ids and [(4,mfg_id.id) for mfg_id in procurement.mfg_ids] or False, 
                #add the routing_id, johnw@07/14/2014    
                'routing_id': routing_id,           
            })


            res[procurement.id] = produce_id
            self.write(cr, uid, [procurement.id], {'state': 'running', 'production_id': produce_id})   
            '''by johnw, 08/04/2014, 
            Under the ID logic, do not computer the MO automatically to generate the product and move lines
            Need the engineering work finished, then the BOM and routing will be confirmed, then can do computing
            ''' 
#            bom_result = production_obj.action_compute(cr, uid,
#                    [produce_id], properties=[x.id for x in procurement.property_ids])
                           
            #by johnw, 07/31/2014, Under the ID logic, do not confirm the MO automatically, need the engineering work finished.
#            wf_service.trg_validate(uid, 'mrp.production', produce_id, 'button_confirm', cr)
            #by johnw, 07/31/2014, auto set the MFG ID's work flow to manufacture state
            #begin
            if procurement.mfg_ids:
                self.pool.get('sale.product').write(cr, uid, [mfg_id.id for mfg_id in procurement.mfg_ids], {'mrp_prod_ids':[(4,produce_id)]},context=context)
                for mfg_id in procurement.mfg_ids:
                    if mfg_id.state == 'draft':
                        wf_service.trg_validate(uid, 'sale.product', mfg_id.id, 'button_confirm', cr)
                        wf_service.trg_validate(uid, 'sale.product', mfg_id.id, 'button_manufacture', cr)
                    if mfg_id.state == 'confirmed':
                        wf_service.trg_validate(uid, 'sale.product', mfg_id.id, 'button_manufacture', cr)
            #end
            if res_id:
                move_obj.write(cr, uid, [res_id],
                        {'location_id': procurement.location_id.id})
        self.production_order_create_note(cr, uid, ids, context=context)
        return res

procurement_order()

class mrp_production(osv.osv):
    _inherit = 'mrp.production'
    def _make_production_line_procurement(self, cr, uid, production_line, shipment_move_id, context=None):
        wf_service = netsvc.LocalService("workflow")
        procurement_order = self.pool.get('procurement.order')
        production = production_line.production_id
        location_id = production.location_src_id.id
        date_planned = production.date_planned
        procurement_name = (production.origin or '').split(':')[0] + ':' + production.name
        procurement_id = procurement_order.create(cr, uid, {
                    'name': procurement_name,
                    'origin': procurement_name,
                    'date_planned': date_planned,
                    'product_id': production_line.product_id.id,
                    'product_qty': production_line.product_qty,
                    'product_uom': production_line.product_uom.id,
                    'product_uos_qty': production_line.product_uos and production_line.product_qty or False,
                    'product_uos': production_line.product_uos and production_line.product_uos.id or False,
                    'location_id': location_id,
                    'procure_method': production_line.product_id.procure_method,
                    'move_id': shipment_move_id,
                    'company_id': production.company_id.id,
                    #add the mfg_id, for reading in procurement.order.make_mo(), johnw, 07/14/2014 
                    'mfg_ids': production_line.mfg_id and [(4,production_line.mfg_id.id)] or False,
                })
        wf_service.trg_validate(uid, procurement_order._name, procurement_id, 'button_confirm', cr)
        return procurement_id

class sale_order(osv.osv):
    _inherit = 'sale.order'
    #override this method in sale_stock.sale_order, to add the mfg ids to the procurement order    
    def _prepare_order_line_procurement(self, cr, uid, order, line, move_id, date_planned, context=None):
#        return {
#            'name': line.name,
#            'origin': order.name,
#            'date_planned': date_planned,
#            'product_id': line.product_id.id,
#            'product_qty': line.product_uom_qty,
#            'product_uom': line.product_uom.id,
#            'product_uos_qty': (line.product_uos and line.product_uos_qty)\
#                    or line.product_uom_qty,
#            'product_uos': (line.product_uos and line.product_uos.id)\
#                    or line.product_uom.id,
#            'location_id': order.shop_id.warehouse_id.lot_stock_id.id,
#            'procure_method': line.type,
#            'move_id': move_id,
#            'company_id': order.company_id.id,
#            'note': line.name,
#        }
        proc_ord_vals = {
            'name': line.name,
            'origin': order.name,
            'date_planned': date_planned,
            'product_id': line.product_id.id,
            'product_qty': line.product_uom_qty,
            'product_uom': line.product_uom.id,
            'product_uos_qty': (line.product_uos and line.product_uos_qty)\
                    or line.product_uom_qty,
            'product_uos': (line.product_uos and line.product_uos.id)\
                    or line.product_uom.id,
            'location_id': order.shop_id.warehouse_id.lot_stock_id.id,
            'procure_method': line.type,
            'move_id': move_id,
            'company_id': order.company_id.id,
            'note': line.name,
        }        
        if line.type == 'make_to_order' and line.product_id.supply_method == 'produce':
            #get the bom_id
            props = line.property_ids and [prop.id for prop in line.property_ids] or None
            bom_obj = self.pool.get('mrp.bom')
            bom_id = bom_obj._bom_find(cr, uid, line.product_id.id, False, props)
            #create MFG id by sales order
            mfg_id_vals = {'source':'sale',
                           'date_planned': date_planned,
                           'mto_design_id': line.mto_design_id and line.mto_design_id.id or False,
                           'product_id': line.product_id.id,
                           'bom_id': bom_id,
                           'so_id': line.order_id.id,
                           'note':line.name}
            new_mfg_ids = []
            for i in range(0,line.product_uom_qty):
                new_mfg_ids.append((4,self.pool.get('sale.product').create(cr, uid, mfg_id_vals)))
            proc_ord_vals.update({
                                #add the property_ids, to fix the matching BOM issue in mrp_bom.action_compute() caused by the procurement.order.property_ids missing
                                'property_ids': line.property_ids and [(4,prop.id) for prop in line.property_ids] or False,
                                #mfg ids
                                'mfg_ids': new_mfg_ids,
                                #bom_id
                                'bom_id': bom_id                                  
                                  })
        return proc_ord_vals
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
