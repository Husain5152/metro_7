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
from dateutil.relativedelta import relativedelta
import time
import datetime
from openerp import netsvc
from openerp.osv import fields,osv
from openerp.addons.metro import utils
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
import xlwt
import tempfile

class material_request(osv.osv):
    _name = "material.request"
    _inherit = "stock.picking"
    _table = "stock_picking"
    _description = "Material Request"
    _order = "name desc"        
    
    _columns = {
        'type': fields.selection([('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal'), ('mr', 'Material Request'), ('mrr', 'Material Return')], 
                                 'Request Type', required=True, select=True, readonly=True, states={'creating':[('readonly',False)]}),
        'move_lines': fields.one2many('material.request.line', 'picking_id', 'Request Products', states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}),
        'mr_notes': fields.related('move_lines', 'mr_notes', type='text',
                                      string='Reason and Use'),
        'mr_dept_id': fields.many2one('hr.department', 'Department', states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}),
        'create_uid': fields.many2one('res.users', 'Creator',readonly=True),
        'message_ids': fields.one2many('mail.message', 'res_id',
            domain=lambda self: [('model', '=', 'stock.picking')],
            auto_join=True,
            string='Messages',
            help="Messages and communication history"),
        'mr_ticket_no': fields.char('Ticket#', size=16, track_visibility='onchange')
    }
    _defaults = {
        'type': 'mr',
        'move_type': 'one',
        'state': 'creating',
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Order Reference must be unique!'),
    ]
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'move_type':self._defaults['move_type'],
        })
        res = super(material_request, self).copy(cr, uid, id, default, context)
        return res       

    def check_access_rights(self, cr, uid, operation, raise_exception=True):
        #override in order to redirect the check of acces rights on the stock.picking object
        return self.pool.get('stock.picking').check_access_rights(cr, uid, operation, raise_exception=raise_exception)

    def check_access_rule(self, cr, uid, ids, operation, context=None):
        #override in order to redirect the check of acces rules on the stock.picking object
        return self.pool.get('stock.picking').check_access_rule(cr, uid, ids, operation, context=context)

    def _workflow_trigger(self, cr, uid, ids, trigger, context=None):
        #override in order to trigger the workflow of stock.picking at the end of create, write and unlink operation
        #instead of it's own workflow (which is not existing)
        return self.pool.get('stock.picking')._workflow_trigger(cr, uid, ids, trigger, context=context)

    def _workflow_signal(self, cr, uid, ids, signal, context=None):
        #override in order to fire the workflow signal on given stock.picking workflow instance
        #instead of it's own workflow (which is not existing)
        return self.pool.get('stock.picking')._workflow_signal(cr, uid, ids, signal, context=context)
        
    def create(self, cr, uid, vals, context=None):
        vals['state'] = 'draft'
        if not vals.get('name') or vals.get('name','/')=='/':
            if vals['type'] == 'mrr':
                vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'material.request.return') or '/'
            else:
                vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'material.request') or '/'
                
        order =  super(material_request, self).create(cr, uid, vals, context=context)
        return order

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)
        return super(material_request,self).search(cr, user, new_args, offset, limit, order, context, count)    
                
