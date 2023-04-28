# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP S.A. <http://www.openerp.com>
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

import re
from osv import fields, osv
import tools
from tools.translate import _
from openerp.addons.metro_purchase.purchase import deal_args
from openerp.addons.stock.product import product_product as stock_product
import openerp.addons.decimal_precision as dp
from openerp.addons.product import product
from openerp.tools import float_round, float_is_zero, float_compare
import math
from openerp import SUPERUSER_ID
from openerp.addons.metro import utils

STEEL_DENSITY = 7850
ALU_DENSITY = 2800
ALU_MATERIALS = 'AL 5052'
STEEL_MATERIALS = ['960E', '70HG', 'Q235', 'Q235 CP', '16Mn']
SHEET = 'sheet'
ROUND_PIPE = 'round_pipe'
ROUND_BAR = 'round_bar'
SQUARE_PIPE = 'square_pipe'
SQUARE_BAR = 'square_bar'
TEN_SQUARE_NINE = 1000000000.0
DUPLICATION_UOMS = ['Piece(s)', 'Set(s)', 'Box(es)', 'Pair(s)']

class product_template(osv.osv):
    _inherit = "product.template"
    _columns = {
        'uom_id': fields.many2one('product.uom', 'Unit of Measure', required=True, write=['metro.group_data_maintain'],
                                  read=['base.group_user'], track_visibility='onchange'),
        'uom_po_id': fields.many2one('product.uom', 'Purchase Unit of Measure', required=True,
                                     write=['metro.group_data_maintain'], read=['base.group_user'],
                                     track_visibility='onchange'),
    }


