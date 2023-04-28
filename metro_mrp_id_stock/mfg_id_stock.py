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

from openerp.osv import fields, osv
from openerp.tools.translate import _
import time, datetime
import openerp.addons.decimal_precision as dp
from dateutil.relativedelta import relativedelta
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT

class mfg_id_reserve(osv.osv):
    _name = "mfg.id.reserve"
    _inherit = ['mail.thread']
    _columns={        
                'mfg_id': fields.many2one("sale.product", string="MFG ID"),  
                'product_id': fields.many2one("product.product", string="Product"),  
                'location_id': fields.many2one("stock.location", string="Location"),
                'product_qty': fields.float('Reserved Quantity', track_visibility='onchange'),
                'product_qty_consumed': fields.float('Consumed Quantity', track_visibility='onchange'),
                'pur_req_line_id': fields.many2one("pur.req.line", string="Requisition Line"),
                'pur_req_id': fields.related("pur_req_line_id","req_id",type="many2one", relation="pur.req", string="Requisition")
              }
    
mfg_id_reserve()

class product_product(osv.osv):
    _inherit = 'product.product'

    def _reserved_qty(self, cr, uid, ids, field_names=None, arg=False, context=None):
        if context is None:
            context = {}
        res = {}
        mfg_inv_obj = self.pool.get('mfg.id.reserve')
        for prod in self.browse(cr, uid, ids, context=context):
            line_ids = mfg_inv_obj.search(cr, uid, [('product_id','=',prod.id)], context=context)
            reserved_qty = 0.0
            for line in mfg_inv_obj.browse(cr, uid, line_ids, context=context):
                reserved_qty += line.product_qty
            res[prod.id] = reserved_qty           
        return res
    
    def _get_mfg_id_products(self, cr, uid, ids, context=None):        
        res = set()
        for mfg_id_inv in self.browse(cr, uid, ids, context=context):
            res.add(mfg_id_inv.product_id.id)
        return res
            
    _columns={        
                'reserved_qty': fields.function(_reserved_qty, string="Reserved Quantity", type="float", 
                     store = {'mfg.id.reserve': (_get_mfg_id_products, ['product_id', 'product_qty'], 10),}
                     , digits_compute=dp.get_precision('Product Unit of Measure')),
              }
    
class sale_product(osv.osv):
    _inherit = 'sale.product'
            
    _columns={
                'bom_id_material': fields.many2one('mrp.bom',string='Material BOM', track_visibility='onchange',readonly=True, states={'draft':[('readonly',False)]}),              
              }
    def onchange_bom_id(self, cr, uid, ids, bom_id, context=None):
        return {'value':{'bom_id_material':bom_id}}
        
    def _get_purchase_schedule_date(self, cr, uid, company, context=None):
        date_planned = datetime.datetime.now()
        schedule_date = (date_planned + relativedelta(days=company.po_lead))
        return schedule_date
        
    def reserve_and_req(self, cr, uid, ids, location_id, context=None):                
        bom_obj = self.pool.get('mrp.bom')
        uom_obj = self.pool.get('product.uom')
        mfg_id_obj = self.pool.get('sale.product')
        pur_req_obj = self.pool.get('pur.req')
        pur_req_line_obj = self.pool.get('pur.req.line')
        prod_obj = self.pool.get('product.product')
        id_reserve_obj = self.pool.get('mfg.id.reserve')
        
        cur_user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        company_id = cur_user.company_id.id
        
        #1.check all of mfg_id's bom_id and merge mfg_ids with same bom
        bom_mfg_ids = {}
        for mfg_id in self.browse(cr, uid, ids, context=context):
            if not mfg_id.bom_id_material:
                raise osv.except_osv(_('Error'), _('Please assign material BOM to MFG ID (%s), then you can generated purchase requisitions from it')%(mfg_id.name,))
            bom = mfg_id.bom_id_material
            mfg_ids = bom_mfg_ids.get(bom.id,[])
            if not mfg_ids:
                bom_mfg_ids[bom.id] = mfg_ids
            mfg_ids.append(mfg_id.id)
            
        #2.generate the purchase requisitions by bom, and make inventory reservation        
        warehouse_id = self.pool.get('stock.warehouse').search(cr, uid, [('company_id', '=', company_id)], context=context)        
        warehouse_id = warehouse_id and warehouse_id[0] or False
        req_ids = []
        for bom_id, mfg_ids in bom_mfg_ids.items():
            bom = bom_obj.browse(cr, uid, bom_id, context=context)
            #generate pur_req
            pur_req_vals = {
                'warehouse_id': warehouse_id,
                'user_id': uid,
                'company_id': company_id,
                'state': 'draft',
            }
            pur_req_id = pur_req_obj.create(cr, uid, pur_req_vals, context=context)
            
            #generate pur_req_line        
            result = bom_obj._bom_explode(cr, uid, bom, factor=len(mfg_ids))[0]
            req_line_cnt = 0
            for line in result:
                #get the quantity to request
                bom_qty = line['product_qty']
                req_qty = bom_qty
                product = prod_obj.browse(cr, uid, line['product_id'], context=context)
                if not product.purchase_ok:
                    continue
                qty_avail = product.qty_virtual + product.product_qty_req - product.reserved_qty
                if qty_avail < bom_qty:
                    req_qty = bom_qty - qty_avail
                
                #create reservation line
                pur_req_line_id = None
                if req_qty > 0:
                    uom_bom_id = line['product_uom']
                    uom_po_id = product.uom_po_id.id
                    req_qty = uom_obj._compute_qty(cr, uid, uom_bom_id, req_qty, uom_po_id)
                    schedule_date = self._get_purchase_schedule_date(cr, uid, bom.company_id, context=context)
                    mfg_ids_str = ','.join([mfg_id.name for mfg_id in mfg_id_obj.browse(cr, uid, mfg_ids, context=context)])
                    pur_req_line_vals = {
                        'req_id': pur_req_id,
                        'name': product.partner_ref,
                        'product_qty': req_qty,
                        'product_id': product.id,
                        'product_uom_id': uom_po_id,
                        'inv_qty': product.qty_available,
                        'date_required': schedule_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                        'req_reason': 'MFG ID [%s]'%(mfg_ids_str,),
                        'req_emp_id': cur_user.employee_id and cur_user.employee_id.id or False,
                        'mfg_ids':[[6,0,mfg_ids]]
                    }
                    pur_req_line_id = pur_req_line_obj.create(cr, uid, pur_req_line_vals, context=context)
                    req_line_cnt += 1
                    
                #create reservation line
                for mfg_id in mfg_ids:
                    #if there are reservation and having consumed quantity,  then can raise error
                    ids_used = id_reserve_obj.search(cr, uid, [('mfg_id','=',mfg_id),('product_id','=',line['product_id']),('product_qty_consumed','>',0)], context=context)
                    if ids_used:
                        raise osv.except_osv(_('Error'), _('MFG ID(%s) consumed product [%s]%s, can not generated reservation again!')%(mfg_id,product.default_code,product.name))
                    cr.execute('delete from mfg_id_reserve where mfg_id=%s and product_id=%s',(mfg_id, line['product_id']))
                    reserve_vals = {'mfg_id':mfg_id, 'product_id':line['product_id'], 'location_id':location_id, 'product_qty':bom_qty/len(mfg_ids), 'pur_req_line_id':pur_req_line_id}
                    id_reserve_obj.create(cr, uid, reserve_vals, context=context)
                    
            #delete the pur_req if there are no req lines generated
            if req_line_cnt == 0:
                pur_req_obj.unlink(cr, uid, pur_req_id, context=context)
            else:
                req_ids.append(pur_req_id)
        
        #finished, go to the purchase requisition page if there are requisition generated
