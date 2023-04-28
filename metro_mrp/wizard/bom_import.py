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
import re
import types
import os

class bom_import(osv.osv_memory):
    _name = "bom.import"
    _description = "Import Bill of Material"

    _columns = {
        'mrp_bom_id': fields.many2one('mrp.bom','BOM'),
        'import_file': fields.binary('Select your Excel File', filters="*.xls", required=True),
        'file_template': fields.binary('Template File', readonly=True),
        'file_template_name': fields.char('Template File Name'),
    }
    def _get_template(self, cr, uid, context):
        cur_path = os.path.split(os.path.realpath(__file__))[0]
        path = os.path.join(cur_path,'bom_import_template.xls')
        data = open(path,'rb').read().encode('base64')
        return data
            
    _defaults = { 
        'file_template': _get_template,
        'file_template_name': 'bom_import_template.xls'
    }    
    def default_get(self, cr, uid, fields, context=None):
        """
         To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary with default values for all field in ``fields``
        """
        if context is None:
            context = {}
        res = super(bom_import, self).default_get(cr, uid, fields, context=context)
        mrp_bom_id = context and context.get('active_id', False) or False
        active_model = context and context.get('active_model', False) or False
        if active_model and active_model == 'project.project':
            project = self.pool.get('project.project').browse(cr, uid, mrp_bom_id, context=context)            
            mrp_bom_id = project.bom_id and project.bom_id.id or False
        if mrp_bom_id:
            mrp_bom = self.pool.get('mrp.bom').browse(cr, uid, mrp_bom_id, context=context)
            res.update({'mrp_bom_id': mrp_bom_id, 'product_id':mrp_bom.product_id.id, 'name':mrp_bom.name})
        return res

    def import_data(self, cr, uid, ids, context=None):
        """ To Import BOM according to the excel file
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: the ID or list of IDs if we want more than one
        @param context: A standard dictionary
        @return:
        """
        if context is None:
            context = {}
        
        order = self.browse(cr,uid,ids[0],context=context)
        #get the uploaded data
        import_data = base64.decodestring(order.import_file)
        excel_data = xlrd.open_workbook(file_contents=import_data)
        sheet = excel_data.sheets()[0]
        row_cnt = sheet.nrows
        
        '''
        level_no: the root product will be ‘root’, other follows the #.#.# format, and must be unique in one excel.
        erp_part_no: the part# of erp
        quantity:the quantity
        '''
        #1 check the column list: 'level_no,part_no,bom_name,quantity' must be in the list
        row_data = sheet.row_values(0);
        level_no_idx = 0
        part_no_idx = 0
        bom_name_idx = 0
        quantity_idx = 0
        route_name_idx = 0
        common_bom_idx = -1
        sequence_idx = -1
        id_idx = -1
        direct_bom_find_idx = -1
        
        try:
            # get the data column index
            level_no_idx = row_data.index('level_no')
            part_no_idx = row_data.index('part_no')
            part_name_idx = row_data.index('part_name')
            bom_name_idx = row_data.index('bom_name')
            quantity_idx = row_data.index('quantity')
            route_name_idx = row_data.index('route_name')
            no_consume_idx = row_data.index('no_consume')
        except Exception:
            raise osv.except_osv(_('Error!'), _('please make sure the "level_no, part_no, part_name, bom_name, quantity, route_name, no_consume" columns in the column list.'))
        try:
            # get the 'id' column index
            id_idx = row_data.index('id')
        except Exception:
            id_idx = -1 
        try:
            # get the 'common_bom' column index
            common_bom_idx = row_data.index('common_bom')
        except Exception:
            common_bom_idx = -1   
        try:
            sequence_idx = row_data.index('sequence')
        except Exception:
            sequence_idx = -1    
        try:
            direct_bom_find_idx = row_data.index('direct_bom_find')
        except Exception:
            direct_bom_find_idx = -1              
            
        header_idxs={'level_no_idx':level_no_idx,
                     'part_no_idx':part_no_idx,
                     'part_name_idx':part_name_idx,
                     'bom_name_idx':bom_name_idx,
                     'quantity_idx':quantity_idx,
                     'route_name_idx':route_name_idx,
                     'common_bom_idx':common_bom_idx,
                     'sequence_idx':sequence_idx,
                     'id_idx':id_idx,
                     'direct_bom_find_idx':direct_bom_find_idx,
                     'no_consume_idx':no_consume_idx}
                    
        #2 find all of the rows with level_no starting with 'root_'
        root_level_prefix = 'root_'
        #root bom row range, format:{rboom1_level_no:(row_start,row_end),...rboomn_level_no:(row_start,row_end)}
        root_boms = {}
        curr_root_level = None
        curr_root_row_start = None
        for i in range(1,row_cnt):
            row_data = sheet.row_values(i);
            level_no = row_data[level_no_idx]
            #first line level_no must be a root boom
            if i == 1 and not level_no.startswith(root_level_prefix):
                raise osv.except_osv(_('Error!'), _('First row must be a root boom, the level_no should start with "root_"'))
            if level_no.startswith(root_level_prefix):
                if root_boms.get(level_no,False):
                    raise osv.except_osv(_('Error!'), _('Root BOM level_no "%s" is duplicated with others'%(level_no,)))
                if curr_root_row_start:
                    root_boms[curr_root_level]=(curr_root_row_start, i-1)
                curr_root_level = level_no
                curr_root_row_start = i
        if curr_root_level and not root_boms.get(curr_root_level,False):
            root_boms[curr_root_level]=(curr_root_row_start, row_cnt-1)
        #for the existing boom, only add import one root boom
        if order.mrp_bom_id and len(root_boms) > 1:
            raise osv.except_osv(_('Error!'), _('Only can import one bom to existing BOM!'))
            
        #loop the root boom to import boom
        mrp_bom_obj = self.pool.get('mrp.bom')
        new_bom_ids = []
        for rbom_level_no, rbom_row in root_boms.items():
            parsed_rows = self._parse_bom(cr, uid, sheet, rbom_level_no, rbom_row[0], rbom_row[1], header_idxs, context=context)
            #having mrp_bom_id: do top BOM updating
            bom_master = parsed_rows[rbom_level_no]
            if order.mrp_bom_id:
                #if from an existing bom ID, then close the window, and refresh parent to show the new data
                mrp_bom_obj.write(cr, uid, order.mrp_bom_id.id, bom_master, context=context)        
                #for existing bomm updating, there will be only one BOOM, so return abort loop and return direct    
                return {'type': 'ir.actions.act_window_close'} 
            else:
                #Show the created new BOM in list view
                new_bom_id = mrp_bom_obj.create(cr, uid, bom_master, context=context)
                new_bom_ids.append(new_bom_id)

        #Show the created new BOM in list view
        return {
            'domain': "[('id', '=', %s)]"%(new_bom_ids,),
            'name': _('MRP BOM'),
            'view_type':'form',
            'view_mode':'tree,form',
            'res_model': 'mrp.bom',
            'type':'ir.actions.act_window',
            'context':context,
        }
            
    def _parse_bom(self,cr, uid, sheet,root_level_no,start_row,end_row, header_idxs, context=None):     
        level_no_idx = header_idxs['level_no_idx']
        part_no_idx = header_idxs['part_no_idx']
        part_name_idx = header_idxs['part_name_idx']
        bom_name_idx = header_idxs['bom_name_idx']
        quantity_idx = header_idxs['quantity_idx']
        route_name_idx = header_idxs['route_name_idx']
        common_bom_idx = header_idxs['common_bom_idx']
        sequence_idx = header_idxs['sequence_idx']
        id_idx = header_idxs['id_idx']
        direct_bom_find_idx = header_idxs['direct_bom_find_idx']
        no_consume_idx = header_idxs['no_consume_idx']
                                        
        #2 loop to check data, and put data to cache if all are OK
        '''
        the regex for the level# like: 1, 1.1, 1.1.1
        ([1-9]+\d*\.)* : no, one or more char like "#.", and the "#" must be greater than zero
        [1-9]+\d*$ : the suffix must be a number, and greater than zero 
        '''
        level_pattern = re.compile(r'L([1-9]+\d*\.)*[1-9]+\d*$')
        parsed_rows = {}
        prod_obj = self.pool.get('product.product')
        bom_obj = self.pool.get('mrp.bom')
        route_obj = self.pool.get('mrp.routing')
        for i in range(start_row,end_row+1):
            row_data = sheet.row_values(i);
            #=========validate the level_no============
            level_no = row_data[level_no_idx]
            #first line level_no must be root_level_no
            if i == start_row and level_no != root_level_no:
                raise osv.except_osv(_('Error!'), _('level_no of bom first line row must be "%s"'%(root_level_no,)))
            parsed_row = {}
            #for the rows not root line
            if i > start_row:
                if level_no is not types.StringType:
                    level_no = str(level_no)
                    if level_no == '':
                        level_no = '0'
                #check the level_no format
                if not level_pattern.match(level_no):
                    raise osv.except_osv(_('Error!'), _('level_no %s at row %s must follow the format #.#.#'%(level_no, i+1,)))
                #level_no must be unique
                if level_no in parsed_rows:                    
                    raise osv.except_osv(_('Error!'), _('level_no %s at row %s already exists, duplicated with order rows!'%(level_no, i+1,)))
                #find the parent row, level_no must have parent
                parent_level_no = ''
                pos = level_no.rfind('.')
                if pos != -1:
                    parent_level_no = level_no[0:pos]
                    if parent_level_no not in parsed_rows:
                        raise osv.except_osv(_('Error!'), _('level_no %s at row %s can not find the parent BOM'%(level_no, i+1,)))
                else:
                    parent_level_no = root_level_no
                #add to parent row's childs
                parent_level_row = parsed_rows.get(parent_level_no)
                childs = parent_level_row.get('bom_lines')
                if not childs:
                    childs = []
                    parent_level_row.update({'bom_lines':childs})
                childs.append((0, 0, parsed_row))
            #=========check the product existing============
            product = None
            common_bom_id = None
            common_bom = None
            if common_bom_idx >= 0 and row_data[common_bom_idx].upper() == 'Y':
                #find the common bom
                ids = bom_obj.search(cr,uid,[('code','=',row_data[part_no_idx]),('is_common','=',True)],context=context)
                if not ids or len(ids) == 0:
                    raise osv.except_osv(_('Error!'), _('the common BOM of row %s does not exist'%(i+1,)))
                common_bom_id = ids[0]
                common_bom = bom_obj.browse(cr, uid, common_bom_id, context=context)
            elif id_idx < 0 or not row_data[id_idx] or row_data[id_idx] == '':
                #if there is no id data, then use default_code to get product id
                if row_data[part_no_idx] and row_data[part_no_idx].strip() != "":
                    ids = prod_obj.search(cr,uid,[('default_code','=',row_data[part_no_idx].strip())],context=context)
                elif row_data[part_name_idx] and row_data[part_name_idx].strip() != "":
                    ids = prod_obj.search(cr,uid,[('name','=',row_data[part_name_idx].strip())],context=context)
                if not ids or len(ids) == 0:
                    raise osv.except_osv(_('Error!'), _('the product[%s] of row %s does not exist'%(row_data[part_no_idx], i+1,)))
                product = prod_obj.browse(cr, uid, ids[0], context=context)
            else:
                product = prod_obj.browse(cr, uid, row_data[id_idx], context=context)
                if not product:
                    raise osv.except_osv(_('Error!'), _('the product of row %s does not exist'%(i+1,)))
                    
                
            #=========check the quantity============
            quantity = row_data[quantity_idx]
            pattern_number = re.compile(r'\d+\.*\d*$')
            if quantity is not types.StringType:
                quantity = str(quantity)
                if quantity == '':
                    quantity = '0'
            if not pattern_number.match(quantity) or float(quantity) == 0:
                raise osv.except_osv(_('Error!'), _('the quantity of row %s must be a number and larger than zero!'%(i+1,)))
            
            #=========check the routing============
            route_name = row_data[route_name_idx]
            routing_id = None
            if (route_name and route_name.strip() != ""):
                route_ids = route_obj.search(cr,uid,[('name','=',route_name.strip())],context=context)
                if not route_ids:
                    raise osv.except_osv(_('Error!'), _('the route "%s" of row %s can be be find!'%(route_name,i+1,)))
                routing_id = route_ids[0]
            
            #=========check the bom name============
            bom_name = row_data[bom_name_idx]
            if (not bom_name or bom_name == ''):
                if product:
                    bom_name = product.name
                elif common_bom:
                    bom_name = common_bom.name
                    
            #=========check the sequence============
            sequence = 0
            if sequence_idx >= 0:
                sequence = row_data[sequence_idx]
                pattern_number = re.compile(r'\d+\.*\d*$')
                if sequence is not types.StringType:
                    sequence = str(sequence)
                    if sequence == '':
                        sequence = '0'
                if sequence != '0' and not pattern_number.match(sequence):
                    raise osv.except_osv(_('Error!'), _('the sequence of row %s must be a number!'%(i+1,)))
            
            #=========set the row data============
            if common_bom_id:
                parsed_row.update({'create_from_common':True,
                                   'common_bom_id':common_bom_id,
                                #'name':'[%s]%s'%(level_no,bom_name),
                                'name':bom_name,
                                'product_qty':quantity,
                                'sequence':int(float(sequence)),
                                'routing_id':routing_id})
            else:
                parsed_row.update({'product_id':product.id,
                                 'product_uom':product.uom_id.id,
                                #'name':'[%s]%s'%(level_no,bom_name),
                                'name':bom_name,
                                'product_qty':quantity,
                                'sequence':int(float(sequence)),
                                'routing_id':routing_id})
                #=========check and set the direct_bom_find============
                if direct_bom_find_idx >= 0:
                    flag = row_data[direct_bom_find_idx]
                    if not flag:
                        flag = ''
                    flag = flag.lower()
                    if flag in ('y','1','yes'):
                        parsed_row.update({'direct_bom_find':True})
                #=========check and set the no_consume============
                if no_consume_idx >= 0:
                    flag = row_data[no_consume_idx]
                    if not flag:
                        flag = ''
                    flag = flag.lower()
                    if flag in ('y','1','yes'):
                        parsed_row.update({'no_consume':True})                        

            parsed_rows.update({level_no:parsed_row})
        #return data
        return parsed_rows
 

class mrp_bom(osv.osv):
    _inherit = 'mrp.bom'  
    def create(self, cr, uid, vals, context=None):
        if 'create_from_common' in vals and 'common_bom_id' in vals:
            if context is None:
                context = {}
            ctx_clone = context.copy()
            ctx_clone.update({'add_common_bom':True})
            bom_obj = self.pool.get('mrp.bom')
            #clone the data
            clone_bom_id = bom_obj.copy(cr, uid, vals['common_bom_id'], context=ctx_clone)        
            bom_obj.write(cr, uid, [clone_bom_id], vals, context=ctx_clone)            
            return clone_bom_id
        else:
            #if importing need to find direct bom and no bom lines, then system will search the existing bom, and set the direct_bom_id
            if vals.get('direct_bom_find',False) and not vals.get('bom_lines'):
                direct_bom_id = self._bom_find(cr, uid, vals['product_id'], None, properties=None)
                if direct_bom_id:
                    vals.update({'direct_bom_id':direct_bom_id})
            return super(mrp_bom,self).create(cr, uid, vals, context)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
