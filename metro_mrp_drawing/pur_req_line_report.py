# -*- coding: utf-8 -*-

from openerp.osv import fields,osv
from openerp import tools
from openerp.addons.metro_mrp_drawing.drawing_order import PART_TYPE_SELECTION
from openerp.addons.metro_purchase.pur_req import PR_STATES_SELECTION
import openerp.addons.decimal_precision as dp
from openerp.tools import float_compare

class pur_req_line_report(osv.osv):
    _name = 'pur.req.line.report'
    _description = "Purchase Requisition Line Report"
    _order = 'erp_no asc'
    _auto = False
    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False):
        res = super(pur_req_line_report, self).read_group(cr, uid, domain, fields, groupby, offset=offset, limit=limit, context=context, orderby=orderby)
        for line in res:
            if '__domain' in line:
                lines = self.search(cr, uid, line['__domain'], context=context)
                grand_qty_value = 0.0
                available_qty = 0.0
                for line2 in self.browse(cr, uid, lines, context=context):
                    grand_qty_value += line2.product_grand_qty_remain
                    available_qty += line2.product_available_qty
                line['product_grand_qty_remain'] = grand_qty_value
                line['product_available_qty'] = available_qty
        return res

    def _calculate_fields(self, cr, uid, ids, field_names=None, arg=False, context=None):
        """ Finds the requisition related PO info.
        @return: Dictionary of values
        """
        if not field_names:
            field_names = []
        if context is None:
            context = {}
        res = {}
        for id in ids:
            res[id] = {}.fromkeys(field_names, 0.0)

        pur_req_obj = self.pool.get('pur.req.line')
        for line in self.browse(cr, uid, ids, context=context):
            line_ids = pur_req_obj.search(cr, uid, [('product_id','=', line.product_id.id),
                                             ('order_state', 'in', ['approved', 'in_purchase'])],
                                   context=context)
            product_grand_qty_remain = 0.0
            mfg_ids = []
            prs = []
            unit = []
            for req_line in pur_req_obj.browse(cr, uid, line_ids, context=context):
                mfg_ids.extend([mfg_id.name for mfg_id in req_line.req_id.sale_product_ids])
                prs.append(req_line.req_id.name)
                if req_line.req_id.unit:
                    unit.append(req_line.req_id.unit.name)
                product_grand_qty_remain += req_line.product_qty_remain
            mfg_ids_set = set(mfg_ids)
            prs_set = set(prs)
            unit_set = set(unit)
            res[line.id]["product_grand_qty_remain"] = product_grand_qty_remain
            res[line.id]["unit_id"] = ' '.join(mfg_ids_set)
            res[line.id]["unit"] = ' '.join(unit_set)
            res[line.id]["source"] = ' '.join(prs_set)

            product_available_qty = line.product_onhand_qty - line.product_current_reserved_qty
            if product_available_qty < 0.0:
                product_available_qty = 0.0

            res[line.id]["product_available_qty"] = product_available_qty
        return res

    _columns = {
        'erp_no': fields.char('ERP #', size=50, readonly=True),
        'product_id': fields.many2one('product.product', 'Product', readonly=True),
        'product_uom_id': fields.many2one('product.uom', 'Product UOM'),
        'supplier_id': fields.many2one('res.partner', 'Partner', readonly=True),
        'part_number': fields.char('Part Number', size=128, readonly=True),
        'description': fields.char('Description', size=128, readonly=True),
        'part_type': fields.selection(PART_TYPE_SELECTION, string='Part Type', readonly=True),
        "material": fields.char("Material", size=128, readonly=True),
        "thickness": fields.char("Thickness/Length", size=128, readonly=True),
        "standard": fields.char("Standard", size=128, readonly=True),
        'product_onhand_qty': fields.related('product_id','qty_available', type='float', digits_compute=dp.get_precision('Product Unit of Measure'),
                                             string='On hand Qty', help="Stock on hand quantity", readonly=True),
        'product_qty_req': fields.related('product_id', 'product_qty_req', type='float',
                                          digits_compute=dp.get_precision('Product Unit of Measure'),
                                          string='Requesting Qty',
                                          help="All PR need quantity that not generated PO yet", readonly=True),
        'product_grand_qty_remain': fields.function(_calculate_fields, multi='pur_line_info', string='Grand Qty Remaining',
                                                    type='float',
                                                    digits_compute=dp.get_precision('Product Unit of Measure'),
                                                    readonly=True),
        'product_available_qty': fields.function(_calculate_fields, multi='pur_line_info', string='Available Qty', type='float',
                                                 digits_compute=dp.get_precision('Product Unit of Measure'),
                                                 readonly=True),
        'source': fields.function(_calculate_fields, multi='pur_line_info', string='Source PR', type='char',
                                                 readonly=True),
        'unit_id': fields.function(_calculate_fields, multi='pur_line_info', string='Unit ID', type='char',
                                  readonly=True),
        'unit': fields.function(_calculate_fields, multi='pur_line_info', string='Unit', type='char',
                                  readonly=True),
        "product_current_reserved_qty": fields.related('product_id','reserved_qty', type='float', string='Reserved Qty'),
        "product_reserved_qty": fields.float('Reserved Qty', help='The reserved quantity of this PR line'),
        "price": fields.float("Price"),
        'amount_total': fields.float('Amount'),
    }

    def init(self, cr):
        tools.sql.drop_view_if_exists(cr, 'pur_req_line_report')
        cr.execute("""
                    create or replace view pur_req_line_report as (
                    SELECT min(l.id) as id, l.erp_no, l.product_id, l.product_uom_id, l.supplier_id, l.part_number,l.description, l.part_type,
                           l.material, l.thickness, l.standard, COALESCE (SUM(l.product_reserved_qty), 0) as product_reserved_qty,
                           COALESCE (SUM(l.amount_total)/(CASE SUM(l.product_qty) WHEN 0 THEN 1 ELSE SUM(l.product_qty) END), 0.0) as price,
                           COALESCE (SUM(l.amount_total)) as amount_total
                    FROM pur_req_line l
                    LEFT JOIN pur_req r ON l.req_id = r.id
                    WHERE r.state not in ('done','cancel','draft')
                    GROUP BY l.erp_no, l.product_id, l.product_uom_id, l.supplier_id, l.part_number,l.description, l.part_type,
                           l.material, l.thickness, l.standard
                    )
                    """)