class material_request_line(osv.osv):
    _name = "material.request.line"
    _inherit = "stock.move"
    _table = "stock_move"
    _description = "Material Request Line"
    def _amount_line(self, cr, uid, ids, prop, arg, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = line.product_qty * line.price_unit
        return res    
    _columns = {
        'picking_id': fields.many2one('material.request', 'MR#', select=True,states={'done': [('readonly', True)]}),
        'mr_emp_id': fields.many2one('hr.employee','Employee'),
        'mr_sale_prod_id': fields.many2one('sale.product','Sale Product ID', ondelete="restrict"),
        'mr_notes': fields.text('Reason and use'),
        'mr_dept_id': fields.related('picking_id','mr_dept_id',string='Department',type='many2one',relation='hr.department',select=True),
        'mr_date_order': fields.related('picking_id','date',string='Order Date',type='datetime'),
        'pick_type': fields.related('picking_id','type',string='Picking Type',type='char'),
        'create_uid': fields.many2one('res.users', 'Creator',readonly=True),
        'price_subtotal': fields.function(_amount_line, string='Subtotal', digits_compute= dp.get_precision('Account')),
        #make the price's decimal precision as the 'Product Price'
        'price_unit': fields.float('Unit Price', digits_compute= dp.get_precision('Product Price'), help="Technical field used to record the product cost set by the user during a picking confirmation (when average price costing method is used)"),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Price'),
            required=True,states={'done': [('readonly', True)]},
            help="This is the quantity of products from an inventory "
                "point of view. For moves in the state 'done', this is the "
                "quantity of products that were actually moved. For other "
                "moves, this is the quantity of product that is planned to "
                "be moved. Lowering this quantity does not generate a "
                "backorder. Changing this quantity on assigned moves affects "
                "the product reservation, and should be done with care."
        ),
        'prod_categ_id': fields.related('product_id','categ_id',string='Product Category Type',type='many2one',relation="product.category",select=True),
    }
    _order = 'id'
    def default_mr_loc(self, cr, uid, context=None):
        if context is None:
            context = {}
        #material_request.type: mr or mrr
        req_type = context.get('req_type')
        if not req_type:
            req_type = 'mr'
        loc_stock_id = None
        loc_prod_id = None
        #get the default stock location
        cr.execute('select c.id \n'+
                    'from res_users a  \n'+
                    'left join stock_warehouse b on a.company_id = b.company_id  \n'+
                    'left join stock_location c on b.lot_stock_id = c.id \n'
                    'where a.id = %s', (uid,))
        loc_src = cr.fetchone()
        if loc_src:
            loc_stock_id = loc_src[0]           
        #get the default production location
        loc_obj = self.pool.get('stock.location')
        prod_loc_ids = loc_obj.search(cr,uid,[('usage','=','production')],context=context)
        if prod_loc_ids and prod_loc_ids[0]:
            prod_loc = loc_obj.browse(cr,uid,prod_loc_ids[0],context=context)
            loc_prod_id = prod_loc.id
        #set the locations by the request type
        loc_from_id = 0
        loc_to_id = 0
        if req_type == 'mr':
            if loc_stock_id:
                loc_from_id = loc_stock_id
            if loc_prod_id:
                loc_to_id = loc_prod_id
        if req_type == 'mrr':
            if loc_prod_id:
                loc_from_id = loc_prod_id
            if loc_stock_id:
                loc_to_id = loc_stock_id
        return loc_from_id, loc_to_id
                       
    def default_get(self, cr, uid, fields_list, context=None):
        resu = super(material_request_line,self).default_get(cr, uid, fields_list, context)
        loc_from_id, loc_to_id = self.default_mr_loc(cr, uid, context=context)
        resu.update({'location_id':loc_from_id, 'location_dest_id':loc_to_id})
        return resu
    
    def onchange_product_id(self, cr, uid, ids, prod_id=False, loc_id=False,
                            loc_dest_id=False, ):
        """ On change of product id, if finds UoM, UoS, quantity and UoS quantity.
        @param prod_id: Changed Product id
        @param loc_id: Source location id
        @param loc_dest_id: Destination location id
        @param partner_id: Address id of partner
        @return: Dictionary of values
        """
        if not prod_id:
            return {}
        user = self.pool.get("res.users").browse(cr,uid,uid)
        
        ctx = {'lang': user.lang,'location':loc_id}

        product = self.pool.get('product.product').browse(cr, uid, [prod_id], context=ctx)[0]
        uos_id  = product.uos_id and product.uos_id.id or False
        result = {
            'product_uom': product.uom_id.id,
            'product_uos': uos_id,
            'product_qty': product.qty_available,
            'product_uos_qty' : self.pool.get('stock.move').onchange_quantity(cr, uid, ids, prod_id, 1.00, product.uom_id.id, uos_id)['value']['product_uos_qty'],
            'prodlot_id' : False,
        }
        if not ids:
            result['name'] = product.partner_ref
        if loc_id:
            result['location_id'] = loc_id
        if loc_dest_id:
            result['location_dest_id'] = loc_dest_id
            
        #update the price_unit the and price_currency_id
        #default is the product's cost price
        price_unit = product.standard_price
        price_currency_id = None
        #get the final purchase price
        move_obj = self.pool.get('stock.move')
        #get the final purchase price
        move_ids = move_obj.search(cr,uid,[('product_id','=',prod_id),('state','=','done'),('type','=','in')],limit=1,order='create_date desc')
        if move_ids:
            move_price = move_obj.read(cr,uid,move_ids[0],['price_unit','price_currency_id'],context=ctx)
            price_unit = move_price['price_unit']
            price_currency_id = move_price['price_currency_id']
        result['price_unit'] = price_unit
        result['price_currency_id'] = price_currency_id
        
        return {'value': result}
    def check_access_rights(self, cr, uid, operation, raise_exception=True):
        #override in order to redirect the check of acces rights on the stock.picking object
        return self.pool.get('stock.move').check_access_rights(cr, uid, operation, raise_exception=raise_exception)

    def check_access_rule(self, cr, uid, ids, operation, context=None):
        #override in order to redirect the check of acces rules on the stock.picking object
        return self.pool.get('stock.move').check_access_rule(cr, uid, ids, operation, context=context)

    def _workflow_trigger(self, cr, uid, ids, trigger, context=None):
        #override in order to trigger the workflow of stock.picking at the end of create, write and unlink operation
        #instead of it's own workflow (which is not existing)
        return self.pool.get('stock.move')._workflow_trigger(cr, uid, ids, trigger, context=context)

    def _workflow_signal(self, cr, uid, ids, signal, context=None):
        #override in order to fire the workflow signal on given stock.picking workflow instance
        #instead of it's own workflow (which is not existing)
        return self.pool.get('stock.move')._workflow_signal(cr, uid, ids, signal, context=context)  
    
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)
        return super(material_request_line,self).search(cr, user, new_args, offset, limit, order, context, count)   
    def create(self, cr, user, vals, context=None):
        #add the procut_uom set by product's purchase uom
        if 'product_uom' not in vals:
            prod = self.pool.get('product.product').browse(cr, user, vals['product_id'], context=context)
            vals.update({'product_uom':prod.uom_id.id})            
        resu = super(material_request_line,self).create(cr, user, vals, context=context)
        return resu            
