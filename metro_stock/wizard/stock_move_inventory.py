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

class stock_move_inventory(osv.osv_memory):
    _name = "stock.move.inventory"
    _description = "Move Inventory"
    _columns = {
        'src_location_id': fields.many2one('stock.location','Source Location',required=True),
        'dest_location_id': fields.many2one('stock.location','Desctination Locaton',required=True ),
        'company_id': fields.many2one('res.company','Company',required=True),
        'inventory_ids': fields.many2many('stock.inventory',string='Inventory to get Quantity'),
    }

    def default_get(self, cr, uid, fields, context=None):
        res = super(stock_move_inventory, self).default_get(cr, uid, fields, context=context)
        active_ids = context.get('active_ids',[])
        active_model = context.get('active_model',False)
        if active_model == 'stock.inventory' and active_ids:
            inventory_obj = self.pool.get('stock.inventory')
            inventory_ids = inventory_obj.browse(cr, uid, active_ids,context=context)
            res.update({'inventory_ids': [(6,0,active_ids)], 'company_id': inventory_ids[0].company_id.id})
        return res

    def move_inventory(self, cr, uid, ids, context=None):

        if context is None:
            context = {}

        inventory_line_obj = self.pool.get('stock.inventory.line')
        wizard = self.browse(cr, uid, ids[0], context=context)
        picking_ids = []
        if wizard.inventory_ids:
            inventory_ids = [inventory.id for inventory in wizard.inventory_ids]
            inventory_line_ids = inventory_line_obj.search(cr, uid, [('inventory_id', 'in', inventory_ids)], context=context)
            if inventory_line_ids:
                picking_obj = self.pool.get('stock.picking')
                move_obj = self.pool.get('stock.move')
                picking_values = {'name': 'From%sTo%s'%(wizard.src_location_id.name,wizard.dest_location_id.name),
                                                          'company_id': wizard.company_id.id}

                picking_lines_values = {}
                for line in inventory_line_obj.browse(cr, uid, inventory_line_ids, context=context):
                    if picking_lines_values.get(line.product_id.id, False):
                        picking_lines_values[line.product_id.id]['product_qty'] += line.product_qty
                    else:

                        result = move_obj.onchange_product_id(cr, uid, [], prod_id=line.product_id.id,
                                                                      loc_id=wizard.src_location_id.id,
                                                                      loc_dest_id=wizard.dest_location_id.id,
                                                                      partner_id=False)
                        picking_lines_values.update({line.product_id.id: result['value']})
                        picking_lines_values[line.product_id.id].update({
                            'product_id': line.product_id.id,
                            'product_qty': line.product_qty,
                            'product_uom': line.product_id.uom_id.id,
                            'type': 'internal',
                            'src_location_id': wizard.src_location_id.id,
                            'dest_location_id': wizard.dest_location_id.id,
                            'company_id': wizard.company_id.id
                        })
                move_lines_values = []
                for product_id, picking_line_value in picking_lines_values.iteritems():
                    move_lines_values.append((0,0,picking_line_value))
                picking_values.update({'move_lines': move_lines_values})
                picking_id = picking_obj.create(cr, uid, picking_values,context=context)
                picking_ids.append(picking_id)

        if picking_ids:
            return {
                'domain': "[('id', 'in', [" + ','.join(map(str, picking_ids)) + "])]",
                'name': _('Internal Move'),
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'stock.picking',
                'type': 'ir.actions.act_window',
                'context': context,
            }
        return True

