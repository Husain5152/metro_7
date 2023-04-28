# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (c) 2004-2012 OpenERP S.A. <http://openerp.com>
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

import base64
import cStringIO

from openerp.osv import fields,osv
from openerp.tools.translate import _
import xlrd
from xlutils.copy import copy

import os
import logging
_logger = logging.getLogger(__name__)

class product_batch_query(osv.osv_memory):
    _name = "product.batch.query"
    _columns = {
            'filename': fields.char('File Name'),
            'data': fields.binary('File', filters="*.xls", required=True),
            'data_result': fields.binary('Result File', filters="*.xls"),
            'state': fields.selection([('choose', 'choose'),('get', 'get')]),
            'file_template': fields.binary('Template File', readonly=True),
            'file_template_name': fields.char('Template File Name'),
    }
    def _get_template(self, cr, uid, context):
        cur_path = os.path.split(os.path.realpath(__file__))[0]
        path = os.path.join(cur_path,'product_query_template.xlsx')
        data = open(path,'rb').read().encode('base64')
#        data = os.path.getsize(path)
        return data
            
    _defaults = { 
        'state': 'choose',
        'file_template': _get_template,
        'file_template_name': 'product_query_template.xlsx'
    }
    def act_query(self, cr, uid, ids, context=None):
        if context is None:
            context = {}        
        order = self.browse(cr,uid,ids[0],context=context)
        #get the uploaded data
        data = base64.decodestring(order.data)
        wb_rd = xlrd.open_workbook(file_contents=data,on_demand=True)
        sheet_rd = wb_rd.sheets()[0]
        row_cnt = sheet_rd.nrows
        
        #1. check the column list: 'part_no,part_no_external,name,cn_name' must be in the list
        row_data = sheet_rd.row_values(0);
        idx_part_no = 0
        idx_part_no_external = 0
        idx_name = 0
        idx_cn_name = 0
        try:
            # get the data column index
            idx_part_no = row_data.index('part_no')
            idx_part_no_external = row_data.index('part_no_external')
            idx_name = row_data.index('name')
            idx_cn_name = row_data.index('cn_name')
        except Exception:
            raise osv.except_osv(_('Error!'), _('please make sure the "part_no,part_no_external,name,cn_name" columns in the column list.'))

        #2. query and update part_no to excel object
        #use xlutils to convert to xlwt.Workbook to do the excel updating
        wb_wt = copy(wb_rd)
        sheet_wt = wb_wt.get_sheet(0)
        #loop to query products and update to excel sheet        
        def _get_part_no(self, sheet, idx_row, field_idx_names):
            search_domain_equal = []
            search_domain_like = []
            for idx_col, field_name in field_idx_names.items():
                field_val = sheet.cell(idx_row,idx_col).value
                if field_val != '':
                    search_domain_equal.append((field_name,'=',field_val))
                    search_domain_like.append((field_name,'ilike',field_val))
                    if len(search_domain_equal) > 1:
                        search_domain_equal.insert(0, '|')
                    if len(search_domain_like) > 1:
                        search_domain_like.insert(0, '|')

            _logger.debug("query row#%s product domain:\n%s \n%s"%(idx_row, search_domain_equal, search_domain_like))
            prod_obj = self.pool.get('product.product')
            prod_ids = prod_obj.search(cr, uid, search_domain_equal, context=context)
            if len(prod_ids) == 0:
                prod_ids = prod_obj.search(cr, uid, search_domain_like, context=context)
            part_no_str = ''
            prods = prod_obj.read(cr, uid, prod_ids, ['default_code'], context=context)
            for prod in prods:
                part_no_str += prod['default_code'] + ',' 
            if part_no_str != '':
                part_no_str = part_no_str[:len(part_no_str)-1]
            return part_no_str
        for i in range(1,row_cnt):
            fields = {idx_part_no_external:'part_no_external',idx_name:'name',idx_cn_name:'cn_name'}
            part_no = _get_part_no(self, sheet_rd, i, fields)
            if part_no and part_no != '':
                sheet_wt.write(i, idx_part_no, part_no)
                
        #output the file
        buf = cStringIO.StringIO()
        wb_wt.save(buf)
        out = base64.encodestring(buf.getvalue())
        buf.close()
        self.write(cr, uid, ids, {'state': 'get','data_result': out,}, context=context)                    

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.batch.query',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': order.id,
            'views': [(False, 'form')],
            'target': 'new',
        }


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