class stock_move(osv.osv):
    _inherit = "stock.move" 
    def _get_rec_info(self, cr, uid, ids, fields, args, context=None):
        result = {}
        for id in ids:
            result[id] = {'return_qty':0,}
        for m in self.browse(cr,uid,ids,context=context):
            return_qty = 0
            if m.state == 'done':
                for rec in m.move_history_ids2:
                    # only take into account 'product return' moves, ignoring any other
                    # kind of upstream moves, such as internal procurements, etc.
                    # a valid return move will be the exact opposite of ours:
                    #     (src location, dest location) <=> (dest location, src location))
                    if rec.state != 'cancel' \
                        and rec.location_dest_id.id == m.location_id.id \
                        and rec.location_id.id == m.location_dest_id.id:
                        return_qty += self.pool.get('product.uom')._compute_qty(cr, uid, m.product_uom.id, rec.product_qty, rec.product_uom.id)
            #calculate the product base uom quantity
            product_uom_base_qty = m.product_qty
            if m.product_uom.id != m.product_id.uom_id.id:
                product_uom_base_qty = self.pool.get('product.uom')._compute_qty_obj(cr, uid, m.product_uom, m.product_qty, m.product_id.uom_id)
            
            result[m.id].update({'return_qty':return_qty,'product_uom_base_qty':product_uom_base_qty})
        return result    
    _columns = {
        'type': fields.related('picking_id', 'type', type='selection', selection=[('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal'), ('mr', 'Material Request'), ('mrr', 'Material Return')], string='Shipping Type'),
        'create_uid': fields.many2one('res.users', 'Creator',readonly=True),
        'supplier_prod_name': fields.related('purchase_line_id', 'supplier_prod_name',string='Supplier Product Name',type="char",readonly=True,store=True),
        'return_qty': fields.function(_get_rec_info, type='float', string='Return Quantity', multi="rec_info", digits_compute=dp.get_precision('Product Price')),
        #make the price's decimal precision as the 'Product Price'
        'price_unit': fields.float('Unit Price', digits_compute= dp.get_precision('Product Price'), help="Technical field used to record the product cost set by the user during a picking confirmation (when average price costing method is used)"),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Price'),
            required=True,states={'done': [('readonly', True)]},
            help="This is the quantity of products from an inventory "
                "point of view. For moves in the state 'done', this is the "
                "quantity of products that were actually moved. For other "
                "moves, this is the quantity of product that is planned to "
                "be moved. Lowering this quantity does not generate a "
                "backorder. Changing this quantity on assigned moves affects "
                "the product reservation, and should be done with care."
        ),                
        'product_uom_base': fields.related('product_id','uom_id',type='many2one',relation='product.uom', string='Base UOM',readonly=True),
        'product_uom_base_qty': fields.function(_get_rec_info, type='float', string='Base Quantity', multi="rec_info", digits_compute=dp.get_precision('Product Unit of Measure'),readonly=True),
        'mfg_ids': fields.related('purchase_line_id','mfg_ids',type='many2many',relation='sale.product',string="MFG IDs"),      
    }

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)
        return super(stock_move,self).search(cr, user, new_args, offset, limit, order, context, count)  

    def action_done(self, cr, uid, ids, context=None):
        resu = super(stock_move,self).action_done(cr, uid, ids, context) 
        move_ids = []
        for move in self.browse(cr, uid, ids, context=context):
            if move.state == 'done':
                move_ids.append(move.id)
        self.write(cr, uid, move_ids, {'date': context.get('date',datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))}, context=context)
        return resu

    def _create_account_move_line(self, cr, uid, move, matches, src_account_id, dest_account_id, reference_amount, reference_currency_id, type='', context=None):
        val = super(stock_move,self)._create_account_move_line(cr, uid, move, matches, src_account_id, dest_account_id, reference_amount, reference_currency_id, type, context)
        #check if this move is a material request line move 
        mr_line = self.pool.get('material.request.line').browse(cr, uid, move.id, context=context)
        if mr_line.mr_sale_prod_id:
            #set the analytic_account_id to debit_line, the detail data ref _create_account_move_line() in product_fifo_lifo.stock.py
            if mr_line.mr_sale_prod_id.analytic_account_id and val and val[0]:
                if mr_line.pick_type == 'mr':
                    #debit dict data 
                    mline_data = val[0][2]
                else:
                    #credit dict data 
                    mline_data = val[1][2]
                mline_data.update({'analytic_account_id':mr_line.mr_sale_prod_id.analytic_account_id.id})
        return val
      