#        if req_ids:
#            return self.material_requested(cr, uid, ids, context)
#        else:
#            return self.material_reserved(cr, uid, ids, context)
        return self.material_reserved(cr, uid, ids, context)

    def material_reserved(self, cr, uid, ids, context):
        act_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_mrp_id_stock', 'action_mfg_id_reserve')
        act_id = act_id and act_id[1] or False        
        act_win = self.pool.get('ir.actions.act_window').read(cr, uid, act_id, [], context=context)
        act_win['context'] = {'search_default_mfg_id': ids[0]}
        return act_win

class stock_move(osv.osv):
    _inherit = "stock.move"
    def action_done(self, cr, uid, ids, context=None):
        resu = super(stock_move,self).action_done(cr, uid, ids, context)
        #get the mfg id's moving out quantity {mfg_id:{product_id:qty,...},...}
        mfg_ids = {}
        mat_req_line = self.pool.get('material.request.line')
        id_reserve_obj = self.pool.get('mfg.id.reserve')
        for move in self.browse(cr, uid, ids, context=context):
            if move.picking_id and move.picking_id.type == 'mr' and move.state == 'done':
                move = mat_req_line.browse(cr, uid, move.id, context=context)
                if not move.mr_sale_prod_id or move.product_qty <= 0:
                    continue
                product_id = move.product_id.id
                mfg_id = move.mr_sale_prod_id.id
                #get the mfg_id's product
                mfg_id_products = {}
                if mfg_id not in mfg_ids:
                    mfg_ids[mfg_id] = mfg_id_products
                else:
                    mfg_id_products = mfg_ids.get(mfg_id)
                #set the products quantity
                prod_qty = mfg_id_products.get(product_id, 0)
                mfg_id_products[product_id] = prod_qty + move.product_qty
        
        #remove  the reserved quantity
        if mfg_ids:
            for mfg_id, product_qty in mfg_ids.items():
                for product_id, qty in product_qty.items():
                    #cr.execute('update mfg_id_reserve set product_qty=product_qty-%s, product_qty_consumed=product_qty_consumed+%s where mfg_id=%s and product_id=%s',(qty, qty, mfg_id, product_id))
                    #In order to record  the quantity changing messages, need use OpenERP to do update
                    id_reserve_ids = id_reserve_obj.search(cr, uid, [('mfg_id','=',mfg_id),('product_id','=',product_id)], context=context)
                    if id_reserve_ids:
                        qty_reserve = id_reserve_obj.read(cr, uid, id_reserve_ids[0], ['product_qty','product_qty_consumed'], context=context)
                        qty_old = qty_reserve['product_qty']
                        qty_consumed_old = qty_reserve['product_qty_consumed']
                        id_reserve_obj.write(cr, uid, id_reserve_ids[0], {'product_qty':qty_old-qty, 'product_qty_consumed':qty_consumed_old+qty}, context=context)
                    
        return resu      
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
