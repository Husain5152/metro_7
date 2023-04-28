# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.pur_req import PR_AVAILABLE_QTY_RULE

class cleanup_product_uom_wizard(osv.osv_memory):
    _name = 'cleanup.product.uom.wizard'
    _description = 'Cleanup Product UOM Wizard'
    _columns = {
        'rename_baseunit_uom': fields.boolean('Rename Base Unit UOM?',help='This will try to rename Base Unit to Sheets or Meters by using the product part type'),
        'categ_id': fields.many2one('product.uom.categ','UOM Category'),
        'reference_uom_id': fields.many2one('product.uom', 'Reference UOM', help='Reference UOM used to change all old uom of products into this'),
        'uom_ids': fields.many2many('product.uom',string='Keep UOMs', help='UOMs to keep, other UOM in this category will be cleaned'),
    }

    def onchange_categ(self, cr, uid, ids, categ_id, context=None):
        res = {'value': {'uom_ids': [],'reference_uom_id': False}}
        return res

    def update_uom(self, cr, uid, uom_ids, categ_id, name, cn_name, code, context=None):
        if not type(uom_ids) is list:
            uom_ids = [uom_ids]
        uom_obj = self.pool.get('product.uom')
        existing_uom_ids = uom_obj.search(cr, uid, [('id', 'not in', uom_ids),
                                                    ('category_id','=', categ_id),
                                                    ('name', '=', name)], context=context)
        if existing_uom_ids:
            # Rename to legacy and inactive it
            uom_obj.write(cr, uid, existing_uom_ids, {'name': '[legacy]%s'%name,
                                                      'active': False}, context=context)
        uom_obj.write(cr, uid, uom_ids, {'name': name,
                                        'cn_name': cn_name,
                                        'code': code}, context=context)

    def do_clean(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wizard = self.browse(cr, uid, ids, context)[0]
        product_ids = []
        uom_obj = self.pool.get('product.uom')
        product_obj = self.pool.get('product.product')
        uom_categ_obj = self.pool.get('product.uom.categ')
        if wizard.categ_id and wizard.uom_ids and wizard.reference_uom_id and \
                        wizard.reference_uom_id.category_id.id == wizard.categ_id.id:
            # Check if keep UOMs has at least 1 reference UOM
            categ_uoms = [wizard.reference_uom_id]
            categ_uom_ids = [wizard.reference_uom_id.id]
            for uom in wizard.uom_ids:
                if uom.id != wizard.reference_uom_id.id and uom.category_id.id == wizard.categ_id.id:
                    categ_uom_ids.append(uom.id)
                    categ_uoms.append(uom)

            #First: Switch all product of other uom

            inactive_uom_ids = uom_obj.search(cr, uid, [('id', 'not in', categ_uom_ids),
                                                        ('category_id', '=', wizard.categ_id.id)], context=context)
            product_ids = product_obj.search(cr, uid, ['|','|',('uom_id','in',inactive_uom_ids),
                                                       ('uom_po_id','in',inactive_uom_ids),
                                                       ('uos_id','in',inactive_uom_ids)],context=context)
            if product_ids:
                product_obj.write(cr, uid, product_ids, {'uom_id': wizard.reference_uom_id.id,
                                                         'uos_id': wizard.reference_uom_id.id,
                                                         'uom_po_id': wizard.reference_uom_id.id}, context=context)
            #Second: Inactive all other UOMs in the category
            uom_obj.write(cr, uid, inactive_uom_ids, {'active': False}, context=context)

        uom_count = 0
        if wizard.rename_baseunit_uom:
            categ_ids = uom_categ_obj.search(cr, uid, [('name','like','MSP_')], context=context)

            for uom_categ in uom_categ_obj.browse(cr, uid, categ_ids, context=context):
                uom_product_name = uom_categ.name.replace('MSP_','')
                uom_product_ids = product_obj.search(cr, uid, [('default_code', '=', uom_product_name)], context=context)
                if uom_product_ids:
                    product = product_obj.browse(cr, uid, uom_product_ids[0], context=context)
                    if product.measure_type == 'msp':
                        tonuom = ('Ton(s)', '吨', 'T', )
                        baseuom = False
                        part_type = product.part_type
                        if product.part_type not in ['PMS', 'PML']:
                            # Trying to guess and update product part type
                            name = product.name.lower()
                            if name.find('plate') != -1:
                                dimensions = re.findall(r'(\d+)\s*[x|\*]\s*(\d+)\s*[x|\*]\s*(\d+)', name)
                                if len(dimensions) > 0:
                                    if len(dimensions[0]) == 3:
                                        part_type = 'PMS'
                            elif re.match(r'.*square\s+pipe.*', name) or \
                                re.match(ur'.*pipe\s+\u00F8.*', unicode(name), flags=re.UNICODE):
                                part_type = 'PML'
                            elif name.find('square') != -1:
                                dimensions = re.findall(r'(\d+)\s*[x|\*]\s*(\d+)\s*[x|\*]\s*(\d+)', name)
                                if len(dimensions) > 0:
                                    if len(dimensions[0]) == 3:
                                        part_type = 'PML'
                            elif name.find('round') != -1:
                                dimensions = re.findall(r'(\d+)\s*[x|\*]\s*(\d+)', name)
                                if len(dimensions) > 0:
                                    if len(dimensions[0]) == 2:
                                        part_type = 'PML'
                            elif name.find('angle') != -1:
                                dimensions = re.findall(r'(\d+)\s*[x|\*]\s*(\d+)\s*[x|\*]\s*(\d+)', name)
                                if len(dimensions) > 0:
                                    if len(dimensions[0]) == 3:
                                        part_type = 'PML'
                        if part_type == 'PML':
                            baseuom = ('Meter(s)', '米', 'M', )
                        elif part_type == 'PMS':
                            baseuom = ('Sheet(s)', '张', 'SH')

                        if baseuom:
                            baseunit_id = uom_obj.search(cr, uid, [('category_id', '=', uom_categ.id),
                                                                ('name','=','BaseUnit')], context=context)
                            if baseunit_id:
                                self.update_uom(cr, uid, baseunit_id, uom_categ.id, baseuom[0],
                                                                       baseuom[1],
                                                                       baseuom[2], context=context)
                                uom_count += 1
                            else:
                                baseunit_id = uom_obj.search(cr, uid, [('category_id', '=', uom_categ.id),
                                                                       ('name', 'in', ['M', 'm','Meter', '米'])], context=context)
                                if baseunit_id:
                                    self.update_uom(cr, uid, baseunit_id, uom_categ.id, 'Meter(s)',
                                                                           '米',
                                                                           'M', context=context)
                                    uom_count += 1

                            ton_id = uom_obj.search(cr, uid, [('category_id', '=', uom_categ.id),
                                                              ('name','in',['Ton','Tons', '吨'])], context=context)
                            if ton_id:
                                self.update_uom(cr, uid, ton_id, uom_categ.id, tonuom[0],
                                                                       tonuom[1],
                                                                       tonuom[2], context=context)
                                uom_count += 1
        message = _("%s products and %s uoms have been updated.") % (len(product_ids), uom_count)
        return  self.pool.get('warning').info(cr, uid, title='Information', message=message)