def _set_minimum_date(self, cr, uid, ids, name, value, arg, context=None):
    """ Calculates planned date if it is less than 'value'.
    @param name: Name of field
    @param value: Value of field
    @param arg: User defined argument
    @return: True or False
    """
    if not value:
        return False
    if isinstance(ids, (int, long)):
        ids = [ids]
    for pick in self.browse(cr, uid, ids, context=context):
        sql_str = """update stock_move set
                date_expected='%s'
            where
                picking_id=%s """ % (value, pick.id)
        if pick.min_date:
            sql_str += " and (date_expected='" + pick.min_date + "' or date_expected<'" + value + "')"
        cr.execute(sql_str)
    return True

def _set_maximum_date(self, cr, uid, ids, name, value, arg, context=None):
    """ Calculates planned date if it is greater than 'value'.
    @param name: Name of field
    @param value: Value of field
    @param arg: User defined argument
    @return: True or False
    """
    if not value:
        return False
    if isinstance(ids, (int, long)):
        ids = [ids]
    for pick in self.browse(cr, uid, ids, context=context):
        sql_str = """update stock_move set
                date_expected='%s'
            where
                picking_id=%d """ % (value, pick.id)
        if pick.max_date:
            sql_str += " and (date_expected='" + pick.max_date + "' or date_expected>'" + value + "')"
        cr.execute(sql_str)
    return True   

from openerp.addons.stock.stock import stock_picking as stock_picking_super     