class product_product(osv.osv):
    _inherit = "product.product"

    _columns = {
        'measure_type': fields.selection(
            [('single', 'Single Unit'), ('mmp', 'Multi Units Multi Products'), ('msp', 'Multi Units Single Product')],
            string='UOM Measure Type', required=True, write=['metro.group_data_maintain'], read=['base.group_user'],
            track_visibility='onchange', help='Choose Multi Units Single Product for PMS, PML part type'),
        'uom_categ_id': fields.many2one('product.uom.categ', 'UOM Category', required=True,
                                        write=['metro.group_data_maintain'], read=['base.group_user'],
                                        track_visibility='onchange'),
        'uom_po_price': fields.float('Purchase Unit Price', track_visibility='onchange',
                                     digits_compute=dp.get_precision('Product Unit of Measure')),
        'uom_po_factor': fields.related('uom_po_id', 'factor_display', type='float', digits=(12, 4), string='UOM Ratio',
                                        readonly=True)
        #		'msp_uom_list': fields.one2many('product.uom','product_id',string='Units of Measure'),
    }

    _defaults = {
        'measure_type': 'single',
        'uom_categ_id': 1,
    }

    def has_related_product(self, cr, uid, ids, context=None):
        '''
        --关联到某个表某列的相关表
        SELECT
            tc.constraint_name, tc.table_name, kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        into tmp_prod_related_tables
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
        WHERE constraint_type = 'FOREIGN KEY'
        AND ccu.table_name='product_product'
        and ccu.column_name='id'


        SELECT
            tc.constraint_name, tc.table_name, kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        into tmp_uom_related_tables
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
        WHERE constraint_type = 'FOREIGN KEY'
        AND ccu.table_name='product_uom'
        and ccu.column_name='id'

        select a.table_name,a.column_name,b.column_name
        from tmp_prod_related_tables a,
        tmp_uom_related_tables b
        where a.table_name = b.table_name
        and b.column_name like '%uom%'

        "account_analytic_line";"product_id";"product_uom_id"
        "account_move_line";"product_id";"product_uom_id"
        "make_procurement";"product_id";"uom_id"
        "mrp_bom";"product_id";"product_uom"
        "mrp_production";"product_id";"product_uom"
        "mrp_production_product_line";"product_id";"product_uom"
        "procurement_order";"product_id";"product_uom"
        "pur_invoice_line";"product_id";"product_uom_id"
        "pur_req_line";"product_id";"product_uom_id"
        "pur_req_po_line";"product_id";"product_uom_id"
        "purchase_order_line";"product_id";"product_uom"
        "sale_order_line";"product_id";"product_uom"
        "stock_inventory_line";"product_id";"product_uom"
        "stock_inventory_line_split";"product_id";"product_uom"
        "stock_move_consume";"product_id";"product_uom"
        "stock_move";"product_id";"product_uom"
        "stock_move_scrap";"product_id";"product_uom"
        "stock_move_split";"product_id";"product_uom"
        "stock_partial_move_line";"product_id";"product_uom"
        "stock_partial_picking_line";"product_id";"product_uom"
        "stock_warehouse_orderpoint";"product_id";"product_uom"

select 1 as flag from account_analytic_line where product_id=3059
union
select 1 as flag from account_move_line where product_id=3059
union
select 1 as flag from make_procurement where product_id=3059
union
select 1 as flag from mrp_bom where product_id=3059
union
select 1 as flag from mrp_production where product_id=3059
union
select 1 as flag from mrp_production_product_line where product_id=3059
union
select 1 as flag from procurement_order where product_id=3059
union
select 1 as flag from pur_invoice_line where product_id=3059
union
select 1 as flag from pur_req_line where product_id=3059
union
select 1 as flag from pur_req_po_line where product_id=3059
union
select 1 as flag from purchase_order_line where product_id=3059
union
select 1 as flag from sale_order_line where product_id=3059
union
select 1 as flag from stock_inventory_line where product_id=3059
union
select 1 as flag from stock_inventory_line_split where product_id=3059
union
select 1 as flag from stock_move_consume where product_id=3059
union
select 1 as flag from stock_move where product_id=3059
union
select 1 as flag from stock_move_scrap where product_id=3059
union
select 1 as flag from stock_move_split where product_id=3059
union
select 1 as flag from stock_partial_move_line where product_id=3059
union
select 1 as flag from stock_partial_picking_line where product_id=3059
union
select 1 as flag from stock_warehouse_orderpoint where product_id=3059
limit 1

        '''
        sql = 'select 1 as flag from account_analytic_line where product_id=%s \
				union \
				select 1 as flag from account_move_line where product_id=%s \
				union \
				select 1 as flag from make_procurement where product_id=%s \
				union \
				select 1 as flag from mrp_bom where product_id=%s \
				union \
				select 1 as flag from mrp_production where product_id=%s \
				union \
				select 1 as flag from mrp_production_product_line where product_id=%s \
				union \
				select 1 as flag from procurement_order where product_id=%s \
				union \
				select 1 as flag from pur_invoice_line where product_id=%s \
				union \
				select 1 as flag from pur_req_line where product_id=%s \
				union \
				select 1 as flag from pur_req_po_line where product_id=%s \
				union \
				select 1 as flag from purchase_order_line where product_id=%s \
				union \
				select 1 as flag from sale_order_line where product_id=%s \
				union \
				select 1 as flag from stock_inventory_line where product_id=%s \
				union \
				select 1 as flag from stock_inventory_line_split where product_id=%s \
				union \
				select 1 as flag from stock_move_consume where product_id=%s \
				union \
				select 1 as flag from stock_move where product_id=%s \
				union \
				select 1 as flag from stock_move_scrap where product_id=%s \
				union \
				select 1 as flag from stock_move_split where product_id=%s \
				union \
				select 1 as flag from stock_partial_move_line where product_id=%s \
				union \
				select 1 as flag from stock_partial_picking_line where product_id=%s \
				union \
				select 1 as flag from stock_warehouse_orderpoint where product_id=%s \
				limit 1'
        for id in ids:
            id_params = []
            i = 0
            while i < 21:
                id_params.append(id)
                i += 1
            cr.execute(sql, id_params)
            res = cr.fetchone()
            found_id = res and res[0] or False
            if found_id:
                return True

        return False

    def onchange_measure_type(self, cr, uid, ids, default_code, measure_type, context=None):
        uom_categ_id = ''
        uom_id = ''
        if measure_type == 'single':
           uom_categ_id = 1
        if measure_type == 'mmp':
            uom_categ_id = ''
            # find the uom category for the product with measure type: 'msp', 'Multi Units Single Product'
        if measure_type == 'msp':
            uom_categ_obj = self.pool.get('product.uom.categ')
            categ_name = 'MSP_%s' % default_code
            # find the product's uom category  by name like :categ_112130_1
            uom_categ = uom_categ_obj.search(cr, uid, [('name', '=', categ_name)], context=context)
            if len(uom_categ) > 0:
                uom_categ_id = uom_categ[0]
            else:
                mod_name, uom_categ_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_product',
                                                                                             'uom_categ_msp_dummy')
                mod_name, uom_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_product',
                                                                                       'uom_msp_dummy')

        value = {'uom_categ_id': uom_categ_id, 'uom_id': uom_id, 'uom_po_id': uom_id}
        #		value = {'uom_categ_id':uom_categ_id}
        res = {'value': value}
        return res

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context:
            context = {}
        if context.get('not_check_uom_category', False):
            if 'uom_id' in vals or 'uom_po_id' in vals:
                # do the units changing checking
                check_ids = set()
                uom_obj = self.pool.get('product.uom')
                if 'uom_id' in vals:
                    new_uom = uom_obj.browse(cr, uid, vals['uom_id'], context=context)
                    for product in self.browse(cr, uid, ids, context=context):
                        old_uom = product.uom_id
                        if old_uom.category_id.id != new_uom.category_id.id:
                            # check if there orders related to this product
                            check_ids.add(product.id)
                if 'uom_po_id' in vals:
                    new_uom = uom_obj.browse(cr, uid, vals['uom_po_id'], context=context)
                    for product in self.browse(cr, uid, ids, context=context):
                        old_uom = product.uom_po_id
                        if old_uom.category_id.id != new_uom.category_id.id:
                            # check if there orders related to this product
                            check_ids.add(product.id)

                if len(check_ids) and self.has_related_product(cr, uid, check_ids, context):
                    raise osv.except_osv(_('Unit of Measure categories Mismatch!'), _(
                        "New Unit of Measure '%s' must belong to same Unit of Measure category '%s' as of old Unit of Measure '%s'. If you need to change the unit of measure, you may deactivate this product from the 'Procurements' tab and create a new one.") % (
                                         new_uom.name, old_uom.category_id.name, old_uom.name,))

        resu = super(product_product, self).write(cr, uid, ids, vals, context=context)
        # update the 'Multi Units Single Product's uom category
        self.update_msp_uom_categ(cr, uid, ids[0], vals, context)
        return resu

    def create(self, cr, uid, vals, context=None):
        new_id = super(product_product, self).create(cr, uid, vals, context=context)
        self.update_msp_uom_categ(cr, uid, new_id, vals, context)
        return new_id

    # This function dectects the pipe type and dimension from the name and material
    # Return:
    # part_type: product part type
    # pipe_type: round pipe, round bar, square pipe, square bar
    # dimension: tuple, varies depends on pipe type
    def get_pipe_info(self, cr, uid, product_id, context=None):
        result = {
            # 'part_type': '',
            # 'type': '',
            # 'dimension': (),
            # 'ton_ratio': 1.0,
        }
        if product_id:
            product = self.browse(cr, uid, product_id, context=context)
            if product.part_type in ['PMS', 'PML']:
                result['part_type'] = product.part_type
                density = STEEL_DENSITY
                if product.material:
                    if product.material.find('AL 5052') != -1:
                        density = ALU_DENSITY
                result['density'] = density
                name = product.name.lower()
                if product.part_type == 'PMS':
                    dimensions = re.findall(r'(\d+)\s*[x|\*]\s*(\d+)\s*[x|\*]\s*(\d+)', name)
                    # print(dimensions)
                    if len(dimensions) > 0:
                        if len(dimensions[0]) == 3:
                            result['type'] = SHEET
                            x = int(dimensions[0][0])
                            y = int(dimensions[0][1])
                            z = int(dimensions[0][2])
                            result['dimension'] = (x, y, z)
                            result['ton_ratio'] = TEN_SQUARE_NINE / (x * y * z * density)
                else:
                    # PML part type
                    type = False
                    if re.match(r'.*square\s+pipe.*', name):
                        type = SQUARE_PIPE
                    elif name.find('square') != -1:
                        type= SQUARE_BAR
                    elif re.match(ur'.*pipe\s+\u00F8.*', unicode(name), flags=re.UNICODE):
                        type = ROUND_PIPE
                    elif name.find('round') != -1:
                        type = ROUND_BAR
                    if type:
                        result['type'] = type
                        if type == ROUND_BAR:
                            dimensions = re.findall(r'(\d+)\s*[x|\*]\s*(\d+)', name)
                            if len(dimensions) > 0:
                                if len(dimensions[0]) == 2:
                                    x = int(dimensions[0][0])
                                    y = int(dimensions[0][1])
                                    result['dimension'] = (x, y)
                                    result['ton_ratio'] = TEN_SQUARE_NINE * 4.0 / (math.pi * x * x * density)
                        else:
                            dimensions = re.findall(r'(\d+)\s*[x|\*]\s*(\d+)\s*[x|\*]\s*(\d+)', name)
                            if len(dimensions) > 0:
                                if len(dimensions[0]) == 3:
                                    x = int(dimensions[0][0])
                                    y = int(dimensions[0][1])
                                    z = int(dimensions[0][2])
                                    result['dimension'] = (x, y, z)
                                    if type == SQUARE_BAR:
                                        result['ton_ratio'] = TEN_SQUARE_NINE / (x * y * density)
                                    elif type == SQUARE_PIPE:
                                        result['ton_ratio'] = TEN_SQUARE_NINE / ((x * y - (x - 2 * z) * (y - 2 * z)) * density)
                                    else:
                                        # ROUND PIPE
                                        result['ton_ratio'] = TEN_SQUARE_NINE * 4.0 / (math.pi * abs(x * x - (x - 2 * y) * (x - 2 * y)) * density)

        return result

    def create_interchange_uom_categ(self, cr, uid, product_code, context=None):
        categ_name = 'MSP_%s' % product_code
        categ_obj = self.pool.get('product.uom.categ')
        categ_ids = categ_obj.search(cr, uid, [('name','=',categ_name)], context=context)
        if not categ_ids:
            uom_categ_id = categ_obj.create(cr, uid,{'name': categ_name,
                                                    'is_interchange': True})
        else:
            uom_categ_id = categ_ids[0]
        return uom_categ_id

    def create_uom(self, cr, uid, categ_id, name, cn_name, ratio=1.0, uom_type='reference', code=None, context=None):
        uom_obj = self.pool.get('product.uom')
        uom_ids = uom_obj.search(cr, uid, [('category_id','=', categ_id),
                                           '|',('name','=',name),('cn_name','=',cn_name)], context=None)
        if not uom_ids:
            uom_id = uom_obj.create(cr, uid, {
                'name': name,
                'cn_name': cn_name,
                'code': code or False,
                'category_id': categ_id,
                'factor': ratio,
                'uom_type': uom_type,
                'rounding': 0.0001
            }, context=context)
        else:
            uom_id = uom_ids[0]
        return uom_id

    def create_pms_pml_uoms(self, cr, uid, categ_id, pipe_info, context=None):
        if categ_id and pipe_info:
            if pipe_info['part_type'] in ['PMS','PML']:
                ratio = pipe_info['ton_ratio']
                uom_type = 'reference'
                if ratio > 1.0:
                    uom_type = 'bigger'
                elif ratio < 1.0:
                    uom_type = 'smaller'
                if pipe_info['part_type'] == 'PMS':
                    sheet_uom_id = self.create_uom(cr, uid, categ_id,  'Sheet(s)', u'张',code='SH',
                                                               context=context)
                    ton_uom_id = self.create_uom(cr, uid, categ_id, 'Ton(s)', u'吨', ratio=ratio,
                                                             uom_type=uom_type, code='T', context=context)
                    return [sheet_uom_id, ton_uom_id]
                else:
                    meter_uom_id = self.create_uom(cr, uid, categ_id, 'Meter(s)', u'米', code='M',
                                                               context=context)
                    ton_uom_id = self.create_uom(cr, uid, categ_id, 'Ton(s)', u'吨', ratio=ratio,
                                                             uom_type=uom_type, code='T', context=context)
                    return [meter_uom_id, ton_uom_id]
        return []

    def update_msp_uom_categ(self, cr, uid, product_id, vals, context=None):
        if not product_id:
            return
        product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
        # if the uom category for the 'Multi Units Single Product' is the dummy category, then need to create one, add update the prodcut's uom category
        if product.measure_type == 'msp':
            mod_name, categ_dummy_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_product',
                                                                                           'uom_categ_msp_dummy')
            if product.uom_categ_id.id == categ_dummy_id:
                # create a new uom category
                # new_uom_categ_id = self.pool.get('product.uom.categ').create(cr, uid,
                #                                                              {'name': 'MSP_%s' % product.default_code,
                #                                                               'is_interchange': True})
                # create a new uom of the new category base on part type
                # new_uom_id = self.pool.get('product.uom').create(cr, uid,
                #                                                  {'name': 'BaseUnit', 'category_id': new_uom_categ_id,
                #                                                   'factor': 1, 'rounding': 0.0001}, context)
                categ_id = self.create_interchange_uom_categ(cr, uid, product.default_code, context=context)
                pipe_info = self.get_pipe_info(cr, uid, product_id, context=context)
                # print(pipe_info)
                uom_ids = self.create_pms_pml_uoms(cr, SUPERUSER_ID, categ_id, pipe_info, context=context)
                if len(uom_ids) == 2:
                # update product's uom category and uom, po uom
                    self.pool.get('product.product').write(cr, uid, [product_id],
                                                           {'uom_categ_id': categ_id,
                                                            'uom_id': uom_ids[0],
                                                            'uom_po_id': uom_ids[1]}, context)


    def open_msp_uom_list(self, cr, uid, ids, context=None):
        ir_model_data_obj = self.pool.get('ir.model.data')
        ir_model_data_id = ir_model_data_obj.search(cr, uid, [['model', '=', 'ir.ui.view'],
                                                              ['name', '=', 'product_uom_measure_tree_view']],
                                                    context=context)
        if ir_model_data_id:
            res_id = ir_model_data_obj.read(cr, uid, ir_model_data_id, fields=['res_id'])[0]['res_id']
        uom_categ_id = context['default_category_id']
        return {
            'type': 'ir.actions.act_window',
            'name': 'Product Units of Measure',
            'view_type': 'form',
            'view_mode': 'tree,form',
            #            'view_id': [res_id],
            'res_model': 'product.uom',
            'context': context,
            'domain': "[('category_id','=',%s)]" % uom_categ_id,
            'nodestroy': True,
            'target': 'current',
        }


