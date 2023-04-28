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

import time
from lxml import etree

from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class rpt_inventory(osv.osv_memory):
    _name = "rpt.inventory"
    _inherit = "rpt.base"
    _description = "Inventory Report"
    _columns = {
        #report data lines
        'rpt_lines': fields.one2many('rpt.inventory.line', 'rpt_id', string='Report Line'),
        'date_from': fields.date("Start Date", required=True),
        'date_to': fields.date("End Date"),
        'product_ids': fields.many2many('product.product', string='Products'),
        'product_categ_ids': fields.many2many('product.category', string='Product Categories'),
        'location_ids': fields.many2many('stock.location', string='Locations', domain=[("usage","=",'internal')]),
        #has amount flag       
        'has_amount': fields.boolean("Has Amount", required=False),     
        }

    _defaults = {
        'type': 'stock_inventory',     
        'date_from': lambda *args:time.strftime('%Y-%m-01'), 
        'date_to': time.strftime('%Y-%m-%d'),
    }
    def _check_dates(self, cr, uid, ids, context=None):
        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.date_from and wiz.date_to and wiz.date_from > wiz.date_to:
                return False
        return True

    _constraints = [
        (_check_dates, 'The chosen periods have to belong to the same company.', ['date_from','date_to']),
    ]
    
    def get_report_name(self, cr, uid, id, rpt_name, context=None):
        has_amount = self.read(cr, uid, id, ['has_amount'],context=context)['has_amount']
        if has_amount:
            return "Inventory Amount Report"
        else:
            return "Inventory Quantity Report"
    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        res = []
        for id in ids:
            res.append((id,'%s'%(id,) ))
        return res
    def _init_rpt_line(self, cr, uid, product_id, uom_id):
        return {
            'seq': 0,
            'product_id': product_id,
            'uom_id': uom_id,
            
            'begin_qty': 0.0,
            'begin_price': 0.0,
            'begin_amount': 0.0,
            
            'income_qty': 0.0,
            'income_price': 0.0,
            'income_amount': 0.0,
            
            'outgo_qty':0.0,
            'outgo_price': 0.0,
            'outgo_amount': 0.0,
            
            'end_qty': 0.0,
            'end_price': 0.0,
            'end_amount': 0.0,
         }
                
    def run_stock_inventory(self, cr, uid, ids, context=None):
        prod_obj = self.pool.get('product.product')
        
        if context is None: context = {}         
        rpt = self.browse(cr, uid, ids, context=context)[0]
        #report data line
        rpt_lns = {}
        #context for the inventory query
        c = context.copy()
        #get the product_ids
        prod_ids = [prod.id for prod in rpt.product_ids]
        if rpt.product_categ_ids:
            categ_ids = [categ.id for categ in rpt.product_categ_ids]
            categ_prod_ids = self.pool.get('product.product').search(cr, uid, [('categ_id','child_of',categ_ids)],context=context)
            prod_ids.extend(categ_prod_ids)
        if not prod_ids:
            prod_ids = self.pool.get('product.product').search(cr, uid, [('type','=','product')])
        #init report line data
        uom_ids = self.pool.get('product.product').read(cr, uid, prod_ids, ['uom_id'], context=context)
        prod_uom_ids = {}
        for uom in uom_ids:
            prod_uom_ids[uom['id']] = uom['uom_id'][0]
        for prod_id in prod_ids:
            if not rpt_lns.has_key(prod_id):
                rpt_lns[prod_id] = (self._init_rpt_line(cr, uid, prod_id, prod_uom_ids.get(prod_id,False)))
        #the locations parameter
        if rpt.location_ids:
            location_ids = [location.id for location in rpt.location_ids]
            c['location'] = location_ids
            c['compute_child']= True
        #need money parameter
        if rpt.has_amount:
            c['need_money'] = True
        '''========begin quantity========='''
        if rpt.date_from:
            c['from_date'] = False
            c['to_date'] = rpt.date_from
            c.update({ 'states': ('done',), 'what': ('in', 'out') })
            stock = prod_obj.get_product_available(cr, uid, prod_ids, context=c)
            for prod_id, inv_data in stock.items():
                qty = 0
                amount = 0
                if c.get('need_money',False):
                    qty = inv_data[0]
                    amount = inv_data[1]
                else:
                    qty = inv_data
                rpt_lns[prod_id].update({'begin_qty':qty,'begin_amount':amount})
        
        #date parameter for the income and outgo query
        if rpt.date_from:
            c['from_date'] = rpt.date_from
        if rpt.date_to:
            c['to_date'] = rpt.date_to
        '''========income quantity========='''
        c.update({ 'states': ('done',), 'what': ('in') })
        stock = prod_obj.get_product_available(cr, uid, prod_ids, context=c)
        for prod_id, inv_data in stock.items():
            qty = 0
            amount = 0
            if c.get('need_money',False):
                qty = inv_data[0]
                amount = inv_data[1]
            else:
                qty = inv_data
            rpt_lns[prod_id].update({'income_qty':qty,'income_amount':amount})
        '''========outgo quantity========='''
        c.update({ 'states': ('done',), 'what': ('out') })
        stock = prod_obj.get_product_available(cr, uid, prod_ids, context=c)
        for prod_id, inv_data in stock.items():
            qty = 0
            amount = 0
            if c.get('need_money',False):
                qty = -inv_data[0]
                amount = -inv_data[1]
            else:
                qty = -inv_data
            rpt_lns[prod_id].update({'outgo_qty':qty,'outgo_amount':amount})
        '''========end quantity========='''
        c['from_date'] = False
        if rpt.date_to:
            c['to_date'] = rpt.date_to
        else:
            c['to_date'] = False
        c.update({ 'states': ('done',), 'what': ('in', 'out') })
        stock = prod_obj.get_product_available(cr, uid, prod_ids, context=c)
        for prod_id, inv_data in stock.items():
            qty = 0
            amount = 0
            if c.get('need_money',False):
                qty = inv_data[0]
                amount = inv_data[1]
            else:
                qty = inv_data
            rpt_lns[prod_id].update({'end_qty':qty,'end_amount':amount})     
        '''========return data to rpt_base.run_report()========='''    
        new_rpt_lns = []
        seq = 0
        for rpt_ln in rpt_lns.values():
            if rpt_ln['begin_qty'] == 0.0 \
                 and rpt_ln['income_qty'] == 0.0 \
                 and rpt_ln['outgo_qty'] == 0.0 \
                 and rpt_ln['end_qty'] == 0.0:
                continue
            seq += 1
            rpt_ln['seq'] = seq
            new_rpt_lns.append(rpt_ln)
        return self.pool.get('rpt.inventory.line'), new_rpt_lns
    
    def _pdf_data(self, cr, uid, ids, form_data, context=None):
        rpt_name = ''
        if form_data['has_amount'] == True:
            rpt_name = 'rpt.inventory.amount'
        else:
            rpt_name = 'rpt.inventory.qty'
        return {'xmlrpt_name': rpt_name}
    
