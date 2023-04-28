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

import base64
import xlrd

import os

class stock_import_inventory(osv.osv_memory):
    _name = "stock.import.inventory"
    _description = "Import Inventory"

    def _default_location(self, cr, uid, ids, context=None):
        try:
            loc_model, location_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')
        except ValueError, e:
            return False
        return location_id or False

    _columns = {
        'location_id': fields.many2one('stock.location', 'Location', required=True),
        'import_file': fields.binary('File', filters="*.xls"),
        #to consider the product current inventory or not, if yes then add the current inventory to the upload excel quantity as the quantity to do physical inventory
        'consider_inventory': fields.boolean('Consider Current Inventory', select=True),
        #overwrite current inventory, if yes deduct the current inventory from the current xls product qty
        #'overwrite_inventory': fields.boolean('Overwrite Current Inventory', help='If yes, deduct the xls product qty with current inventory'),
        'all_done': fields.boolean('All Data Imported', readonly=True, select=True), 
        'result_line': fields.one2many('stock.import.inventory.result', 'import_id', 'Importing Result', readonly=True), 
        'file_template': fields.binary('Template File', readonly=True),
        'file_template_name': fields.char('Template File Name'),
    }
    
    def _get_template(self, cr, uid, context):
        cur_path = os.path.split(os.path.realpath(__file__))[0]
        path = os.path.join(cur_path,'stock_import_template.xls')
        data = open(path,'rb').read().encode('base64')
#        data = os.path.getsize(path)
        return data
    
    _defaults = {
        'location_id': _default_location,
        'file_template': _get_template,
        'file_template_name': 'stock_import_template.xls'
    }

    def view_init(self, cr, uid, fields_list, context=None):
        """
         Creates view dynamically and adding fields at runtime.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param context: A standard dictionary
         @return: New arch of view with new columns.
        """
        if context is None:
            context = {}
        super(stock_import_inventory, self).view_init(cr, uid, fields_list, context=context)

        if len(context.get('active_ids',[])) > 1:
            raise osv.except_osv(_('Error!'), _('You cannot perform this operation on more than one Stock Inventories.'))

        if context.get('active_id', False):
            stock = self.pool.get('stock.inventory').browse(cr, uid, context.get('active_id', False))
        return True


    def import_inventory(self, cr, uid, ids, context=None):
        """ To Import stock inventory according to the excel file
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: the ID or list of IDs if we want more than one
        @param context: A standard dictionary
        @return:
        """
        if context is None:
            context = {}

        inventory_line_obj = self.pool.get('stock.inventory.line')
        prod_obj = self.pool.get('product.product')

        inventory_id = context and context.get('active_id', False) or False
        import_inventory = self.browse(cr, uid, ids[0], context=context)
        location = import_inventory.location_id 
        #get the uploaded data
        import_data = base64.decodestring(import_inventory.import_file)
        excel_data = xlrd.open_workbook(file_contents=import_data,formatting_info=False, on_demand=True)
        sheet = excel_data.sheets()[0]
        row_cnt = sheet.nrows
        col_cnt = sheet.ncols
        # check the column list: 'default_code,product_qty' must be in the list
        row_data = sheet.row_values(0);
        code_idx = 0
        qty_idx = 0
        id_idx = -1
        try:
            # get the data column index
            code_idx = row_data.index('default_code')
            qty_idx = row_data.index('product_qty')
        except Exception:
            raise osv.except_osv(_('Error!'), _('please make sure the default_code and product_qty column in the column list.'))
        try:
            # get the 'id' column index
            id_idx = row_data.index('id')
        except Exception:
            id_idx = -1        
        #loop to insert inventory line data
        error_rows = []
        for i in range(1,row_cnt):
            row_data = sheet.row_values(i);
            #get the product data
            product_id = None
            if id_idx < 0 or not row_data[id_idx] or row_data[id_idx] == '':
                #if there is no id data, then use default_code to get product id
                ids = prod_obj.search(cr,uid,[('default_code','=',row_data[code_idx])],context=context)
                if not ids or len(ids) == 0:
                    #if system can not find the product info, then set the import fail flag and message to false
                    error_rows.append({'row':i+1,'default_code':row_data[code_idx],'msg':_('System can not find this product')})
                    continue
                product_id = ids[0]
            else:
                product_id = row_data[id_idx]
            prod = prod_obj.browse(cr, uid,product_id,context=context)
            if not prod:
                #if can not find the product info, then set the import fail flag and message to false
                error_rows.append({'row':i+1,'default_code':'','msg':_('System can not find this product')})
                continue
            else:
                product_qty = row_data[qty_idx]
                if import_inventory.consider_inventory:
                    product_qty += prod.qty_available
                #if import_inventory.overwrite_inventory:
                #    product_qty -= prod.qty_available
                inv_line_data = {'inventory_id':inventory_id,'location_id':location.id,
                              'product_id':product_id,'product_uom':prod.uom_id.id,'product_qty':product_qty}
                inventory_line_obj.create(cr,uid,inv_line_data,context=context)
            #set import success flag
            row_data.append(True)
            
        #SET THE RESULT DATA
        if len(error_rows) > 0:
            #set the failed flag
            self.write(cr,uid,import_inventory.id,{'all_done':False})
            #put the data to result_line
            result_obj = self.pool.get('stock.import.inventory.result')
            for result in error_rows:
                result.update({'import_id':import_inventory.id})
                result_obj.create(cr,uid,result,context=context)
        else:
            #set done flag
            self.write(cr,uid,import_inventory.id,{'all_done':True})
        
        mod_obj = self.pool.get('ir.model.data')
        views = mod_obj.get_object_reference(cr, uid, 'metro_stock', 'view_stock_import_inventory_result')
        view_id = views and views[1]
                
        return {
            'name': _('Import Inventory Result'),
            'context': context,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.import.inventory',
            'views': [(view_id,'form')],
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': import_inventory.id,
        }


class stock_import_inventory_result(osv.osv_memory):
    _name = "stock.import.inventory.result"
    _description = "Import Inventory Result"

    _columns = {
        'import_id': fields.many2one('stock.import.inventory', 'Stock Inventory Import'),
        'row': fields.char('Row#', size=5, readonly=True),
        'msg': fields.char('Error Message', size=100, readonly=True),        
    }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
