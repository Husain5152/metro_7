# -*- coding: utf-8 -*-
import re
from osv import fields, osv
import tools
from tools.translate import _
from openerp.addons.metro_purchase.purchase import deal_args
from openerp.addons.stock.product import product_product as stock_product
import openerp.addons.decimal_precision as dp
from datetime import datetime
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT,DEFAULT_SERVER_DATE_FORMAT
from openerp.tools.config import config
from openerp.addons.metro_mrp_drawing.drawing_order import PART_TYPE_SELECTION
from openerp.addons.metro_mrp_drawing.drawing_order import CHUNK_SIZE
from openerp.addons.metro import utils
import logging

_logger = logging.getLogger(__name__)

class product_product(osv.osv):
    _inherit = "product.product"
    _name = "product.product"
    _columns = {
        'thickness': fields.char('Thicknesss', size=128),
        'width': fields.char('Width',size=128),
        #'material': fields.char('Material', size=128),  Already defined in metro_mfg
        'part_type': fields.selection(PART_TYPE_SELECTION, string='Part Type'),
        'do_lines': fields.one2many('product.do.line','product_id','Drawing PDF Lines'),
        'cnc_code': fields.char('CNC Code', size=128),
    }

    def onchange_part_type(self, cr, uid, ids, part_type, context=None):
        vals = {}
        if part_type in ['PMS','PML']:
            vals.update({'measure_type': 'msp'})
        return {'value': vals}


    def reserved_infor(self, cr, uid, ids, context=None):
        pr_reserved_obj = self.pool.get('pur.req.reserve')
        return pr_reserved_obj.view_reserved_infor_products(cr, uid, ids, context=context)

    def copy(self, cr, uid, id, default=None, context=None):
        #TODO: Keep main image clear reserve list
        if not default:
            default = {}
        product = self.browse(cr, uid, id, context=context)
        if product:
            default.update({
                'image': product.image,
                'do_lines': False,
                'pr_reserved_ids': False,
            })
        return super(product_product, self).copy(cr, uid, id, default, context)
product_product()



class product_do_line(osv.osv):
    _name = 'product.do.line'

    def _move_drawing_file_to_disk(self, cr, uid, ids=None, context=None):
        line_ids = self.search(cr,uid, [('drawing_file2','=',False),
                                        ('drawing_file','!=',False)], context=context)
        for i in xrange(0, len(line_ids), CHUNK_SIZE):
            for line in self.browse(cr, uid, line_ids[i:i + CHUNK_SIZE], context=context):
                self.write(cr, uid, [line.id], {'drawing_file2': line.drawing_file}, context=context)
        return True

    _columns = {
        'date': fields.datetime('Date', readonly=True),
        'product_id': fields.many2one('product.product','Product',readonly=True),
        'user': fields.many2one('res.users','User',readonly=True),
        'drawing_order_id': fields.many2one('drawing.order','Drawing Order'),
        'do_line_id': fields.many2one('drawing.order.line', 'Drawing Order', readonly=True),
        'drawing_file_name': fields.char('Drawing PDF Name', size=128),
        'drawing_file': fields.binary("Drawing PDF"),
        'drawing_file2': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file, string="Drawing PDF",
                                        type="binary", multi="_get_file", ),
        'drawing_download': fields.char('Drawing PDF', size=128, readonly=True),

        'type': fields.selection([('manual','Manual Upload'),
                                  ('auto','From DO')],'Type',readonly=True)
    }
    _defaults = {
        'user': lambda self,cr, uid, c: uid,
        'date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        'type': 'manual',
        'drawing_download': 'drawing_file2',

    }
product_do_line()