# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
import base64
from openerp import SUPERUSER_ID
import xlrd
import xlwt
from xlrd import XLRDError
import StringIO

class cleanup_import_product_uom_wizard(osv.osv_memory):
    _name = 'cleanup.import.product.uom.wizard'
    _description = 'Cleanup Import Product UOM Wizard'
    _columns = {
        'import_file': fields.binary(string="Import File"),
    }

    def do_import(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wizard = self.browse(cr, uid, ids, context)[0]
        if wizard.import_file:
            uom_obj = self.pool.get('product.uom')
            uom_categ_obj = self.pool.get('product.uom.categ')
            product_obj = self.pool.get('product.product')
            count = 0
            # Read the bom file and add parts
            inputStr = StringIO.StringIO()
            inputStr.write(wizard.import_file.decode('base64'))
            workbook = xlrd.open_workbook(file_contents=inputStr.getvalue())
            worksheet = workbook.sheet_by_index(0)
            # Check if exist column 5
            if worksheet.cell(0, 5).value != _('UOM Chinese Name') or worksheet.cell(0, 0).value != _('ERP #'):
                raise osv.except_osv(_('Error!'),
                                     _(
                                         'Please make sure ERP #(%s) is 1st column and UOM Chinese Name(%s) is 6th in the xls.')%(worksheet.cell(0, 5).value,worksheet.cell(0, 0).value))

            row = 1
            context2 = context.copy().update({'not_check_category_uom': True})
            while row < worksheet.nrows:
                erp_no = worksheet.cell(row, 0).value
                uom_cn_name = worksheet.cell(row, 5).value
                if erp_no and uom_cn_name:
                    uom_cn_name = uom_cn_name.strip()
                    erp_no = erp_no.strip()
                    product_ids = product_obj.search(cr, uid, [('default_code','=', erp_no)], context=context)
                    if product_ids:
                        for product in product_obj.browse(cr, uid, product_ids, context=context):
                            uom_ids = uom_obj.search(cr, uid, [('id','!=',product.uom_id.id),
                                                               ('cn_name','=', uom_cn_name),
                                                               ('category_id','=',product.uom_id.category_id.id),
                                                               ('active','=',True)], context=context)
                            if uom_ids:
                                uom_vals = {'uom_id': uom_ids[0]}
                                if product.uom_id.id == product.uom_po_id.id or product.measure_type == 'single':
                                    uom_vals.update({'uom_po_id': uom_ids[0]})
                                product_obj.write(cr, uid, [product.id], uom_vals, context=context)
                                count += 1
                            else:
                                if product.measure_type == 'single':
                                    normal_category_ids = uom_categ_obj.search(cr, uid, [('name','not like','MSP_')], context=context)
                                    uom_ids = uom_obj.search(cr, uid, [('cn_name','=',uom_cn_name),
                                                                       ('category_id','in', normal_category_ids),
                                                                       ('active','=',True)], context=context)
                                    if uom_ids:
                                        uom = uom_obj.browse(cr, uid, uom_ids[0], context=context)
                                        product_obj.write(cr, uid, [product.id], {'uom_id': uom_ids[0],
                                                                                  'uom_po_id': uom_ids[0],
                                                                                  'uom_categ_id': uom.category_id.id,
                                                                                  }, context=context2)
                                        count += 1
                row += 1

        message = _("%s products have been updated.") % count
        return  self.pool.get('warning').info(cr, uid, title='Information', message=message)