def fields_view_get_pick(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
    if view_type == 'form' and not view_id:
        mod_obj = self.pool.get('ir.model.data')
        if self._name == "stock.picking.in":
            model, view_id = mod_obj.get_object_reference(cr, uid, 'stock', 'view_picking_in_form')
        if self._name == "stock.picking.out":
            model, view_id = mod_obj.get_object_reference(cr, uid, 'stock', 'view_picking_out_form')
        if self._name == "material.request":
            model, view_id = mod_obj.get_object_reference(cr, uid, 'metro_stock', 'view_material_request_form')
    return super(stock_picking_super, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)

stock_picking_super.fields_view_get = fields_view_get_pick
     
class stock_picking(osv.osv):
    _inherit = "stock.picking" 
        
    _columns = {   
        'create_uid': fields.many2one('res.users', 'Creator',readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True), 
        'account_move_ids': fields.one2many('account.move', 'picking_id',string = 'Stock Accout Move', readonly=False),
        'deliver_ticket_no': fields.char('Deliver Ticket#', size=50, track_visibility='onchange'),
        'mr_ticket_no': fields.char('Ticket#', size=16, track_visibility='onchange')
    }      
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)
        return super(stock_picking,self).search(cr, user, new_args, offset, limit, order, context, count)
    
    _order = 'name desc'  
    
    def action_done(self, cr, uid, ids, context=None):
        """Changes picking state to done.
        
        This method is called at the end of the workflow by the activity "done".
        @return: True
        """
        po_obj = self.pool.get('purchase.order')
        for pick in self.browse(cr,uid,ids,context):
            if pick.purchase_id:
                #if this is a out, then check  the purchase return                
                if pick.type=='out':
                    if pick.purchase_id:
                        #if this is purchase return
                        #1.then set the related purchase order shipped to False
                        po_obj.write(cr,uid,[pick.purchase_id.id],{'shipped':False})
                        '''
                        remove the auto invoice generating, by johnw, 10/10/2014
                        '''
                        '''
                        #2.if need create invoices after picking, then auto generate the invoie
                        if pick.invoice_state == '2binvoiced':
                            inv_create_obj = self.pool.get("stock.invoice.onshipping")
                            if not context:
                                context = {}
                            context.update({'active_model':'stock.picking.out','active_ids':[pick.id],'active_id':pick.id})
                            journal_id = inv_create_obj._get_journal(cr,uid,context)
                            inv_create_id = inv_create_obj.create(cr,uid,{'journal_id':journal_id},context)
                            pick_inv_ids = inv_create_obj.create_invoice(cr,uid,[inv_create_id],context)
                        '''
                #if this is related to a PO and need to create invoices after picking, then auto generate the invoie and valid the invoice.
                if pick.type=='in' and pick.invoice_state == '2binvoiced':
                    '''
                    remove the auto invoice generating, by johnw, 10/09/2014, for the price chaning, 
                    need user to adjust price on stock_move, 
                    otherwise user change the price on invoice, 
                    then the move price will be wrong, then the FIFO price will be wrong
                    '''
                    '''
                    inv_create_obj = self.pool.get("stock.invoice.onshipping")
                    if not context:
                        context = {}
                    context.update({'active_model':'stock.picking.in','active_ids':[pick.id],'active_id':pick.id})
                    journal_id = inv_create_obj._get_journal(cr,uid,context)
                    inv_create_id = inv_create_obj.create(cr,uid,{'journal_id':journal_id},context)
                    pick_inv_ids = inv_create_obj.create_invoice(cr,uid,[inv_create_id],context)
                    invoice_ids = pick_inv_ids.values()
                    '''
                    '''
                    #remove the auto validate, need the accoutant to validate manually.
                    wf_service = netsvc.LocalService("workflow")
                    for invoice_id in invoice_ids:
                        wf_service.trg_validate(uid, 'account.invoice', invoice_id, 'invoice_open', cr)
                    '''   

        super(stock_picking,self).action_done(cr,uid,ids,context)
        #fix the time issue to use utc now, by johnw
        self.write(cr, uid, ids, {'date_done': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')})
        return True            

    def action_confirm(self, cr, uid, ids, context=None):
        """ Add the lines aggisnment checking
        """
        resu = super(stock_picking,self).action_confirm(cr, uid, ids, context=context)
        if resu:
            pickings = self.browse(cr, uid, ids, context=context)
            todo = []
            for picking in pickings:
#                if picking.type in('mr','mrr'):
                for r in picking.move_lines:
                    if r.state == 'confirmed':
                        todo.append(r.id)
            if len(todo):
                self.pool.get('stock.move').check_assign(cr, uid, todo, context=context)
        return resu       
    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        res = super(stock_picking,self).do_partial(cr, uid, ids, partial_datas, context)
        #get the deliver ticket no from context, transfered from stock_partial_picking
        vals = {'deliver_ticket_no':context.get('deliver_ticket_no') and context.get('deliver_ticket_no') or None,
                'mr_ticket_no':context.get('mr_ticket_no') and context.get('mr_ticket_no') or None,}
        #get the delivered picking ids
        done_pick_ids = []
        for pick_id, done_pick_id in res.items():
            if done_pick_id.get('delivered_picking'):
                done_pick_ids.append(done_pick_id.get('delivered_picking'))
        #update ticket#
        self.write(cr, uid, done_pick_ids, vals, context=context)
        return res

    def _prepare_invoice_line(self, cr, uid, group, picking, move_line, invoice_id, invoice_vals, context=None):
        invoice_line_vals = super(stock_picking, self)._prepare_invoice_line(cr, uid, group, picking, move_line, invoice_id, invoice_vals, context=context)
        if invoice_vals['type'] in ('in_invoice', 'in_refund'):
            #check the 'property_stock_valuation_account_id' for the incoming stock, if it is true, then replace the invoice line account_id
            use_valuation_account = move_line.product_id.categ_id.prop_use_value_act_as_invoice
            if use_valuation_account:
                invoice_line_vals['account_id'] = move_line.product_id.categ_id.property_stock_valuation_account_id.id
        return invoice_line_vals
    #inherit from stock_cancel, to reset the picking date and deliver ticket#
    def action_revert_done(self, cr, uid, ids, context=None):
        resu = super(stock_picking, self).action_revert_done(cr, uid, ids, context=context)
        self.write(cr, uid, ids, {'deliver_ticket_no':None, 'mr_ticket_no':None, 'date_done':None})
        return resu
        
class stock_picking_out(osv.osv):
    _inherit = "stock.picking.out"   
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)
        return super(stock_picking_out,self).search(cr, user, new_args, offset, limit, order, context, count)
    _columns = {   
        'message_ids': fields.one2many('mail.message', 'res_id',
            domain=lambda self: [('model', '=', 'stock.picking')],
            auto_join=True,
            string='Messages',
            help="Messages and communication history"), 
        'account_move_ids': fields.one2many('account.move', 'picking_id',string = 'Stock Accout Move', readonly=False),
    }            
    _order = 'name desc'  
            
class stock_picking_in(osv.osv):
    _inherit = "stock.picking.in"
 
    _columns = {   
        'create_uid': fields.many2one('res.users', 'Creator',readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'min_date': fields.function(stock_picking_super.get_min_max_date, fnct_inv=_set_minimum_date, multi="min_max_date",
                 store=True, type='datetime', string='Scheduled Time', select=1, help="Scheduled time for the shipment to be processed"), 
        'max_date': fields.function(stock_picking_super.get_min_max_date, fnct_inv=_set_maximum_date, multi="min_max_date",
                 store=True, type='datetime', string='Max. Expected Date', select=2),
        'message_ids': fields.one2many('mail.message', 'res_id',
            domain=lambda self: [('model', '=', 'stock.picking')],
            auto_join=True,
            string='Messages',
            help="Messages and communication history"),
        #fields added to stock_picking_in/out also need add to stock_picking, since the read() method to the 2 classes are using stock_picking class, see addons/stock/stock.py.stock_picking_in
        'account_move_ids': fields.one2many('account.move', 'picking_id',string = 'Stock Accout Move', readonly=False),
        'deliver_ticket_no': fields.char('Deliver Ticket#', size=50, track_visibility='onchange')
    }     
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)
        return super(stock_picking_in,self).search(cr, user, new_args, offset, limit, order, context, count)   
    _order = 'name desc'      


class stock_inventory(osv.osv):
    _inherit = "stock.inventory"
    _order = "id desc"
    _columns = {
        'comments': fields.text('Comments', size=64, readonly=False, states={'done': [('readonly', True)]}),
        'inventory_date': fields.datetime('Inventory Date', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'create_uid': fields.many2one('res.users', 'Creator',readonly=True),
    }
    _defaults = {
        'inventory_date': datetime.datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
    }

    def action_done(self, cr, uid, ids, context=None):
        """ Finish the inventory
        @return: True
        """
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        for inv in self.browse(cr, uid, ids, context=context):
            context.update({'date': inv.inventory_date})
            move_obj.action_done(cr, uid, [x.id for x in inv.move_ids], context=context)
            # self.write(cr, uid, [inv.id], {'state':'done', 'date_done': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
            self.write(cr, uid, [inv.id], {'state': 'done',
                                           'date_done': inv.inventory_date},
                       context=context)
        return True

    def action_confirm(self, cr, uid, ids, context=None):
        """ Confirm the inventory and writes its finished date
        @return: True
        """
        if context is None:
            context = {}
        # to perform the correct inventory corrections we need analyze stock location by
        # location, never recursively, so we use a special context
        product_context = dict(context, compute_child=False)

        location_obj = self.pool.get('stock.location')
        for inv in self.browse(cr, uid, ids, context=context):
            move_ids = []
            for line in inv.inventory_line_id:
                pid = line.product_id.id
                product_context.update(uom=line.product_uom.id, to_date=inv.inventory_date, date=inv.inventory_date, prodlot_id=line.prod_lot_id.id)
                amount = location_obj._product_get(cr, uid, line.location_id.id, [pid], product_context)[pid]
                change = line.product_qty - amount
                lot_id = line.prod_lot_id.id
                if change:
                    location_id = line.product_id.property_stock_inventory.id
                    value = {
                        'name': _('INV:') + (line.inventory_id.name or ''),
                        'product_id': line.product_id.id,
                        'product_uom': line.product_uom.id,
                        'prodlot_id': lot_id,
                        'date': inv.inventory_date,
                    }

                    if change > 0:
                        value.update( {
                            'product_qty': change,
                            'location_id': location_id,
                            'location_dest_id': line.location_id.id,
                        })
                    else:
                        value.update( {
                            'product_qty': -change,
                            'location_id': line.location_id.id,
                            'location_dest_id': location_id,
                        })
                    move_ids.append(self._inventory_line_hook(cr, uid, line, value))
            self.write(cr, uid, [inv.id], {'state': 'confirm', 'move_ids': [(6, 0, move_ids)]})
            self.pool.get('stock.move').action_confirm(cr, uid, move_ids, context=context)
        return True

    def unlink(self, cr, uid, ids, context=None):
        inventories = self.read(cr, uid, ids, ['state'], context=context)
        unlink_ids = []
        for s in inventories:
            if s['state'] in ['draft','cancel']:
                unlink_ids.append(s['id'])
            else:
                raise osv.except_osv(_('Invalid Action!'), _('Only the physical inventory orders with Draft or Cancelled state can be delete!'))

        return super(stock_inventory, self).unlink(cr, uid, unlink_ids, context=context)

    def change_inventory_date(self, cr, uid, ids, context=None):
        if context is None:
            context= {}
        return {
            'name': 'Change Inventory Date Wizard',
            'res_model': 'stock.change.inventory.date',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def export_all_productS(self, cr, uid, ids, context=None):
        product_obj = self.pool.get('product.product')
        product_ids = product_obj.search(cr, uid, [], order='default_code asc', context=context)
        workbook = xlwt.Workbook()
        row = 0
        sheet = workbook.add_sheet('Products')
        sheet.write(row, 0, _('ERP #'))
        sheet.write(row, 1, _('Quantity'))
        sheet.write(row, 2, _('Name'))
        sheet.write(row, 3, _('Chinese Name'))
        sheet.write(row, 4, _('UOM English name'))
        sheet.write(row, 5, _('UOM Chinese name'))
        sheet.write(row, 6, _('UOM Purchase English name'))
        sheet.write(row, 7, _('UOM Purchase Chinese name'))
        sheet.write(row, 8, _('Part Type'))
        sheet.write(row, 9, _('Measure Type'))
        sheet.write(row, 10, _('UOM Category'))
        sheet.write(row, 11, _('UOM Purchase Category'))
        sheet.write(row, 12, _('Is Dual UOM'))
        for product in product_obj.browse(cr, uid, product_ids, context=context):
            row += 1
            sheet.write(row, 0, product.default_code)
            sheet.write(row, 1, product.qty_available)
            sheet.write(row, 2, product.name)
            sheet.write(row, 3, product.cn_name)
            sheet.write(row, 4, product.uom_id.name)
            sheet.write(row, 5, product.uom_id.cn_name)
            sheet.write(row, 6, product.uom_po_id.name)
            sheet.write(row, 7, product.uom_po_id.cn_name)
            sheet.write(row, 8, product.part_type)
            sheet.write(row, 9, product.measure_type)
            sheet.write(row, 10, product.uom_id.category_id.name)
            sheet.write(row, 11, product.uom_po_id.category_id.name)
            sheet.write(row, 12, product.uom_po_id.category_id.id == product.uom_id.category_id.id and 'No' or 'Yes')

        file_name = u'Inventory-List-%s.xls' % datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
        temp_xls_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xls')
        temp_xls_file_name = temp_xls_file.name
        temp_xls_file.close()
        workbook.save(temp_xls_file_name)

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/export/drawing_order_print_pdf?file_name=%s&file_data=%s' % (
                file_name, temp_xls_file_name),
            'target': 'self',
        }

    def export_lines(self, cr, uid, ids, context=None):
        workbook = xlwt.Workbook()
        inventory_names = []
        for inventory in self.browse(cr, uid, ids, context=context):
            row = 0
            inventory_name = utils._format_file_name(inventory.name)
            inventory_names.append(inventory_name)
            sheet = workbook.add_sheet(inventory.name[:20])
            sheet.write(row, 0, _('ERP #'))
            sheet.write(row, 1, _('Quantity'))
            sheet.write(row, 2, _('Name'))
            sheet.write(row, 3, _('Chinese Name'))
            sheet.write(row, 4, _('UOM ID'))
            sheet.write(row, 5, _('UOM English name'))
            sheet.write(row, 6, _('UOM Chinese name'))
            for line in inventory.inventory_line_id:
                row += 1
                sheet.write(row, 0, line.product_id.default_code)
                sheet.write(row, 1, line.product_qty)
                sheet.write(row, 2, line.product_id.name)
                sheet.write(row, 3, line.product_id.cn_name)
                sheet.write(row, 4, line.product_uom.id)
                sheet.write(row, 5, line.product_uom.name)
                sheet.write(row, 6, line.product_uom.cn_name)
        file_name = u'Inventory-List-%s.xls' % ('-'.join(inventory_names))
        temp_xls_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xls')
        temp_xls_file_name = temp_xls_file.name
        temp_xls_file.close()
        workbook.save(temp_xls_file_name)

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/export/drawing_order_print_pdf?file_name=%s&file_data=%s' % (
                file_name, temp_xls_file_name),
            'target': 'self',
        }

