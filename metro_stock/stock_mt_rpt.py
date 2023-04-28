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

#
# Please note that these reports are not multi-currency !!!
#
import logging
from openerp.osv import fields,osv
from openerp import tools
import openerp.addons.decimal_precision as dp
from openerp.addons.metro import utils

from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
_logger = logging.getLogger(__name__)


class stock_mt_rpt(osv.osv):
    _name = "stock.mt.rpt"
    _description = "Material Requisition Report"
    _auto = False
    _columns = {
        'picking_id': fields.many2one('stock.picking', 'Picking'),   
        'date': fields.datetime('Date'),          
        'date_done': fields.datetime('Done Date'),        
        'mr_date_order': fields.datetime('Order Date'),
        'mr_dept_id': fields.many2one('hr.department','Department'),
        'prod_categ_id': fields.many2one('product.category','Product Category'),
        
        'product_id': fields.many2one('product.product', 'Product'),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure'),       
        'price_unit': fields.float('Unit Price', digits_compute= dp.get_precision('Account'), group_operator='avg'),
        'price_subtotal': fields.float('Subtotal', digits_compute= dp.get_precision('Account')),
        
        'mr_emp_id': fields.many2one('hr.employee','Employee'),
        'mr_sale_prod_id': fields.many2one('sale.product','Sale Product ID', ondelete="restrict"),
        'mr_notes': fields.text('Reason and use'),
        'name': fields.char('Description'),
        
        'location_id': fields.many2one('stock.location', 'Source Location'),
        'location_dest_id': fields.many2one('stock.location', 'Destination Location'),
        
        'create_date': fields.datetime('Creation Date'),
        'state': fields.selection([('draft', 'New'),
                                   ('cancel', 'Cancelled'),
                                   ('waiting', 'Waiting Another Move'),
                                   ('confirmed', 'Waiting Availability'),
                                   ('assigned', 'Available'),
                                   ('done', 'Done'),
                                   ], 'Status'),
        'date_from':fields.function(lambda *a,**k:{}, type='datetime',string="Date Sart",),
        'date_to':fields.function(lambda *a,**k:{}, type='datetime',string="Date End",),
    }
    
    _order = 'id desc'
    
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'datetime' field query
        new_args = utils.deal_args_dt(cr, user, self, args,['date', 'date_done', 'mr_date_order'],context=context)
        #the date_start/end parameter
        for arg in new_args:
            if arg[0] == 'date_from':
                arg[0] = 'mr_date_order'
                arg[1] = '>='
            if arg[0] == 'date_to':
                arg[0] = 'mr_date_order'
                arg[1] = '<='
                #for the end date, need add one day to use as the end day
                time_obj = datetime.strptime(arg[2],DEFAULT_SERVER_DATETIME_FORMAT)
                time_obj += relativedelta(days=1)                                
                arg[2] = time_obj.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        return super(stock_mt_rpt,self).search(cr, user, new_args, offset, limit, order, context, count)
        
    def init(self, cr):
        tools.sql.drop_view_if_exists(cr, 'stock_mt_rpt')
        cr.execute("""
            create or replace view stock_mt_rpt as (
                select
                a.id,
                a.picking_id,
                a.date,
                b.date_done,
                b.date as mr_date_order,
                b.mr_dept_id as mr_dept_id,
                d.categ_id as prod_categ_id,
                
                a.product_id,
                a.product_qty,
                a.product_uom,
                a.price_unit,
                a.price_unit*a.product_qty as price_subtotal,
                
                a.mr_emp_id,
                a.mr_sale_prod_id,
                a.mr_notes,
                a.name,
                
                a.location_id,
                a.location_dest_id,
                a.create_date,
                a.state
                from stock_move a
                join stock_picking b on a.picking_id = b.id
                join product_product c on a.product_id = c.id
                join product_template d on c.product_tmpl_id = d.id
                where b.type in ('mr','mrr')       
            )
        """)
stock_mt_rpt()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
