# -*- coding: utf-8 -*-
import time
import re
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST
import logging
_logger = logging.getLogger(__name__)

class generate_pr_wizard(osv.osv_memory):
    _name = 'generate.pr.wizard'
    _description = 'Generate PR Wizard'
    _columns = {
        'mfg_o': fields.boolean('MFG-O Type?'),
        'delivery_date': fields.date('Delivery Date', required=True),
        'delete_old_prs': fields.boolean('Delete Old PRs'),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse', required=True),
    }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        res = super(generate_pr_wizard, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        record_model = context and context.get('active_model', False) or False
        mfg_o = context and context.get('mfg_o', False) or False
        delivery_date = context and context.get('delivery_date', False) or False
        if mfg_o:
            res.update({'mfg_o': True})
        #Search for warehouse id
        warehouse_obj = self.pool.get('stock.warehouse')
        if record_model == 'drawing.order':
            drawing_order_obj = self.pool.get('drawing.order')
            order = drawing_order_obj.browse(cr, uid, record_id, context=context)
            if order:
                if order.mo_id:
                    if order.mo_id.delivery_date:
                        res.update({'delivery_date': order.mo_id.delivery_date})
                    if order.mo_id.location_src_id:
                        warehouse_ids = warehouse_obj.search(cr, uid, [('lot_input_id', '=', order.mo_id.location_src_id and
                                                               order.mo_id.location_src_id.id or False)],
                                                    context=context)
                    else:
                        warehouse_ids = warehouse_obj.search(cr, uid, [('company_id','=',order.company_id.id)], context=context)
                    if warehouse_ids:
                        res.update({'warehouse_id': warehouse_ids[0]})

        elif record_model == 'drawing.order.line':
            drawing_order_line_obj = self.pool.get('drawing.order.line')
            drawing_order_line_ids = context.get('drawing_order_line_ids',[])
            if drawing_order_line_ids:
                record_id = drawing_order_line_ids[0]
                order_line = drawing_order_line_obj.browse(cr, uid, record_id, context=context)
                if order_line:
                    order = order_line.order_id
                    if order_line.order_id.mo_id:
                        if order_line.order_id.mo_id.delivery_date:
                            res.update({'delivery_date': order_line.order_id.mo_id.delivery_date})
                        if order.mo_id.location_src_id:
                            warehouse_ids = warehouse_obj.search(cr, uid,
                                                             [('lot_input_id', '=', order.mo_id.location_src_id and
                                                               order.mo_id.location_src_id.id or False)],
                                                             context=context)

                        else:
                            warehouse_ids = warehouse_obj.search(cr, uid, [('company_id', '=', order.company_id.id)],
                                                             context=context)
                        if warehouse_ids:
                            res.update({'warehouse_id': warehouse_ids[0]})
        if delivery_date:
            res.update({'delivery_date': delivery_date})
        return res

    def _get_bom_line(self, cr, uid, order_line):
        #drawing_order_obj = self.pool.get('drawing.order')
        #mo_do_qty = drawing_order_obj.get_big_subassembly_qty(cr, uid, order_line.order_id)
        return {
            'item_no': order_line.item_no,
            'part_name': order_line.name,
            'part_number': order_line.part_number,
            'description': order_line.description,
            'erp_no': order_line.erp_no,
            'standard': order_line.standard,
            'material': order_line.material,
            'thickness': order_line.thickness,
            'work_steps': order_line.work_steps,
            'part_type': order_line.part_type,
            'bom_qty': order_line.bom_qty,
            'quantity': getattr(order_line,
                                    "%s_need_qty" % order_line.last_step, 0),# * mo_do_qty,
            'product_id': order_line.product_id,
        }

    def _create_pr(self, cr, uid, pr_vals):
        pur_req_obj = self.pool.get('pur.req')
        return pur_req_obj.create(cr, uid, pr_vals)

    def _create_pr_line(self, cr, uid, pr_id, bom_line, sequence, delivery_date, order_line_id,
                        check_part_type=True,
                        merge_line=True,
                        mfg_o=False):
        pr_obj = self.pool.get('pur.req')
        pr_line_obj = self.pool.get('pur.req.line')
        po_line_obj = self.pool.get('purchase.order.line')
        product_obj = self.pool.get('product.product')
        result = True
        if (bom_line['part_type'] not in ['ASM','CD']) or (not check_part_type):
            product = bom_line.get('product_id',False)
            #Check if this product already in pr lines
            if mfg_o:
                existing_erp_no_ids = product_obj.search(cr, uid, [
                    '|',('name', '=', bom_line['part_number']),
                    ('name','=',product_obj.check_dimension_in_en_name(bom_line['part_number']))
                ])
                if not existing_erp_no_ids:
                    # new_product_id = product_obj.copy(cr, uid, product.id, {
                    #    'name': bom_line['part_number'],
                    #    'cn_name': False,
                    # })
                    # Create product with uom = PCS
                    new_product_id = product_obj.create(cr, uid, {
                        'name': bom_line['part_number'],
                        'part_type': bom_line['part_type'],
                    })
                else:
                    new_product_id = existing_erp_no_ids[0]
                product = product_obj.browse(cr, uid, new_product_id)
            exist_pr_line_ids = []
            if merge_line:
                if mfg_o and bom_line['part_type'] == 'PMS':
                    exist_pr_line_ids = pr_line_obj.search(cr, uid, [
                        ('req_id', '=', pr_id),
                        ('product_id','=',product.id),
                    ])
                elif bom_line['erp_no']:
                    exist_pr_line_ids = pr_line_obj.search(cr, uid, [
                        ('req_id','=',pr_id),
                        ('erp_no','=',bom_line['erp_no'])
                    ])
            quantity = bom_line['quantity']
            thickness_extra_mm = 6.0
            #Calculate quantity for some special part type
            if bom_line['part_type'] == 'PML':
                quantity = bom_line['quantity'] * (float(bom_line['thickness']) + thickness_extra_mm) / 1000.0
            if bom_line['part_type'] == 'PMS' and not mfg_o:
                sheetsize = 1
                if product:
                    sheetdimensions = re.findall(r'(\d+)\s*\*\s*(\d+)\s*\*\s*(\d+)',product.name)
                    if len(sheetdimensions) > 0:
                        if len(sheetdimensions[0]) == 3:
                            sheetsize = int(sheetdimensions[0][1]) * int(sheetdimensions[0][2]) / 1000000.0
                if bom_line['description']:
                    dimensions = re.findall(r'(\d+)\s*x\s*(\d+)\s*x\s*(\d+)',bom_line['description'])
                    if len(dimensions) > 0:
                        if len(dimensions[0]) == 3:
                            quantity = int(dimensions[0][0]) * int(dimensions[0][1]) * bom_line['quantity']/ (1000000.0 * sheetsize)
                    else:
                        dimensions = re.findall(ur'\u00F8(\d+)',unicode(bom_line['description']),flags=re.UNICODE)
                        if len(dimensions) > 0:
                            quantity = int(dimensions[0]) * int(dimensions[0]) * bom_line['quantity'] / (1000000.0 * sheetsize)
            if exist_pr_line_ids:
                pr_line = pr_line_obj.browse(cr, uid, exist_pr_line_ids[0])
                quantity += pr_line.product_qty
                pr_line_obj.write(cr, uid, [pr_line.id],{
                    'product_qty' : quantity,
                })
                result = False
            else:
                pur_req_line_vals = {
                    'date_required': delivery_date,
                    'req_id': pr_id,
                    'order_line_id': order_line_id,
                    'product_qty': quantity,
                    'sequence': sequence,
                    'erp_no': bom_line['erp_no'],
                    'item_no': bom_line['item_no'],
                    'name': bom_line["description"],
                    'part_type': bom_line['part_type'],
                    'description': bom_line['description'],
                    'part_number': bom_line['part_name'],
                    'material': bom_line["material"],
                    'thickness': bom_line["thickness"],
                    'standard': bom_line["standard"],
                    'quantity_per_unit': bom_line["bom_qty"],
                    'note': '',
                }
                if bom_line['part_type'] == 'PMS':
                    pur_req_line_vals.update({'part_number': '',})
                if product:
                    # qty_available = 0.0
                    # if product.qty_available > product.reserved_qty:
                    #     qty_available = product.qty_available - product.reserved_qty
                    uom = product.uom_po_id or product.uom_id
                    price = pr_obj.get_product_purchase_price(cr, uid, product, bom_line['part_type'])
                    pur_req_line_vals.update({
                        'product_id': product.id,
                        'product_uom_id': uom.id,
                        'uom_categ_id': product.uom_id.category_id.id,
                        # 'inv_qty': qty_available,
                        'price': price,
                    })

                    purchase_order_line_ids = po_line_obj.search(cr, uid,
                                                                             [('product_id', '=', product.id),
                                                                              ('state', 'in',
                                                                               ['confirmed', 'approved',
                                                                                'done'])],
                                                                             order="date_planned desc")
                    if purchase_order_line_ids:
                        purchase_order_line = po_line_obj.browse(cr, uid, purchase_order_line_ids)[
                            0]
                        pur_req_line_vals.update({'supplier_id': purchase_order_line.order_id.partner_id.id})
                    elif len(product.seller_ids) > 0:
                        pur_req_line_vals.update({'supplier_id': product.seller_ids[0].name.id})
                pr_line_obj.create(cr, uid, pur_req_line_vals)
        return result

    def _create_pr_from_do(self, cr, uid, wizard, order, order_lines = [], check_part_type = True, context=None):
        pur_req_obj = self.pool.get('pur.req')
        pur_req_line_obj = self.pool.get('pur.req.line')
        drawing_order_obj = self.pool.get('drawing.order')
        # Split DO into 3 PR
        normal_lines = order_lines
        pms_lines = []
        pml_lines = []
        generated_prs = []
        if not wizard.mfg_o:
            normal_lines= []
            for order_line in order_lines:
                if order_line.part_type == 'PMS':
                    pms_lines.append(order_line)
                elif order_line.part_type == 'PML':
                    pml_lines.append(order_line)
                elif (order_line.part_type not in ['ASM','CD']) or (not check_part_type):
                    normal_lines.append(order_line)
        pr_vals = {
            'warehouse_id': wizard.warehouse_id.id,
            'drawing_order_id': order.id,
            'pr_type': 'mfg',
            'unit': order.mo_id.product_id.id,
            'mo_id': order.mo_id.id,
            'delivery_date': wizard.delivery_date,
            'engineer': order.create_uid.id,
            'bigsubassembly_id': order.product_id.id,
        }
        if wizard.mfg_o:
            pr_vals.update({'pr_type': 'mfg_o',})

        if normal_lines:
            sequence = 1
            normal_pr_id = self._create_pr(cr, uid, pr_vals)
            for order_line in normal_lines:
                bom_line = self._get_bom_line(cr, uid, order_line)
                if wizard.mfg_o:
                    if order_line.part_type == 'PMS':
                        self._create_pr_line(cr, uid, normal_pr_id, bom_line, sequence, wizard.delivery_date, order_line.id,
                                         check_part_type,merge_line=True,mfg_o=True)
                    else:
                        self._create_pr_line(cr, uid, normal_pr_id, bom_line, sequence, wizard.delivery_date, order_line.id,
                                             check_part_type, merge_line=False, mfg_o=True)
                else:
                    self._create_pr_line(cr, uid, normal_pr_id, bom_line, sequence,
                                         wizard.delivery_date, order_line.id, check_part_type)
                sequence += 1
            normal_pr = pur_req_obj.browse(cr, uid, normal_pr_id)
            generated_prs.append(normal_pr)
            if wizard.mfg_o:
                drawing_order_obj.write(cr, uid, [order.id], {'req_o_id': normal_pr_id})
            else:
                drawing_order_obj.write(cr, uid, [order.id], {'req_id': normal_pr_id})
            for line in normal_pr.line_ids:
                if line.part_type == 'PMS':
                    quantity = int(round(line.product_qty * 100)) / 100.0
                    pur_req_line_obj.write(cr, uid, [line.id], {'product_qty': quantity,
                                                                })
            msg = _('Purchase Requisition %s is created' % normal_pr.name)
            drawing_order_obj.message_post(cr, uid, [order.id], body=msg, context=context)
        if pms_lines:
            sequence = 1
            pr_vals.update({'pr_type': 'mfg_pms'})
            pms_pr_id = self._create_pr(cr, uid, pr_vals)
            for order_line in pms_lines:
                bom_line = self._get_bom_line(cr, uid, order_line)
                self._create_pr_line(cr, uid, pms_pr_id, bom_line, sequence,
                                         wizard.delivery_date, order_line.id, check_part_type)
                sequence += 1
            pms_pr = pur_req_obj.browse(cr, uid, pms_pr_id)
            msg = _('Purchase Requisition %s-PMS is created ' % pms_pr.name)
            drawing_order_obj.message_post(cr, uid, [order.id], body=msg, context=context)
            generated_prs.append(pms_pr)
            drawing_order_obj.write(cr, uid, [order.id], {'req_id_pms': pms_pr_id,
                                                          }, context=context)
            for line in pms_pr.line_ids:
                quantity = int(round(line.product_qty * 100)) / 100.0
                pur_req_line_obj.write(cr, uid, [line.id], {'product_qty': quantity,
                                                                })

        if pml_lines:
            sequence = 1
            pr_vals.update({'pr_type': 'mfg_pml'})
            pml_pr_id = self._create_pr(cr, uid, pr_vals)
            for order_line in pml_lines:
                bom_line = self._get_bom_line(cr, uid, order_line)
                self._create_pr_line(cr, uid, pml_pr_id, bom_line, sequence,
                                         wizard.delivery_date, order_line.id, check_part_type)
                sequence += 1
            pml_pr = pur_req_obj.browse(cr, uid, pml_pr_id)
            msg = _('Purchase Requisition %s-PML is created' % pml_pr.name)
            drawing_order_obj.message_post(cr, uid, [order.id], body=msg, context=context)
            generated_prs.append(pml_pr)
            drawing_order_obj.write(cr, uid, [order.id], {'req_id_pml': pml_pr_id,
                                                          }, context=context)


        return generated_prs

    def do_generate(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids, context)[0]
        drawing_order_ids = context.get('drawing_order_ids', False)
        drawing_order_line_ids = context.get('drawing_order_line_ids', False)
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        pur_req_obj = self.pool.get('pur.req')
        pur_req_line_obj = self.pool.get('pur.req.line')
        pr_names = []
        do_line_not_generate_mfg_o = []
        if drawing_order_ids:
            for order in drawing_order_obj.browse(cr, uid, drawing_order_ids):
                search_domain = [('drawing_order_id', '=', order.id)]
                if wizard.mfg_o:
                    search_domain.append(('pr_type','=','mfg_o'))
                else:
                    search_domain.append(('pr_type', '!=', 'mfg_o'))
                if wizard.delete_old_prs:
                    search_domain.append(('state', 'not in', ['draft','rejected','cancel']))
                pur_req_ids = pur_req_obj.search(cr, uid, search_domain, context=context)
                if pur_req_ids:
                    if wizard.delete_old_prs:
                        raise osv.except_osv(_("Error!"),
                                             _('A Purchase Requisition (%s) of this drawing order can not be deleted!') %
                                             ','.join(req.name for req in pur_req_obj.browse(cr, uid, pur_req_ids)))
                    else:
                        raise osv.except_osv(_("Error!"),
                                                 _('A Purchase Requisition (%s) of this drawing order is already exist!')%
                                                 ','.join(req.name for req in pur_req_obj.browse(cr, uid, pur_req_ids)))
                if wizard.delete_old_prs:
                    search_domain = [('drawing_order_id', '=', order.id),
                                     ('state','in',['draft','rejected','cancel'])]
                    if wizard.mfg_o:
                        search_domain.append(('pr_type', '=', 'mfg_o'))
                    pur_req_ids = pur_req_obj.search(cr, uid, search_domain, context=context)
                    pur_req_obj.unlink(cr, uid, pur_req_ids, context=context)
                order_lines = order.order_lines
                if wizard.mfg_o:
                    order_lines = []
                    for order_line in order.order_lines:
                        if order_line.part_type == 'PMS':
                            exist_req_line_ids = pur_req_line_obj.search(cr, uid, [
                                #('order_line_id', '=', order_line.id),
                                ('part_number','=',order_line.part_number),
                                ('req_id','in',pur_req_ids)
                                #('state', 'not in', ['draft', 'rejected', 'cancel'])
                            ], context=context)
                            if exist_req_line_ids:
                                do_line_not_generate_mfg_o.append(order_line.part_number)
                            else:
                                order_lines.append(order_line)
                    if not order_lines:
                        raise osv.except_osv(_("Warning!"),
                                             _('All PMS parts has been generated. Nothing will be created'))
                prs = self._create_pr_from_do(cr, uid, wizard, order, order_lines, context=context)
                for pr in prs:
                    pr_names.append(pr.name)
        elif drawing_order_line_ids:
            order_groups = {}
            for order_line in drawing_order_line_obj.browse(cr, uid, drawing_order_line_ids, context=context):
                # Check if this order line has been generated in PR
                if wizard.mfg_o:
                    if order_line.part_type == 'PMS':
                        pur_req_ids = pur_req_obj.search(cr, uid, [('pr_type','=','mfg_o'),
                                                                   ('state', 'not in', ['draft', 'rejected', 'cancel']),
                                                                   ('drawing_order_id', '=', order_line.order_id.id),
                                                                   ], context=context)
                        exist_req_line_ids = pur_req_line_obj.search(cr, uid, [
                            #('order_line_id','=',order_line.id),
                            ('part_number', '=', order_line.part_number),
                            ('req_id', 'in', pur_req_ids),
                        ], context=context)
                        if exist_req_line_ids:
                            do_line_not_generate_mfg_o.append(order_line.part_number)
                            continue
                if order_line.order_id.id not in order_groups:
                    order_groups[order_line.order_id.id] = {
                        'order': order_line.order_id,
                        'lines': [order_line]
                    }
                else:
                    order_groups[order_line.order_id.id]['lines'].append(order_line)
            for order_id in order_groups.keys():
                order = order_groups[order_id]['order']
                order_lines = order_groups[order_id]['lines']
                if wizard.mfg_o and not order_lines:
                    raise osv.except_osv(_("Warning!"),
                                         _('All PMS parts has been generated. Nothing will be created'))
                prs = self._create_pr_from_do(cr, uid, wizard, order, order_lines, check_part_type=False, context=context)
                for pr in prs:
                    pr_names.append(pr.name)
        if pr_names:
            message = _("Purchase Requisition(%s) has been created!") % ",".join(pr_names)
            if do_line_not_generate_mfg_o:
                message += _('\n.Some parts (%s) already in PRs') % ",".join(do_line_not_generate_mfg_o)
            return self.pool.get('warning').info(cr, uid, title='Information', message=message)
        return True

generate_pr_wizard()