class stock_inventory_line(osv.osv):
    _inherit = "stock.inventory.line"
    _columns = {   
        'image_medium': fields.related('product_id','image_medium',type='binary',String="Medium-sized image"),
        'state': fields.related('inventory_id','state',type='selection',selection=(('draft', 'Draft'), ('cancel','Cancelled'), ('confirm','Confirmed'), ('done', 'Done')),
                                string='Status',readonly=True),
        'uom_categ_id': fields.related('product_uom','category_id',type='many2one',relation='product.uom.categ',String="UOM Category"),
    }
    #override the parent's _default_stock_location, to avoid the location reading right issue under multi company's environment 
    def _default_stock_location(self, cr, uid, context=None):
        loc_ids = self.pool.get('stock.location').search(cr, uid, [('usage','=','internal')], context=context)
        if loc_ids:
            return loc_ids[0]
        else:
            return False

    _defaults = {
        'location_id': _default_stock_location
    }    
    
    def on_change_product_id(self, cr, uid, ids, location_id, product_id, uom=False, to_date=False):
        '''
        Add the uom_categ_id, johnw, 01/07/2015
        '''
        res = super(stock_inventory_line, self).on_change_product_id(cr, uid, ids, location_id, product_id, uom, to_date)
        if not product_id:
            return res        
        product = self.pool.get('product.product').browse(cr, uid, product_id)
        if res['value'].get('product_uom') and res['value']['product_uom'] != product.uom_id.id:
            #if user changed product, then need to change to new product's uom, this is an issue in addons/stock.py
            res['value']['product_uom'] = product.uom_id.id
        res['value']['uom_categ_id'] = product.uom_id.category_id.id
        return res

