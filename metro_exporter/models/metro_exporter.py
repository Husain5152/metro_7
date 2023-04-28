# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
import xlwt
import tempfile
import base64
import os
import json


class metro_exporter(osv.osv):
    _name = 'metro.exporter'
    _description = 'Metro Exporter'
    _columns = {
        'name': fields.char('Name', default='Export ...'),
        'export_type': fields.selection([('customer', 'Customers'),
                                         ('supplier', 'Suppliers'),
                                         ('product', 'Products')],
                                        string='Select data to export?', required=True),
        'result_file': fields.binary('Result File'),
        'result_file_name': fields.char('File Name')
    }
    _defaults = {
        'name': 'Export ..',
    }

    def action_export(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        exporters = self.browse(cr, uid, ids, context)
        for exporter in exporters:
            partner_obj = self.pool.get('res.partner')
            temp_xls_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xls')
            temp_xls_file_name = temp_xls_file.name
            temp_xls_file.close()
            if exporter.export_type == 'customer' or exporter.export_type == 'supplier':
                if exporter.export_type == 'customer':
                    partner_ids = partner_obj.search(cr, uid, [('customer','=', True)])
                    result_file_name = 'Customers.xls'
                else:
                    partner_ids = partner_obj.search(cr, uid, [('supplier', '=', True)])
                    result_file_name = 'Suppliers.xls'
                workbook = xlwt.Workbook()
                columns = ['ID', 'Parent ID', 'Type', 'Name', 'Street', 'Street2', 'City', 'State', 'Zip',
                           'Country', 'Website', 'Phone', 'Mobile', 'Fax', 'Email', 'Link in ERP']
                sheet = workbook.add_sheet("Customers")
                row = 0
                for column in range(len(columns)):
                    sheet.write(row, column, columns[column])
                row += 1
                customer_link = 'http://wrecker.metro.industries/#id=%s&view_type=form&model=res.partner&menu_id=79&action=62'
                supplier_link = 'http://wrecker.metro.industries/#id=%s&view_type=form&model=res.partner&menu_id=303&action=64'
                partners = partner_obj.browse(cr, uid, partner_ids, context)
                for partner in partners:
                    # Only export partners with some information
                    if partner.street or partner.city or partner.state_id or partner.zip or partner.country_id or \
                        partner.website or partner.phone or partner.email or partner.fax:
                        if exporter.export_type == 'customer':
                            link = customer_link % partner.id
                        else:
                            link = supplier_link % partner.id
                        column_values = [
                            partner.id,
                            partner.parent_id and partner.parent_id.id or '',
                            partner.is_company and 'Company' or 'Individual',
                            partner.name.strip(),
                            partner.street and partner.street or '',
                            partner.street2 and partner.street2 or '',
                            partner.city and partner.city or '',
                            partner.state_id and partner.state_id.name or '',
                            partner.zip and partner.zip or '',
                            partner.country_id and partner.country_id.name or '',
                            partner.website and partner.website or '',
                            partner.phone and partner.phone or '',
                            partner.mobile and partner.mobile or '',
                            partner.fax and partner.fax or '',
                            partner.email and partner.email or '',
                            link
                        ]
                        for column in range(len(column_values)):
                            sheet.write(row, column, column_values[column])
                        row = row + 1

                workbook.save(temp_xls_file_name)
                customer_file = open(temp_xls_file_name,'rb')
                exporter.write({
                    'result_file': base64.b64encode(customer_file.read()),
                    'result_file_name': result_file_name
                })
                customer_file.close()
                os.unlink(temp_xls_file_name)
            else:
                result_file_name = 'Products.xls'
                product_obj = self.pool.get('product.product')
                product_ids = product_obj.search(cr, uid, [])
                link = 'http://wrecker.metro.industries/#id=%s&view_type=form&model=product.product&menu_id=253&action=1026'
                columns = ['ID', 'Name', 'Chinese Name', 'ERP #', 'Category', 'Cost Price', 'Purchase Price', 'Type', 'Exernal Part #', 'Barcode', 'UOM', 'Purchase UOM',
                           'Can be Sold', 'Can be Purchase', 'ERP Link', 'Images', 'Sellers']
                workbook = xlwt.Workbook()
                sheet = workbook.add_sheet("Products")
                row = 0
                for column in range(len(columns)):
                    sheet.write(row, column, columns[column])
                row += 1
                products = product_obj.browse(cr, uid, product_ids, context)
                for product in products:
                    sellers = []
                    for seller in product.seller_ids:
                        price = 0.0
                        # Search for lowest price in PO
                        po_line_ids = self.pool.get('purchase.order.line').search(cr, uid, [('product_id', '=', product.id),
                                                                                   ('partner_id', '=', seller.name.id),
                                                                                   ('state', 'not in', ['draft',
                                                                                                        'cancel',
                                                                                                        'cancel_except',
                                                                                                        'rejected',
                                                                                                        'changing_rejected'])],
                                                                                  order='price_unit asc')
                        po_lines = self.pool.get('purchase.order.line').browse(cr, uid, po_line_ids)
                        if po_lines:
                            price = po_lines[0].price_unit
                        sellers.append({
                            'id': seller.id,
                            'name': seller.name.id,
                            'sequence': seller.sequence,
                            'product_name': seller.product_name,
                            'product_code': seller.product_code,
                            'product_uom': seller.product_uom.code,
                            'min_qty': seller.min_qty,
                            'price': price,
                            'delay': seller.delay,
                        })
                    column_values = [
                        product.id,
                        product.name,
                        product.cn_name and product.cn_name or '',
                        product.default_code,
                        product.categ_id and product.categ_id.name or '',
                        product.standard_price,
                        product.uom_po_price,
                        product.type,
                        product.part_no_external and product.part_no_external or '',
                        product.ean13 and product.ean13 or '',
                        product.uom_id.code and product.uom_id.code or product.uom_id.name,
                        product.uom_po_id.code and product.uom_po_id.code or product.uom_po_id.name,
                        product.sale_ok,
                        product.purchase_ok,
                        link % product.id,
                        product.multi_images,
                        json.dumps(sellers)
                    ]
                    for column in range(len(column_values)):
                        sheet.write(row, column, column_values[column])
                    row = row + 1
                workbook.save(temp_xls_file_name)
                customer_file = open(temp_xls_file_name, 'rb')
                exporter.write({
                    'result_file': base64.b64encode(customer_file.read()),
                    'result_file_name': result_file_name
                })
                customer_file.close()
                os.unlink(temp_xls_file_name)