def product_product_onchange_uom(self, cursor, user, ids, uom_id, uom_po_id):
    if uom_id:
        uom_obj = self.pool.get('product.uom')
        uom = uom_obj.browse(cursor, user, [uom_id])[0]
        if not uom_po_id:
            return {'value': {'uom_po_id': uom_id}}
        else:
            uom_po = uom_obj.browse(cursor, user, [uom_po_id])[0]
            if uom.category_id.id != uom_po.category_id.id:
                return {'value': {'uom_po_id': uom_id}}
    return False


product.product_product.onchange_uom = product_product_onchange_uom


def product_template_write(self, cr, uid, ids, vals, context=None):
    #	if 'uom_po_id' in vals:
    #		new_uom = self.pool.get('product.uom').browse(cr, uid, vals['uom_po_id'], context=context)
    #		for product in self.browse(cr, uid, ids, context=context):
    #			old_uom = product.uom_po_id
    #			if old_uom.category_id.id != new_uom.category_id.id:
    #				raise osv.except_osv(_('Unit of Measure categories Mismatch!'), _("New Unit of Measure '%s' must belong to same Unit of Measure category '%s' as of old Unit of Measure '%s'. If you need to change the unit of measure, you may deactivate this product from the 'Procurements' tab and create a new one.") % (new_uom.name, old_uom.category_id.name, old_uom.name,))
    return super(product.product_template, self).write(cr, uid, ids, vals, context=context)