from openerp.addons.procurement.procurement import stock_warehouse_orderpoint as stock_warehouse_orderpoint_sup

def stock_warehouse_orderpoint_default_get(self, cr, uid, fields, context=None):
    res = super(stock_warehouse_orderpoint_sup, self).default_get(cr, uid, fields, context)
    # default 'warehouse_id' and 'location_id'
    if 'warehouse_id' not in res:
        '''
        override the parent's logic, to avoid the warehouse reading right issue under multi company's environment
        '''
#            warehouse = self.pool.get('ir.model.data').get_object(cr, uid, 'stock', 'warehouse0', context)
        warehouse_ids = self.pool.get('stock.warehouse').search(cr, uid, [],context=context)
        res['warehouse_id'] = warehouse_ids[0]
    if 'location_id' not in res:
        warehouse = self.pool.get('stock.warehouse').browse(cr, uid, res['warehouse_id'], context)
        res['location_id'] = warehouse.lot_stock_id.id
    return res

stock_warehouse_orderpoint_sup.default_get = stock_warehouse_orderpoint_default_get      

class stock_warehouse_orderpoint(osv.osv):
    _inherit = "stock.warehouse.orderpoint"
    def create(self, cr, uid, vals, context=None):
        if not 'product_uom' in vals:
            prod = self.pool.get('product.product').browse(cr, uid, vals['product_id'], context=context)
            if prod:
                vals.update({'product_uom':prod.uom_id.id})
        return super(stock_warehouse_orderpoint,self).create(cr, uid, vals, context)