rpt_inventory()

class rpt_inventory_line(osv.osv_memory):
    _name = "rpt.inventory.line"
    _inherit = "rpt.base.line"
    _description = "Inventory Report Lines"
    _columns = {
        'rpt_id': fields.many2one('rpt.inventory', 'Report'),
        'seq': fields.integer('Sequence',),
        'product_id': fields.many2one('product.product', 'Product',),
        'uom_id': fields.many2one('product.uom', 'Unit of Measure',),
        
        'begin_qty': fields.float('Begin Quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
        'begin_price': fields.float('Begin Price', digits_compute=dp.get_precision('Product Price')), #useless now
        'begin_amount': fields.float('Begin Amount', digits_compute=dp.get_precision('Account')),
        
        'income_qty': fields.float('Income Quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
        'income_price': fields.float('Income Price', digits_compute=dp.get_precision('Product Price')), #useless now
        'income_amount': fields.float('Income Amount', digits_compute=dp.get_precision('Account')),
        
        'outgo_qty': fields.float('Outgo Quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
        'outgo_price': fields.float('Outgo Price', digits_compute=dp.get_precision('Product Price')), #useless now
        'outgo_amount': fields.float('Outgo Amount', digits_compute=dp.get_precision('Account')),
        
        'end_qty': fields.float('End Quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
        'end_price': fields.float('End Price', digits_compute=dp.get_precision('Product Price')), #useless now
        'end_amount': fields.float('End Amount', digits_compute=dp.get_precision('Account')),
        }

rpt_inventory_line()

from openerp.report import report_sxw
class inv_rpt(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(inv_rpt, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'obj_ids_name': self.obj_ids_name,
        })
    def obj_ids_name(self, obj_ids):
        obj_ids_name = [obj.name for obj in obj_ids]
        return ','.join(obj_ids_name)     
report_sxw.report_sxw('report.rpt.inventory.qty', 'rpt.inventory', 'addons/metro_accounts/report/rpt_inventory_qty.rml', parser=inv_rpt, header='internal')
report_sxw.report_sxw('report.rpt.inventory.amount', 'rpt.inventory', 'addons/metro_accounts/report/rpt_inventory_amount.rml', parser=inv_rpt, header='internal landscape')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