product.product_template.write = product_template_write


class product_uom_category(osv.osv):
    _inherit = 'product.uom.categ'
    _columns = {
        'cn_name': fields.char('Chinese Name', size=64),
        'is_interchange': fields.boolean('Interchange Category?', help='Indicate this category is used for convert UOM cross normal category ex: meter to ton, square to ton'),
        'uom_ids': fields.one2many('product.uom', 'category_id', 'UOMs'),

    }

    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if name:
            ids = self.search(cr, user, [('name', '=', name)] + args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, user, [('cn_name', '=', name)] + args, limit=limit, context=context)
            if not ids:
                # Do not merge the 2 next lines into one single search, SQL search performance would be abysmal
                # on a database with thousands of matching products, due to the huge merge+unique needed for the
                # OR operator (and given the fact that the 'name' lookup results come from the ir.translation table
                # Performing a quick memory merge of ids in Python will give much better performance
                ids = set()
                # we may underrun the limit because of dupes in the results, that's fine
                ids.update(self.search(cr, user, args + [('name', operator, name)],
                                       limit=(limit and (limit - len(ids)) or False), context=context))
                if not limit or len(ids) < limit:
                    ids.update(self.search(cr, user, args + [('cn_name', operator, name)],
                                           limit=(limit and (limit - len(ids)) or False), context=context))
                ids = list(ids)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
        result = self.name_get(cr, user, ids, context=context)
        return result


    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        chinese = (utils.get_user_language == 'zh_CN')
        def _name_get(d, chinese=False):
            name = d.get('name', '')
            cn_name = d.get('cn_name', False)
            if cn_name and cn_name != name:
                if chinese:
                    name = '%s/%s' % (cn_name, name)
                else:
                    name = '%s/%s' % (name, cn_name)
            return (d['id'], name)

        result = []
        for categ in self.browse(cr, user, ids, context=context):
            mydict = {
                'id': categ.id,
                'name': categ.name,
                'cn_name': categ.cn_name,
            }
            result.append(_name_get(mydict, chinese))
        return result

