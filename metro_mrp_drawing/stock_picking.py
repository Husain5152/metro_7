# -*- encoding: utf-8 -*-

from osv import osv, fields
import netsvc
from tools.translate import _

class stock_partial_picking(osv.osv_memory):
    _name = "stock.partial.picking"
    _inherit = "stock.partial.picking"

    def do_partial(self, cr, uid, ids, context=None):
        if context == None:
            context = {}
        result = super(stock_partial_picking, self).do_partial(cr, uid, ids, context=context)
        #If this picking is from a PO with PR MFG then find the task with DO and update its prepare qty
        #Temporarily disable warehouse checkin
        # partial = self.browse(cr, uid, ids[0], context=context)
        # picking_id = partial.picking_id
        # if picking_id.purchase_id:
        #     purchase_id = picking_id.purchase_id
        #     if purchase_id.req_id:
        #         req_id = purchase_id.req_id
        #         if req_id.drawing_order_id:
        #             product_ids = []
        #             check_in_qty = {}
        #             task_line_obj = self.pool.get('project.task.line')
        #             task_obj = self.pool.get('project.task')
        #             for move in picking_id.move_lines:
        #                 product_ids.append(move.product_id.id)
        #                 if move.product_id.id not in check_in_qty:
        #                     check_in_qty[move.product_id.id] = move.product_qty - move.return_qty
        #                 else:
        #                     check_in_qty[move.product_id.id] += move.product_qty - move.return_qty
        #             order_id = req_id.drawing_order_id
        #             cr.execute("SELECT id from drawing_order_line where order_id = %s and first_step in %s",
        #                   (order_id.id, tuple(['Fc','B'])))
        #             records = cr.dictfetchall()
        #             order_line_ids = []
        #             for r in records:
        #                 order_line_ids.append(r['id'])
        #             #Search all tasks Fc and B with this order id
        #             task_ids = task_obj.search(cr, uid, [
        #                 ('workorder_id','=',order_id.workorder_id.id),
        #                 ('dept_code','in',['Fc','B'])
        #             ])
        #             task_line_ids = task_line_obj.search(cr, uid, [
        #                 '|',
        #                 '&',('dept_code','=','Fc'),('work_steps','like','Fc%'),
        #                 '&',('dept_code','=','B'),('work_steps','like','B%'),
        #                 ('task_id','in',task_ids),
        #                 ('product_id','in',product_ids),
        #             ])
        #             print(task_line_ids)
        #             for task_line in task_line_obj.browse(cr, uid, task_line_ids, context=context):
        #                 if task_line.prepare_qty < task_line.need_qty:
        #                     need_prepare_qty = task_line.need_qty - task_line.prepare_qty
        #                     if check_in_qty[task_line.product_id.id]:
        #                         if need_prepare_qty <= check_in_qty[task_line.product_id.id]:
        #                             task_line_obj.write(cr, uid, [task_line.id],{'prepare_qty': task_line.need_qty})
        #                             check_in_qty[task_line.product_id.id] -= need_prepare_qty
        #                         else:
        #                             task_line_obj.write(cr, uid, [task_line.id], {'prepare_qty': task_line.prepare_qty + check_in_qty[task_line.product_id.id] })
        #                             check_in_qty[task_line.product_id.id] = 0
        return result