class product_category(osv.osv):
    _inherit = 'product.category'
    _columns = {
        #use valuation account as invoice account
        #使用存货科目作为生成凭据明细的会计科目,也就是凭据确认时应付账款的对方科目
        'prop_use_value_act_as_invoice': fields.property(None,
            type='boolean',
            string="Use valuation as invoice",
            view_load=True,
            help="Use Stock Valuation Account as the invoice counterpart account to the payable."),
    }

product_category()
      
def deal_args(obj,args):  
    new_args = []
    for arg in args:
        fld_name = arg[0]
        if fld_name in ('date', 'date_done'):
            fld_operator = arg[1]
            fld_val = arg[2]
            fld = obj._columns.get(fld_name)
            #['date','=','2013-12-12 16:00:00'] the '16' was generated for the timezone
            if fld._type == 'datetime' and fld_operator == "=" and fld_val.endswith('00:00'):
                time_start = [fld_name,'>=',fld_val]
                time_obj = datetime.datetime.strptime(fld_val,DEFAULT_SERVER_DATETIME_FORMAT)
                time_obj += relativedelta(days=1)
                time_end = [fld_name,'<=',time_obj.strftime(DEFAULT_SERVER_DATETIME_FORMAT)]
                new_args.append(time_start)
                new_args.append(time_end)
            else:
                new_args.append(arg)
        else:
            new_args.append(arg)    
    return new_args