class product_uom(osv.osv):
    _inherit = ["mail.thread", "product.uom"]
    _name = "product.uom"

    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if name:
            ids = self.search(cr, user, [('code', '=', name)] + args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, user, [('name', '=', name)] + args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, user, [('cn_name', '=', name)] + args, limit=limit, context=context)
            if not ids:
                # Do not merge the 2 next lines into one single search, SQL search performance would be abysmal
                # on a database with thousands of matching products, due to the huge merge+unique needed for the
                # OR operator (and given the fact that the 'name' lookup results come from the ir.translation table
                # Performing a quick memory merge of ids in Python will give much better performance
                ids = set()
                ids.update(
                    self.search(cr, user, args + [('code', operator, name)], limit=limit, context=context))
                if not limit or len(ids) < limit:
                    # we may underrun the limit because of dupes in the results, that's fine
                    ids.update(self.search(cr, user, args + [('name', operator, name)],
                                           limit=(limit and (limit - len(ids)) or False), context=context))
                if not limit or len(ids) < limit:
                    ids.update(self.search(cr, user, args + [('cn_name', operator, name)],
                                           limit=(limit and (limit - len(ids)) or False), context=context))
                ids = list(ids)
            if not ids:
                ptrn = re.compile('(\[(.*?)\])')
                res = ptrn.search(name)
                if res:
                    ids = self.search(cr, user, [('code', '=', res.group(2))] + args, limit=limit,
                                      context=context)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
        result = self.name_get(cr, user, ids, context=context)
        return result

    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        chinese = (utils.get_user_language == 'zh_CN')
        def _name_get(d, chinese=False):
            name = d.get('name', '')
            cn_name = d.get('cn_name', False)
            category = d.get('category', False)
            if cn_name and cn_name != name:
                if chinese:
                    name = '%s/%s' % (cn_name, name)
                else:
                    name = '%s/%s' % (name, cn_name)
            if category:
                name = '[%s]%s'% (category, name)
            return (d['id'], name)

        result = []
        for uom in self.browse(cr, user, ids, context=context):
            mydict = {
                'id': uom.id,
                'name': uom.name,
                'cn_name': uom.cn_name,
                'code': uom.code,
            }
            # if uom.category_id.name.find('MSP_') != -1:
            #     mydict.update({'category': uom.category_id.name})
            result.append(_name_get(mydict, chinese))
        return result


    def name_create(self, cr, uid, name, context=None):
        """ The UoM category and factor are required, so we'll have to add temporary values
            for imported UoMs """
        raise osv.except_osv(_('Error'), _('Quick creation is not allowed to Unit of Measure!'))

    def _factor_display(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for uom in self.browse(cursor, user, ids, context=context):
            if uom.uom_type == 'bigger':
                res[uom.id] = uom.factor and (1.0 / uom.factor) or 0.0
            else:
                res[uom.id] = uom.factor
        return res

    _columns = {
        'code': fields.char('Code',size=64),
        'cn_name': fields.char('Chinese Name', size=64),
        'is_interchange': fields.related('category_id','is_interchange', type='boolean', readonly=False,string='Is Interchange?'),
        'factor_display': fields.function(_factor_display, digits=(12, 4), string='Ratio', ),
        'create_uid': fields.many2one('res.users', 'Creator', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'note': fields.text('Note'),

    }
    _defaults = {
        'rounding': 0.0001,
    }

    def has_related_data(self, cr, uid, ids, context=None):
        sql = 'select 1 as flag from account_analytic_line where product_uom_id=%s \
                union \
                select 1 as flag from account_invoice_line where uos_id=%s \
                union \
                select 1 as flag from account_move_line where product_uom_id=%s \
                union \
                select 1 as flag from make_procurement where uom_id=%s \
                union \
                select 1 as flag from mrp_bom where product_uom=%s \
                union \
                select 1 as flag from mrp_bom where product_uos=%s \
                union \
                select 1 as flag from mrp_production_product_line where product_uom=%s \
                union \
                select 1 as flag from mrp_production_product_line where product_uos=%s \
                union \
                select 1 as flag from mrp_production where product_uom=%s \
                union \
                select 1 as flag from mrp_production where product_uos=%s \
                union \
                select 1 as flag from procurement_order where product_uom=%s \
                union \
                select 1 as flag from procurement_order where product_uos=%s \
                union \
                select 1 as flag from pur_history_line where product_uom=%s \
                union \
                select 1 as flag from pur_invoice_line where product_uom_id=%s \
                union \
                select 1 as flag from pur_req_line where product_uom_id=%s \
                union \
                select 1 as flag from pur_req_po_line where product_uom_id=%s \
                union \
                select 1 as flag from purchase_order_line where product_uom=%s \
                union \
                select 1 as flag from sale_config_settings where time_unit=%s \
                union \
                select 1 as flag from sale_order_line where product_uom=%s \
                union \
                select 1 as flag from sale_order_line where product_uos=%s \
                union \
                select 1 as flag from stock_inventory_line where product_uom=%s \
                union \
                select 1 as flag from stock_inventory_line_split where product_uom=%s \
                union \
                select 1 as flag from stock_move_consume where product_uom=%s \
                union \
                select 1 as flag from stock_move where product_uom=%s \
                union \
                select 1 as flag from stock_move where product_uos=%s \
                union \
                select 1 as flag from stock_move_scrap where product_uom=%s \
                union \
                select 1 as flag from stock_move_split where product_uom=%s \
                union \
                select 1 as flag from stock_partial_move_line where product_uom=%s \
                union \
                select 1 as flag from stock_partial_picking_line where product_uom=%s \
                union \
                select 1 as flag from stock_warehouse_orderpoint where product_uom=%s \
                limit 1 \
                '
        for id in ids:
            id_params = [id for i in range(30)]
            cr.execute(sql, id_params)
            res = cr.fetchone()
            found_id = res and res[0] or False
            if found_id:
                return True

        return False

    def create(self, cr, uid, vals, context=None):
        # check the duplicated name under same category
        if 'name' in vals and 'category_id' in vals:
            if not vals['name'] in DUPLICATION_UOMS:
                exist_ids = self.search(cr, uid, [('name', '=', vals['name']), ('category_id', '=', vals['category_id'])])
                if len(exist_ids) > 0:
                    raise osv.except_osv(_('Error'), _("Duplicated UOM name of same category"))
        return super(product_uom, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        check_ids = set()
        if 'category_id' in vals:
            for uom in self.browse(cr, uid, ids, context=context):
                if uom.category_id.id != vals['category_id']:
                    check_ids.add(uom.id)
        if 'uom_type' in vals:
            for uom in self.browse(cr, uid, ids, context=context):
                if uom.uom_type != vals['uom_type']:
                    check_ids.add(uom.id)
        if 'factor' in vals:
            for uom in self.browse(cr, uid, ids, context=context):
                if not float_is_zero(uom.factor - vals['factor'], precision_rounding=uom.rounding):
                    check_ids.add(uom.id)
        if len(check_ids) > 0 and self.has_related_data(cr, uid, ids, context):
            raise osv.except_osv(_('Warning!'), _(
                "There are related business data with '%s', cannot change the Category,Type or Ratio.") % (uom.name,))
        # check the duplicated name under same category
        if 'name' in vals or 'category_id' in vals:
            id = ids[0]
            uom = self.browse(cr, uid, id, context=context)
            # HoangTK - Allow piece, set duplication
            if not vals['name'] in DUPLICATION_UOMS:
                domain = [('id', '!=', id)]
                if 'name' not in vals:
                    domain.append(('name', '=', uom.name))
                else:
                    domain.append(('name', '=', vals['name']))
                if 'category_id' not in vals:
                    domain.append(('category_id', '=', uom.category_id.id))
                else:
                    domain.append(('category_id', '=', vals['category_id']))

                exist_ids = self.search(cr, uid, domain)
                if len(exist_ids) > 0:
                    raise osv.except_osv(_('Error'), _("Duplicated UOM name of same category"))

        track_fields = {'name': 'Name',
                        'cn_name': 'Chinese Name',
                        'code': 'Part Number',
                        'factor': 'Ratio'}
        changes = []
        for field, description in track_fields.iteritems():
            if field in vals:
                for uom in self.browse(cr, uid, ids, context=context):
                    current_val = getattr(uom, field) and getattr(uom, field) or ''
                    changes.append(track_fields[field] + ' changed (%s->%s)' % (current_val, vals[field]))
        if changes:
            self.message_post(cr, uid, ids, body=','.join(changes), context=context)
        return super(product_uom, self).write(cr, uid, ids, vals, context=context)


from openerp.addons.product import product


def uom_write(self, cr, uid, ids, vals, context=None):
    #	if 'category_id' in vals:
    #		for uom in self.browse(cr, uid, ids, context=context):
    #			if uom.category_id.id != vals['category_id']:
    #				raise osv.except_osv(_('Warning!'),_("Cannot change the category of existing Unit of Measure '%s'.") % (uom.name,))
    return super(product.product_uom, self).write(cr, uid, ids, vals, context=context)


product.product_uom.write = uom_write
