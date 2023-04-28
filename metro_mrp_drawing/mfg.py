# -*- encoding: utf-8 -*-
'''
Created on 24-11-2015
 
@author: Khai Hoang
'''
from openerp.osv import osv, fields
from openerp.tools.translate import _
from lxml import etree
from openerp.addons.metro import utils
from datetime import datetime
from openerp import tools
from openerp import tools, SUPERUSER_ID
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.addons.metro_mrp_drawing.drawing_order import WORK_STEP_LIST, CHUNK_SIZE
from openerp.addons.base_status.base_stage import base_stage
from openerp import netsvc
import time
import logging
_logger = logging.getLogger(__name__)

STAGE_SEQUENCES = {_('Missed Deadline'): 0,
                   _('In Progress'): 1000,
                   _('Pending'): 2000,
                   _('On Working'): 3000,
                   _('Waiting On Parts'): 4000,
                   _('Done'): 5000,
                   _('Cancelled'): 10000,
                   }

def ceiling(f, r):
    if not r:
        return f
    return tools.float_round(f, precision_rounding=r, rounding_method='UP')
class project_task_modifyhistory(osv.osv):
    _name = "project.task.modifyhistory"
    _description = "Project Task Modify History"
    _columns = {
        'date': fields.datetime('Modified Date',readonly=True),
        'task_id': fields.many2one('project.task','Project Task',readonly=True),
        'user_id': fields.many2one('res.users','User',readonly=True),
        'content': fields.char('Content',readonly=True),
        'vals': fields.char('Update Values',readonly=True,size=256),
    }
    _order = "date desc"
project_task_modifyhistory()
class project_task_completion(osv.osv):
    _name = "project.task.completion"
    _description = "Project Task Completion"
    _rec_name = "dept_id"
    def _get_total_qty(self, cr, uid, ids, name, arg, context=None):
        result = {}
        for completion in self.browse(cr, uid, ids):
            total = 0
            for line in completion.completion_lines:
                total = total + line.done_qty
            result[completion.id] = total
        return result
    _columns = {
        #'name': fields.char('Name',type="char",size=128,readonly=True),
        'task_id': fields.many2one('project.task','Task',ondelete="cascade",required=True,states={'draft': [('readonly', False)]},readonly=True),
        'date': fields.date('Date',required=True,states={'draft': [('readonly', False)]},readonly=True),
        'dept_id': fields.many2one('hr.department','Team',required=True,states={'draft': [('readonly', False)]},readonly=True),
        'big_subassembly_id': fields.many2one('product.product','Big Sub Assembly',required=True,states={'draft': [('readonly', False)]},readonly=True),
        'mo_id': fields.many2one('mrp.production','Manufacturer Order',required=True,states={'draft': [('readonly', False)]},readonly=True),
        'completion_lines': fields.one2many('project.task.completion.line','completion_id',string='Completion Lines',states={'draft': [('readonly', False)]},readonly=True),
        'total_qty': fields.function(_get_total_qty,method=True,type="integer",string='Total Quantity',readonly=True),
        'date_create': fields.datetime('Create Date',readonly=True),
        'user_id': fields.many2one('res.users','Create User',readonly=True),
        'state': fields.selection([('draft','Draft'),
                                   ('confirmed','Confirm'),
                                   ('cancelled','Cancelled')],string='State',readonly=True)
    }
    _sql_constraints = [
        ('task_id_date_uniq', 'unique(task_id,date)', _('You are not allow to create 2 dispatch for a task in one day!')),
    ]
    #def _check_duplicate_completion(self, cr, uid, ids, context=None):
        #for completion in  self.browse(cr, uid, ids):
        #    duplicate_ids = self.search(cr, uid, [
        #        ('task_id','=',completion.task_id.id),
        #        ('date','=',completion.date)
        #    ])
        #    if len(duplicate_ids) >= 2:
        #        return False
        #return True
    #_constraints = [
    #    (_check_duplicate_completion, _('You are not allow to create 2 dispatch for a task in one day!'), ['task_id','date']),
    #    ]

    def unlink(self, cr, uid, ids, context=None):
        confirmed_ids = self.search(cr, uid, [('id','in',ids),
                                             ('state','=','confirmed')])
        if len(confirmed_ids) > 0:
            raise osv.except_osv(_('Error!'), _('Can not delete confirmed task completions !'))
            return False
        return super(project_task_completion,self).unlink(cr, uid, ids, context=context)


    def onchange_mo_dept_big_subassembly(self, cr, uid, ids, mo_id, dept_id, big_subassembly_id, context=None):
        values = {}
        if mo_id and dept_id and big_subassembly_id:
            project_task_obj = self.pool.get('project.task')
            task_ids = project_task_obj.search(cr, uid, [('production_id', '=', mo_id),
                                                         ('dept_id', '=', dept_id),
                                                         ('big_subassembly_id', '=', big_subassembly_id)])
            if len(task_ids) == 1:
                task = project_task_obj.browse(cr, uid, task_ids[0])
                values.update({'task_id': task_ids[0],'name': '%s-%s-%s'%(task.production_id.name,
                                                                      task.dept_id.name,
                                                                      task.big_subassembly_id.name)})
        return {'value': values}
    def onchange_task_id(self, cr, uid, ids, task_id, context=None):
        task_obj = self.pool.get('project.task')
        task_line_obj = self.pool.get('project.task.line')
        task_completion_line_obj = self.pool.get('project.task.completion.line')
        task = task_obj.browse(cr, uid, task_id)
        completion_line_ids = []
        if task:
            old_completion_line_ids = task_completion_line_obj.search(cr, uid, [('completion_id','in',ids)])
            task_completion_line_obj.unlink(cr, uid, old_completion_line_ids)
            task_line_ids  = task_line_obj.search(cr, uid, [('task_id','=',task.id),
                                                            ('need_qty','>',0)],order="sequence asc")
            sequence = 1
            for line in task_line_obj.browse(cr, uid, task_line_ids):
                if line.prepare_qty > 0 and line.done_qty < line.need_qty:
                    vals = {
                        'sequence': sequence,
                        'task_line_id': line.id,
                        'item_no': line.item_no,
                        'part_number': line.part_number,
                        'product_id': line.product_id.id,
                        'task_done_qty': line.done_qty,
                        'task_need_qty': line.need_qty,
                        'task_prepare_qty': line.prepare_qty,
                        'need_qty': line.need_qty - line.done_qty,
                        'prepare_qty': line.prepare_qty - line.done_qty,
                        'done_qty': 0,
                    }
                    #completion_line_id = task_completion_line_obj.create(cr, uid, vals)
                    #completion_line_ids.append(completion_line_id)
                    completion_line_ids.append(vals)
                    sequence = sequence + 1
        return {'value': {'completion_lines': completion_line_ids}}

    def _set_state(self,cr,uid,ids,state,context=None):
        self.write(cr,uid,ids,{'state':state},context=context)

    def update_quantity_to_task(self,cr, uid, ids, context=None):
        task_line_obj = self.pool.get('project.task.line')
        project_task_obj = self.pool.get('project.task')
        updated_task_line_ids = []
        updated_task_ids = []
        for completion in self.browse(cr, uid, ids):
            for line in completion.completion_lines:
                if line.done_qty != 0:
                    new_done_qty = line.done_qty + line.task_done_qty
                    if new_done_qty > line.task_prepare_qty or new_done_qty > line.task_need_qty:
                        raise osv.except_osv(_('Error!'), _('(%s %s)%s : done quantity is not correct !')%(line.item_no, line.part_number,line.product_id.name,))
                        return False
                    task_line_obj.write(cr, uid, [line.task_line_id.id],{
                        'done_qty': new_done_qty,
                    })
                    updated_task_line_ids.append(line.task_line_id.id)
            updated_task_ids.append(completion.task_id.id)
        project_task_obj.move_part_when_task_line_updated(cr, uid, updated_task_ids, updated_task_line_ids)
        return True
    def cancel_quantity_to_task(self, cr, uid, ids, context=None):
        return True
    def action_confirm(self, cr, uid, ids, context=None):
        for completion in self.browse(cr, uid, ids, context=context):
            if completion.task_id.state in ['draft','cancelled','done']:
                raise osv.except_osv(_('Error!'), _('Can not confirm! Task is not in working states!'))
                return False
        #Update done quantity to project task
        result = self.update_quantity_to_task(cr, uid, ids, context=context)
        if not result:
            raise osv.except_osv(_('Error!'), _('Can not confirm task completion!'))
            return False
        self._set_state(cr, uid, ids, 'confirmed',context)
        return True
    def action_cancel(self, cr, uid, ids, context=None):
        result = self.cancel_quantity_to_task(cr, uid, ids, context=context)
        if not result:
            raise osv.except_osv(_('Error!'), _('Can not cancel task completion!'))
            return False
        self._set_state(cr, uid, ids, 'cancelled',context)
        return True

    def action_draft(self, cr, uid, ids, context=None):
        self._set_state(cr, uid, ids, 'draft',context)
        return True

    _defaults = {
        'state': 'draft',
        'date': fields.date.context_today,
        'date_create': lambda *a: datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'user_id': lambda obj, cr, uid, context: uid,
    }
project_task_completion()
class project_task_completion_line(osv.osv):
    _name = "project.task.completion.line"
    _description = "Project Task Completion Line"
    def _get_remain_need_qty(self, cr, uid, ids, name, args, context=None):
        result = {}
        for line in self.browse(cr, uid, ids):
            result[line.id] = 0
            if line.task_line_id:
                result[line.id] = line.task_need_qty - line.task_done_qty
        return result
    def _get_remain_prepare_qty(self, cr, uid, ids, name, args, context=None):
        result = {}
        for line in self.browse(cr, uid, ids):
            result[line.id] = 0
            if line.task_line_id:
                result[line.id] = line.task_prepare_qty - line.task_done_qty
        return result
    _columns = {
        'sequence': fields.integer('Sequence',readonly=True),
        'completion_id': fields.many2one('project.task.completion','Task Compeltion',readonly=True),
        'task_line_id': fields.many2one('project.task.line',readonly=True),
        'part_number': fields.char("Part Number", type="char",size=128,readonly=True),
        'item_no': fields.char('Item No.',type='char',size=50,readonly=True),
        'product_id': fields.many2one('product.product',string='Product',readonly=True),
        'task_done_qty':fields.related('task_line_id','done_qty',type='integer',string='Total Done Quantity',readonly=True),
        'task_need_qty':fields.related('task_line_id','need_qty',type='integer',string='Total Need Quantity',readonly=True),
        'task_prepare_qty':fields.related('task_line_id','prepare_qty',type='integer',string='Total Prepare Quantity',readonly=True),
        'done_qty': fields.integer('Done Quantity'),
        'need_qty': fields.function(_get_remain_need_qty, string='Remain Need Quantity', type="integer",method=True,readonly=True),
        'prepare_qty': fields.function(_get_remain_prepare_qty,string='Remain Prepare Quantity', type="integer",method=True,readonly=True)
    }
    def write(self, cr, uid, ids, vals, context=None):
        if not type(ids) is list:
            ids = [ids]
        if 'done_qty' in vals:
            for line in self.browse(cr, uid, ids):
                if vals['done_qty'] > line.need_qty:
                    raise osv.except_osv(_('Error!'), _('%s : done quantity must <= need quantity!')%(line.product_id.name,))
                    return False
        result = super(project_task_completion_line,self).write(cr, uid, ids, vals, context=context)
        return result
project_task_completion_line()
class project_task_line(osv.osv):
    _name = "project.task.line"
    _description = "Project Task Line"

    def _get_name(self, cr, uid, ids , name, args, context=None):
        result = {}
        for line in self.browse(cr, uid, ids, context=context):
            result.update({line.id : '[%s] %s'%(line.item_no, line.part_number)})
        return result

    _columns = {
                'name': fields.function(_get_name,string='Name',type='char',size=128),
                'sequence': fields.integer('Sequence',readonly=True),
                'order_line_id': fields.many2one('drawing.order.line','Drawing Order Line',readonly=True),
                'drawing_file_name': fields.related('order_line_id','drawing_file_name',string='Drawing PDF Name', type='char', size=128, readonly=True),
                'drawing_file': fields.related('order_line_id','drawing_file', string="Drawing PDF", type="binary",readonly=True),
                'part_type': fields.related('order_line_id','part_type',type='char',size=50,readonly=True),
                'erp_no': fields.related('order_line_id', 'erp_no', type='char', size=50, readonly=True),
                #HoangTK - Drawing Download field is used to display link to download drawing
                #it will fix the overload on Openerp when it will keep read whole the binary if display drawing_file
                'drawing_download': fields.char('Drawing PDF', size=128,readonly=True),
                'item_no': fields.char('Item No.',size=50,readonly=True),
                'task_id': fields.many2one('project.task','Task',ondelete="cascade"),
                'dept_code': fields.related('task_id', 'dept_code', type="char", size=10, readonly=True),
                'product_id': fields.many2one('product.product','Product'),
                #'part_number': fields.related('order_line_id','part_number',string='Part Number',type='char',size=128),
                'part_number': fields.char('Part Number',size=128,readonly=True),
                'description': fields.char('Description', size=128, readonly=True),
                'prepare_qty': fields.integer('Prepare Qty',readonly=True),
                'transfer_qty': fields.integer('Transfer Qty', readonly=True),
                'done_qty': fields.integer('Done Qty'),
                'need_qty': fields.integer('Need Qty',readonly=True),
                #'work_steps': fields.related('order_line_id','work_steps',string='Work Steps',type='char',size=128,store=True,readonly=True),
                'work_steps': fields.char('Work Steps',size=128,readonly=True),
                'next_step': fields.char('Next Step',size=128,readonly=True),

                'state': fields.selection([('created','Created'),
                                            ('on_working','On Working'),
                                            ('done','Done')],string='State',readonly=True),
                }
    def write(self, cr, uid, ids, vals, context=None):
        if not type(ids) is list:
            ids = [ids]
        if 'done_qty' in vals:
            for line in self.browse(cr, uid, ids):
                if vals['done_qty'] > line.need_qty:
                    raise osv.except_osv(_('Error!'), _('%s : done quantity must <= need quantity!')%(line.product_id.name,))
                    return False
        if 'prepare_qty' in vals:
            for line in self.browse(cr, uid, ids):
                if vals['prepare_qty'] < line.done_qty:
                    raise osv.except_osv(_('Error!'), _('%s : prepare quantity must >= done quantity!')%(line.product_id.name, ))
                    return False
        result = super(project_task_line,self).write(cr, uid, ids, vals, context=context)
        for line in self.browse(cr, uid, ids):
            if line.need_qty > 0:
                if line.done_qty == line.need_qty:
                    super(project_task_line,self).write(cr, uid, [line.id], {'state': 'done'}, context=context)
                elif line.task_id.state not in ['draft','cancelled','done']:
                    super(project_task_line,self).write(cr, uid, [line.id], {'state': 'on_working'}, context=context)
                else:
                    super(project_task_line,self).write(cr, uid, [line.id], {'state': ''}, context=context)
        return result
    _defaults = {
        'sequence': 0,
        'drawing_download': 'drawing_file',
                }
    _order = "sequence"
project_task_line()

def rounding(f, r):
    import math
    if not r:
        return f
    return math.ceil(f / r) * r
class mrp_bom(osv.osv):
    _name = 'mrp.bom'
    _inherit = 'mrp.bom'

    def _bom_explode_an_assembly(self, cr, uid, bom, factor, properties=None, addthis=False, level=0, routing_id=False,assembly_id = False):
        """ Finds Products and Work Centers for related BoM for manufacturing order.
        @param bom: BoM of particular product.
        @param factor: Factor of product UoM.
        @param properties: A List of properties Ids.
        @param addthis: If BoM found then True else False.
        @param level: Depth level to find BoM lines starts from 10.
        @return: result: List of dictionaries containing product details.
                 result2: List of dictionaries containing Work Center details.
        """
        routing_obj = self.pool.get('mrp.routing')
        factor = factor / (bom.product_efficiency or 1.0)
        factor = rounding(factor, bom.product_rounding)
        if factor < bom.product_rounding:
            factor = bom.product_rounding
        result = []
        result2 = []
        phantom = False
        if bom.type == 'phantom' and not bom.bom_lines:
            newbom = self._bom_find(cr, uid, bom.product_id.id, bom.product_uom.id, properties)

            if newbom:
                # +++HoangTK, 03/26/2019# check for bom recursive before proceed
                new_bom_point = self.browse(cr, uid, [newbom])[0]
                if self._check_bom_recursive(new_bom_point):
                    raise osv.except_osv(_('Error'), _('Bom can not include itself as a child'))
                res = self._bom_explode(cr, uid, new_bom_point, factor*bom.product_qty, properties, addthis=True, level=level+10)
                result = result + res[0]
                result2 = result2 + res[1]
                phantom = True
            else:
                phantom = False
        if not phantom:
            if addthis and not bom.bom_lines:
                result.append(
                {
                    'name': bom.product_id.name,
                    'product_id': bom.product_id.id,
                    'product_qty': bom.product_qty * factor,
                    'product_uom': bom.product_uom.id,
                    'product_uos_qty': bom.product_uos and bom.product_uos_qty * factor or False,
                    'product_uos': bom.product_uos and bom.product_uos.id or False,
                })
            routing = (routing_id and routing_obj.browse(cr, uid, routing_id)) or bom.routing_id or False
            if routing:
                for wc_use in routing.workcenter_lines:
                    wc = wc_use.workcenter_id
                    d, m = divmod(factor, wc_use.workcenter_id.capacity_per_cycle)
                    mult = (d + (m and 1.0 or 0.0))
                    cycle = mult * wc_use.cycle_nbr
                    result2.append({
                        'name': tools.ustr(wc_use.name) + ' - '  + tools.ustr(bom.product_id.name),
                        'workcenter_id': wc.id,
                        'sequence': level+(wc_use.sequence or 0),
                        'cycle': cycle,
                        'hour': float(wc_use.hour_nbr*mult + ((wc.time_start or 0.0)+(wc.time_stop or 0.0)+cycle*(wc.time_cycle or 0.0)) * (wc.time_efficiency or 1.0)),
                    })
            for bom2 in bom.bom_lines:
                if bom2.product_id.id == assembly_id:
                    # +++HoangTK, 03/26/2019# check for bom recursive before proceed
                    if self._check_bom_recursive(bom2):
                        raise osv.except_osv(_('Error'), _('Bom can not include itself as a child'))
                    res = self._bom_explode(cr, uid, bom2, factor, properties, addthis=True, level=level+10)
                    result = result + res[0]
                    result2 = result2 + res[1]
        return result, result2
mrp_bom()
class mrp_production(osv.osv):
    _inherit = 'mrp.production'

    def _get_not_generate_do_qty(self, cr, uid, ids, name=None, args=None, context=None):
        result = {}
        drawing_order_obj = self.pool.get('drawing.order')
        for mo in self.browse(cr, uid, ids, context=context):
            result[mo.id] = 0
            for order in mo.drawing_order_ids:
                if not order.workorder_id:
                    result[mo.id] += drawing_order_obj.get_big_subassembly_qty(cr, uid, order)
        return result

    _columns = {
        'delivery_date': fields.date('Delivery Date(ETA)', required=True),
        'not_generated_do_qty': fields.function(_get_not_generate_do_qty, string='Not generated Qty',readonly=True,type='integer'),
    }

    def write(self, cr, uid, ids, vals, context=None, update=True, mini=True):
        if not type(ids) is list:
            ids = [ids]
        result = super(mrp_production, self).write(cr, uid, ids, vals, context=context, update=update, mini=mini)
        if vals.get('product_qty', False):
            drawing_order_obj = self.pool.get('drawing.order')
            for mo in self.browse(cr, uid, ids):
                order_ids = [order.id for order in mo.drawing_order_ids]
                drawing_order_obj.update_do_line_quantity(cr, uid, order_ids)
        return result

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if view_type == 'form' and not view_id:
            view_name = 'metro_mrp_production_with_drawing_order_form_view'
            view_obj = self.pool.get('ir.ui.view')
            view_ids = view_obj.search(cr, uid, [('name','=',view_name)])
            if view_ids:
                view = view_obj.browse(cr, uid, view_ids[0])
                department_obj = self.pool.get('hr.department')
                department_ids = department_obj.search(cr, uid, [('code','in',WORK_STEP_LIST)],order = 'sequence asc')
                departments = department_obj.browse(cr, uid, department_ids)
                work_step_fields = ''
                for department in departments:
                    work_step_fields = work_step_fields + \
                                       "<field name='%s_prepare_qty' attrs=\"{'invisible':[('%s_prepare_qty', '==', 0)]}\" readonly='1'/> \
                                       <field name='%s_done_qty' attrs=\"{'invisible':[('%s_done_qty', '==', 0)]}\" readonly='1'/> \
                                       <field name='%s_need_qty' attrs=\"{'invisible':[('%s_need_qty', '==', 0)]}\" readonly='1'/>" % (department.code,department.code,department.code,department.code,department.code,department.code)
                arch_parts = view.arch.split('<!--DYNAMIC WORKSTEPS DO NOT DELETE-->')
                if len(arch_parts) == 3:
                    view_arch = arch_parts[0] + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                                work_step_fields + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                                arch_parts[2]
                    view_obj.write(cr, SUPERUSER_ID, [view_ids[0]],{
                        'arch': view_arch
                    })
        res = super(mrp_production,self).fields_view_get(cr,uid,view_id,view_type,context,toolbar,submenu)
        return res
    def generate_drawing_orders(self, cr, uid, mo_id, big_subassembly_ids):
        drawing_order_obj = self.pool.get('drawing.order')
        product_obj = self.pool.get('product.product')
        mo = self.browse(cr, uid, mo_id)
        if mo and big_subassembly_ids:
            # Remove all drawing orders of this mo
            old_drawing_order_ids = drawing_order_obj.search(cr, uid, [
                ('mo_id', '=', mo.id)
            ])
            drawing_order_obj.unlink(cr, uid, old_drawing_order_ids)
            mfg_ids = []
            for mfg_id in mo.mfg_ids:
                mfg_ids.append("ID" + str(mfg_id.name))
            mfg_name = "_".join(mfg_ids)
            for asm in product_obj.browse(cr, uid, big_subassembly_ids):
                drawing_order_name = asm.name
                if mfg_name:
                    drawing_order_name += "-" + mfg_name
                drawing_order_vals = {'mo_id': mo.id,
                                      'product_id': asm.id,
                                      'name': drawing_order_name,
                                      'main_part_id': mo.product_id.id,
                                      'state': 'draft',
                                      'bom_file_name': False}
                drawing_order_obj.create(cr, uid, drawing_order_vals)
        return True

    def action_drawing_order_generate(self, cr, uid, ids, properties=None, context=None):
        for mo in self.browse(cr, uid, ids, context=context):
            big_subassembly_ids = []
            for bom_line in mo.bom_id.bom_lines:
                big_subassembly_ids.append(bom_line.product_id.id)
            self.generate_drawing_orders(cr, uid, mo.id,big_subassembly_ids)
        return True

    def action_compute_an_assembly(self, cr, uid, ids, properties=None, context=None, assembly_id=False):
        """ Computes bills of material of a product.
        @param properties: List containing dictionaries of properties.
        @return: No. of products.
        """
        if properties is None:
            properties = []
        results = []
        bom_obj = self.pool.get('mrp.bom')
        uom_obj = self.pool.get('product.uom')
        prod_line_obj = self.pool.get('mrp.production.product.line')
        workcenter_line_obj = self.pool.get('mrp.production.workcenter.line')
        for production in self.browse(cr, uid, ids):
            #cr.execute('delete from mrp_production_product_line where production_id=%s', (production.id,))
            #cr.execute('delete from mrp_production_workcenter_line where production_id=%s', (production.id,))
            bom_point = production.bom_id
            bom_id = production.bom_id.id
            if not bom_point:
                bom_id = bom_obj._bom_find(cr, uid, production.product_id.id, production.product_uom.id, properties)
                if bom_id:
                    bom_point = bom_obj.browse(cr, uid, bom_id)
                    routing_id = bom_point.routing_id.id or False
                    self.write(cr, uid, [production.id], {'bom_id': bom_id, 'routing_id': routing_id})

            if not bom_id:
                raise osv.except_osv(_('Error!'), _("Cannot find a bill of material for this product."))
            factor = uom_obj._compute_qty(cr, uid, production.product_uom.id, production.product_qty, bom_point.product_uom.id)
            res = bom_obj._bom_explode_an_assembly(cr, uid, bom_point, factor / bom_point.product_qty, properties, routing_id=production.routing_id.id,assembly_id = assembly_id)
            results = res[0]
            results2 = res[1]
            for line in results:
                line['production_id'] = production.id
                prod_line_obj.create(cr, uid, line)
            for line in results2:
                line['production_id'] = production.id
                if line.get('bom_id', False) and line.get('routing_id', False) and line.get('routing_operation_id',
                                                                                            False):
                    workcenter_line_obj.create(cr, uid, line)
        return len(results)

    def _generate_task_from_drawing_orders(self, cr, uid, drawing_order_ids, context=None):
        workcenter_line_obj = self.pool.get('mrp.production.workcenter.line')
        #production_obj = self.pool.get('mrp.production')
        project_task_obj = self.pool.get('project.task')
        project_task_line_obj = self.pool.get('project.task.line')
        dept_obj = self.pool.get('hr.department')
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        project_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_project', 'project_mfg')[1]
        cnc_p_task_ids = []
        for order in drawing_order_obj.browse(cr, uid, drawing_order_ids):
            if order.state in ['draft', 'rejected', 'cancel']:
                raise osv.except_osv(_('Error!'),
                                     _('Can not generate tasks for draft, cancel or rejected drawing orders!'))
            # Check if work order exists ? if not create it
            product = order.product_id
            mo = order.mo_id
            mfg_ids = [mfg_id.id for mfg_id in order.sale_product_ids]
            wo_line_ids = workcenter_line_obj.search(cr, uid, [
                ('production_id', '=', mo.id),
                ('big_subassembly_id', '=', product.id),
                ('drawing_order_id', '=', order.id)
             ])
            if not wo_line_ids:
                self.action_compute_an_assembly(cr, uid, [mo.id], assembly_id=product.id)
                wo_line_ids = workcenter_line_obj.search(cr, uid, [
                    ('production_id', '=', mo.id),
                    ('big_subassembly_id', '=', product.id),
                    ('drawing_order_id', '=', False)
                ])

            if not wo_line_ids:
                raise osv.except_osv(_('Error!'), _('Can not create work order for assembly %s !') % (product.name,))
            old_task_ids = project_task_obj.search(cr, uid, [('workorder_id', 'in', wo_line_ids)])
            project_task_obj.unlink(cr, uid, old_task_ids)
            if len(wo_line_ids) > 1:
                workcenter_line_obj.unlink(cr, uid, wo_line_ids[1:],context=context)
            wo_id = wo_line_ids[0]
            #if len(wo_line_ids) != 1:
            #    raise osv.except_osv(_('Error!'),
            #                         _('There are more than 2 work orders for assembly %s !') % (product.name,))

            # if wo.state != 'draft':
            #    raise osv.except_osv(_('Error!'), _('Can not generate tasks for work order not in draft state !'))
            # Remove all current tasks

            # Create all new tasks
            # Check if any part type of PS or POEM
            all_drawing_steps = []
            all_steps = {}
            ps_poem_line_ids = drawing_order_line_obj.search(cr, uid, [('order_id','=',order.id),
                                                                       ('part_type','in',['PS','POEM'])], context=context)
            if ps_poem_line_ids:
                all_drawing_steps = ['Wa']

            cr.execute("SELECT DISTINCT id,work_steps,first_step,quantity from drawing_order_line where order_id = %s" % (order.id,))
            result = cr.dictfetchall()
            for r in result:
                steps = drawing_order_obj.split_work_steps(r["work_steps"])
                for step in steps:
                    if not step in all_steps:
                        all_drawing_steps.append(step)
                        all_steps.update({step: True})
                    #Reupdate the DO quantity
                    vals = {
                        '%s_need_qty' % (step,): r["quantity"],
                        '%s_prepare_qty' % (step,): 0,
                        '%s_done_qty' % (step,): 0,
                    }
                    if step == r['first_step']:
                        #If step in B and Fc then prepare qty = 0 to link with warehouse check in
                        #if step not in ('B','Fc'):
                        vals.update({
                            '%s_prepare_qty' % (step,): r["quantity"],
                        })
                    drawing_order_line_obj.write(cr, uid, [r["id"]],vals)
            for step in all_drawing_steps:
                dept_ids = dept_obj.search(cr, uid, [
                    ('code', '=', step)
                ])
                if dept_ids:
                    dept = dept_obj.browse(cr, uid, dept_ids[0])
                    task_vals = {
                        'name': dept.name,
                        'workorder_id': wo_id,
                        'mfg_ids': [(6,0,mfg_ids)],
                        'user_id': uid,
                        'dept_id': dept.id,
                        'dept_mgr_id': dept.manager_id.id,
                        'drawing_order_id': order.id,
                        'project_id': project_id,
                        'sequence': STAGE_SEQUENCES[_('Waiting On Parts')], #default sequence for waiting on part stage
                    }
                    project_task_obj.create(cr, uid, task_vals)
                    # Add product and qty to task
            wo = workcenter_line_obj.browse(cr, uid, wo_id)
            for task_id in wo.task_ids:
                # prepare_qty = 0
                # need_qty = 0
                sequence = 1
                drawing_order_line_ids = []
                for order_line in task_id.drawing_order_lines:
                    drawing_order_line_ids.append(order_line.id)
                drawing_order_line_ids = drawing_order_line_obj.search(cr, uid, [
                    ('id', 'in', drawing_order_line_ids)
                ], order='item_no asc')
                if task_id.dept_code == 'Fc' or task_id.dept_code == 'P':
                    cnc_p_task_ids.append(task_id.id)
                for order_line in drawing_order_line_obj.browse(cr, uid, drawing_order_line_ids):
                    steps = []
                    if order_line.part_type in ['PS','POEM']:
                        steps = ['Wa']
                    steps.extend(drawing_order_obj.split_work_steps(order_line.work_steps))
                    if task_id.dept_code not in steps:
                        continue
                    if task_id.dept_code != 'A':
                        task_line_ids = project_task_line_obj.search(cr, uid, [
                            ('task_id','=',task_id.id),
                            ('product_id','=',order_line.product_id.id),
                            ('part_number','=',order_line.part_number),
                            ('description','=',order_line.description),
                            ('work_steps','=',order_line.work_steps)
                        ])
                        if task_line_ids:
                            task_line = project_task_line_obj.browse(cr, uid, task_line_ids)[0]
                            if task_id.dept_code != 'Wa':
                                project_task_line_obj.write(cr, uid, [task_line_ids[0]],{
                                    'prepare_qty': drawing_order_obj.get_department_qty(task_id.dept_code, "prepare_qty", order_line) +
                                                   task_line.prepare_qty,
                                    'need_qty': drawing_order_obj.get_department_qty(task_id.dept_code, "need_qty", order_line) +
                                                task_line.need_qty,
                                })
                            else:
                                project_task_line_obj.write(cr, uid, [task_line_ids[0]], {
                                    'need_qty': order_line.quantity +
                                                task_line.need_qty,
                                })
                            continue

                    if task_id.dept_code == 'Wa':
                        if order_line.part_type in ['PS','POEM']:
                            task_line_vals = {
                                'task_id': task_id.id,
                                'order_line_id': order_line.id,
                                'product_id': order_line.product_id.id,
                                'work_steps': order_line.work_steps,
                                'part_number': order_line.part_number,
                                'description': order_line.description,
                                'next_step': '',
                                'sequence': sequence,
                                'item_no': order_line.item_no,
                                'prepare_qty': 0,
                                'done_qty': 0,
                                'need_qty': order_line.quantity,
                            }
                    else:
                        task_line_vals = {
                            'task_id': task_id.id,
                            'order_line_id': order_line.id,
                            'product_id': order_line.product_id.id,
                            'work_steps': order_line.work_steps,
                            'part_number': order_line.part_number,
                            'description': order_line.description,
                            'next_step': '',
                            'sequence': sequence,
                            'item_no': order_line.item_no,
                            'prepare_qty': drawing_order_obj.get_department_qty(task_id.dept_code, "prepare_qty",
                                                                                order_line),
                            'done_qty': 0,
                            'need_qty': drawing_order_obj.get_department_qty(task_id.dept_code, "need_qty",
                                                                             order_line),
                        }
                    # TODO prepare qty of PURCH-S get from inventory
                    if order_line.part_type == 'PS' and task_id.dept_code != 'Wa':
                        purch_s_prepare_qty =  drawing_order_obj.get_department_qty(task_id.dept_code, "prepare_qty",
                                                                            order_line),
                        inventory_qty = order_line.product_id.qty_available
                        if inventory_qty < purch_s_prepare_qty:
                            task_line_vals.update({'prepare_qty': inventory_qty})
                    sequence = sequence + 1

                    next_step = ""
                    if task_id.dept_code != order_line.last_step:
                        for index, step in enumerate(steps):
                            if step == task_id.dept_code:
                                next_step = steps[index + 1]
                                break
                    if task_line_vals["need_qty"] == 0 and next_step == "":
                        next_step = order_line.work_steps
                    task_line_vals.update({
                        'next_step': next_step,
                    })
                    project_task_line_obj.create(cr, uid, task_line_vals)
                # project_task_obj._update_task_line_sequence(cr, uid, [task_id.id])
                project_task_obj.write(cr, uid, [task_id.id], {
                    'assigned_to': task_id.dept_mgr_id.id,
                })
                #Generate warehouse task
                if task_id.dept_code == 'Wa':
                    project_task_obj._create_warehouse_task_report(cr, uid, task_id.id, context=context)
            #Link drawing order to work order:
            drawing_order_obj.write(cr, uid, [order.id],{
                'workorder_id': wo.id,
            })
            #Link work order to drawing order
            workcenter_line_obj.write(cr, uid, [wo.id], {
                'drawing_order_id': order.id,
            })
            if wo.state == 'startworking':
                workcenter_line_obj.action_start_working(cr, uid, [wo.id])
        if cnc_p_task_ids:
            stage_obj = self.pool.get('project.task.type')
            stage_ids = stage_obj.search(cr, uid, [('name', '=', _('Pending')),
                                                   ('project_type', '=', 'mfg')])
            if stage_ids:
                project_task_obj.stage_set(cr, uid, cnc_p_task_ids, stage_ids[0] , context=context)
        return True

    def action_compute(self, cr, uid, ids, properties=None, context=None):
        #TODO: Check if work order is existed and task already started ?
        result = super(mrp_production, self).action_compute(cr, uid, ids, properties, context)
        workcenter_line_obj = self.pool.get('mrp.production.workcenter.line')
        for mo in self.browse(cr, uid, ids):
            remove_workcenter_line_ids = []
            drawing_order_ids = []
            for line in mo.workcenter_lines:
                remove_workcenter_line_ids.append(line.id)
            workcenter_line_obj.unlink(cr, uid, remove_workcenter_line_ids)
            for order in mo.drawing_order_ids:
                if order.state not in ['draft', 'rejected', 'cancel']:
                    drawing_order_ids.append(order.id)
            self._generate_task_from_drawing_orders(cr, uid, drawing_order_ids)
        return result

class project_task(base_stage, osv.osv):
    _inherit = "project.task"
    _name = "project.task"
    _order = "priority asc, sequence asc, production_id desc"

    def do_partial_transfer(self, cr, uid, task_id, task_line_ids, context=None):
        task_line_obj = self.pool.get('project.task.line')
        task_obj = self.pool.get('project.task')
        mr_obj = self.pool.get('material.request')
        mr_line_obj = self.pool.get('material.request.line')
        task = task_obj.browse(cr, uid, task_id, context=context)
        mr_vals = {'mr_dept_id': task.dept_id.id,
                   'type': 'mr'}
        mr_line_vals = []
        transfer_lines = {}

        for line in task_line_obj.browse(cr, uid, task_line_ids, context=context):
            if line.transfer_qty < line.done_qty:
                mfg_ids = [mfg_id.id for mfg_id in line.task_id.mfg_ids]
                if len(mfg_ids) == 0:
                    line_update_vals = mr_line_obj.onchange_product_id(cr, uid, [], line.product_id.id,
                                                                       False,
                                                                       False)
                    line_vals = line_update_vals['value']
                    line_vals.update({
                        'product_id': line.product_id.id,
                        'product_qty': line.done_qty - line.transfer_qty,
                    })
                    mr_line_vals.append((0, 0, line_vals))
                else:
                    for mfg_id in mfg_ids:
                        line_update_vals = mr_line_obj.onchange_product_id(cr, uid, [], line.product_id.id,
                                                                           False,
                                                                           False)
                        line_vals = line_update_vals['value']
                        line_vals.update({
                            'product_id': line.product_id.id,
                            'product_qty': line.done_qty - line.transfer_qty,
                            'mr_sale_prod_id': mfg_id,
                        })
                        mr_line_vals.append((0, 0, line_vals))

                transfer_lines.update({line.id: line.done_qty})
        if mr_line_vals:
            mr_vals.update({'move_lines': mr_line_vals})
            mr_id = mr_obj.create(cr, uid, mr_vals, context=context)
            mr = mr_obj.browse(cr, uid, mr_id, context=context)
            for transfer_line_id in transfer_lines:
                task_line_obj.write(cr, uid, [transfer_line_id], {'transfer_qty': transfer_lines[transfer_line_id]})

        return mr.name

    def do_transfer(self, cr, uid, ids, context=None):
        mr_names = []
        for task_id in self.browse(cr, uid, ids, context=context):
            task_line_ids = [line.id for line in task_id.task_lines]
            mr_names.append(self.do_partial_transfer(cr, uid, task_id.id, task_line_ids, context=context))
        if not mr_names:
            return self.pool.get('warning').info(cr, uid, title='Information',
                                                 message=_("Nothing to transfer"))
        else:
            return self.pool.get('warning').info(cr, uid, title='Information', message= _("Material Request (%s) have been created")% (','.join(mr_names),))

    def action_partial_transfer(self, cr, uid, ids, context=None):
        if not context:
            context = {'active_id': ids[0], 'active_model': 'project.task'}
        if ids:
            mod_obj = self.pool.get('ir.model.data')
            res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'view_warehouse_partial_transfer_wizard')
            res_id = res and res[1] or False
            return {
                'name': _('Warehouse Partial Transfer Wizard'),
                'view_type':'form',
                'view_mode':'form',
                'res_model':'task.partial.transfer.wizard',
                'view_id':res_id,
                'type':'ir.actions.act_window',
                'target':'new',
                'context':context,
            }
        return True

    def action_full_transfer(self, cr, uid, ids, context=None):
        return self.do_transfer(cr, uid, ids, context=context)

    def onchange_pdf_drw_printed(self, cr, uid, ids, pdf_printed, drw_issued, context=None):
        values = {}
        if pdf_printed:
            values.update({'pdf_printed_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)})
        else:
            values.update({'pdf_printed_date': False})
        if drw_issued:
            values.update({'drw_issued_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)})
        else:
            values.update({'drw_issued_date': False})
        return {'value': values}

    def _hours_get(self, cr, uid, ids, field_names, args, context=None):
        res = super(project_task,self)._hours_get(cr, uid, ids, field_names, args, context=context)
        for task in self.browse(cr, uid, ids, context=context):
            if task.project_type == 'mfg' :
                done_qty = 0.0
                need_qty = 0.0
                res[task.id]['progress'] = 0.0
                for task_line in task.task_lines:
                    done_qty += task_line.done_qty
                    need_qty += task_line.need_qty
                if need_qty > 0:
                    res[task.id]['progress'] = done_qty * 100.0 / need_qty
        return res

    def _get_quantities(self, cr, uid, ids, field_names=None, arg=False, context=None):
        if not field_names:
            field_names = []
        if context is None:
            context = {}
        result = {}
        for id in ids:
            result[id] = {}.fromkeys(field_names, 0)
        for task in self.browse(cr, uid, ids):
            prepare_qty = 0
            done_qty = 0
            need_qty = 0
            for line in task.task_lines:
                prepare_qty += line.prepare_qty
                done_qty += line.done_qty
                need_qty += line.need_qty
            result[task.id].update({'prepare_qty': prepare_qty,
                                   'done_qty': done_qty,
                                   'need_qty': need_qty,
                                   })
        return result

    def _get_task(self, cr, uid, ids, context=None):
        result = {}
        for work in self.pool.get('project.task.work').browse(cr, uid, ids, context=context):
            if work.task_id:
                result[work.task_id.id] = True
        return result.keys()

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if view_type == 'form' and not view_id:
            view_name = 'project_task_with_drawing_mfg_form_view'
            view_obj = self.pool.get('ir.ui.view')
            view_ids = view_obj.search(cr, uid, [('name','=',view_name)])
            if view_ids:
                view = view_obj.browse(cr, uid, view_ids[0])
                arch_parts = view.arch.split('<!--DYNAMIC WORKSTEPS DO NOT DELETE-->')
                if len(arch_parts) == 3:
                    department_obj = self.pool.get('hr.department')
                    department_ids = department_obj.search(cr, uid, [('code','in',WORK_STEP_LIST)],order = 'sequence asc')
                    departments = department_obj.browse(cr, uid, department_ids)
                    work_step_fields = ''
                    for department in departments:
                        work_step_fields = work_step_fields + \
                                           "<field name='%s_prepare_qty' class='metro_high_light' attrs=\"{'invisible':[('%s_prepare_qty', '==', 0)],'readonly': True}\"/> \
                                           <field name='%s_done_qty' class='metro_high_light' attrs=\"{'invisible':[('%s_need_qty', '==', 0)],'readonly': True}\"/> \
                                           <field name='%s_need_qty' class='metro_high_light' attrs=\"{'invisible':[('%s_need_qty', '==', 0)],'readonly': True}\"/>" % (department.code,department.code,department.code,department.code,department.code,department.code)
                    #view_arch = arch_parts[0] + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                    #            work_step_fields + '<!--DYNAMIC WORKSTEPS DO NOT DELETE-->' + \
                    #            arch_parts[2]
                    view_arch = arch_parts[0] + \
                                work_step_fields +  \
                                arch_parts[2]
                    view_obj.write(cr, SUPERUSER_ID, [view_ids[0]],{
                        'arch': view_arch
                    })
        res = super(project_task,self).fields_view_get(cr,uid,view_id,view_type,context,toolbar,submenu)
        return res

    def _get_task_ids_from_task_line(self, cr, uid, ids, context=None):
        result = []
        project_task_line_obj = self.pool.get('project.task.line')
        for line in project_task_line_obj.browse(cr, uid, ids):
            if line.task_id.id not in result:
                result.append(line.task_id.id)
        return result

    _columns = {
            'assigned_to': fields.many2one('hr.employee','Assigned To'),
            'date_issued': fields.date('Date Issued'),
            'drawing_order_id': fields.many2one('drawing.order', "Drawing Order",readonly=True),
            'prepare_qty': fields.function(_get_quantities, string='Prepare Quantity',type="integer", readonly=True, store={
                'project.task.line': (_get_task_ids_from_task_line, ['prepare_qty', 'done_qty', 'need_qty'], 40),
            },multi="task_quantities"),
            'done_qty': fields.function(_get_quantities, string='Done Quantity',type="integer", readonly=True, store={
                'project.task.line' : (_get_task_ids_from_task_line, ['prepare_qty', 'done_qty', 'need_qty'], 40),
            },multi="task_quantities"),
            'need_qty': fields.function(_get_quantities, string='Need Quantity',type="integer", readonly=True, store={
                'project.task.line' : (_get_task_ids_from_task_line, ['prepare_qty', 'done_qty', 'need_qty'], 40),
            },multi="task_quantities"),
            'drawing_order_lines': fields.related('drawing_order_id','order_lines',type="one2many",relation="drawing.order.line",string="Drawing Order Lines",readonly=True),
            'big_subassembly_id': fields.related('workorder_id','big_subassembly_id',type='many2one',relation='product.product',string='Big Sub Assembly',readonly=True),
            'dept_code': fields.related('dept_id','code',type="char",size=10,readonly=True,store=True),
            'task_lines': fields.one2many('project.task.line','task_id',string='Task Lines',readonly=True),
            'completion_ids': fields.one2many('project.task.completion','task_id',string='Task Completion',readonly=True),
            'progress': fields.function(_hours_get, string='Progress (%)', multi='hours', group_operator="avg", help="If the task has a progress of 99.99% you should close the task if it's finished or reevaluate the time",
                store = {
                    'project.task.line': (_get_task_ids_from_task_line, ['prepare_qty', 'done_qty', 'need_qty'], 10),
                    'project.task': (lambda self, cr, uid, ids, c={}: ids, ['work_ids', 'remaining_hours', 'planned_hours','state','done_qty','need_qty'], 20),
                    'project.task.work': (_get_task, ['hours'], 40),
                }),
            #'modifyhistory_ids': fields.one2many('project.task.modifyhistory','task_id','Modify History',readonly=True),
            'pdf_printed': fields.boolean('PDF Printed',readonly=False,states={'done':[('readonly', True)]}),
            'pdf_printed_date': fields.date('Printed Date',readonly=False,states={'done':[('readonly', True)]}),
            'drw_issued': fields.boolean('DRW Issued', readonly=False, states={'done': [('readonly', True)]}),
            'drw_issued_date': fields.date('Issued Date', readonly=False, states={'done': [('readonly', True)]})

    }
    def _email_notify_done(self, cr, uid, ids, group_params, context=None):
        task_ids = ', '.join(str(i) for i in ids)
        email_subject = "Manufacturing Tasks %s have completed" % (task_ids,)
        email_body = ""
        email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'],context=context)['email']
        for group_param in group_params:
            email_group_id = self.pool.get('ir.config_parameter').get_param(cr, uid, group_param, context=context)
            if email_group_id:
                utils.email_send_group(cr, uid, email_from, None,email_subject,email_body, email_group_id, context=context)

    def force_close(self, cr, uid, ids, context=None):
        task_line_obj = self.pool.get('project.task.line')
        order_line_obj = self.pool.get('drawing.order.line')
        task_line_ids = []
        for task in self.browse(cr, uid, ids, context=context):
            for task_line in task.task_lines:
                if task_line.prepare_qty < task_line.need_qty or task_line.done_qty < task_line.need_qty:
                    task_line_obj.write(cr, uid, [task_line.id],{
                        'prepare_qty': task_line.need_qty,
                        'done_qty': task_line.need_qty,
                        'state': 'done',
                    })
                    task_line_ids.append(task_line.id)
                    order_line = task_line.order_line_id
                    if order_line:
                        order_line_obj.write(cr, uid, [order_line.id],{
                            '%s_done_qty'% task.dept_code : task_line.need_qty,
                            '%s_prepare_qty'% task.dept_code : task_line.need_qty,
                        },context=context)
                        if not task_line.next_step:
                            order_line_obj.write(cr, uid, [order_line.id], {
                                'status': _('Done'),
                            }, context=context)

        #Mark task done:
        #self.write(cr, uid, ids, {'state':'done'}, context=context)
        task_line_obj.write(cr, uid, task_line_ids, {'state': 'done'}, context=context)
        super(project_task, self).do_close(cr, uid, ids, context=context)
        return True

    def do_close(self, cr, uid, ids, force_close = False, context=None):
        """ Compatibility when changing to case_close. """
        result = True
        completion_obj = self.pool.get('project.task.completion')
        #completion_line_obj = self.pool.get('project.task.completion.line')
        completion_for_task_ids = {}
        for task in self.browse(cr, uid, ids, context=context):
            for task_line in task.task_lines:
                if task_line.need_qty > 0:
                    if task_line.prepare_qty > 0 and task_line.prepare_qty > task_line.done_qty:
                        #Make part done if possible
                        if task.id not in completion_for_task_ids:
                            completion_vals = {
                                'task_id': task.id,
                                'mo_id': task.production_id.id,
                                'big_subassembly_id': task.big_subassembly_id.id,
                                'dept_id': task.dept_id.id,
                                'completion_lines': [],
                            }
                            completion_for_task_ids[task.id] =  completion_vals
                        completion_for_task_ids[task.id]['completion_lines'].append((0,0,{
                            'task_line_id': task_line.id,
                            'sequence': len(completion_for_task_ids[task.id]['completion_lines'])+ 1,
                            'done_qty': task_line.prepare_qty - task_line.done_qty,
                        }))
        completion_ids = []
        for task_id,completion_vals in completion_for_task_ids.iteritems():
            completion_id = completion_obj.create(cr, uid, completion_vals)
            completion_ids.append(completion_id)
        completion_obj.action_confirm(cr, uid, completion_ids)
        #done_task_ids = []
        #for task in self.browse(cr, uid, ids, context=context):
            # Check if all task lines finished ?
        #    total_count = len(task.task_lines)
        #    done_count = 0
        #    for task_line in task.task_lines:
        #        if task_line.need_qty == task_line.done_qty:
        #            done_count += 1
        #    if total_count == done_count:
        #        done_task_ids.append(task.id)
        #result = super(project_task, self).do_close(cr, uid, done_task_ids, context=context)
        #Send email to notify task is done
        #self._email_notify_done(cr, uid, ids, ['group_mrp_supervisor'], context)
        return result
    def do_open(self, cr, uid, ids, context=None):
        """ Compatibility when changing to case_open. """
        result = super(project_task,self).do_open(cr, uid, ids, context=context)
        self.update_task_line_to_start(cr, uid, ids, context)
        return result

    def do_new_task_completion(self, cr, uid, ids, context=None):
        #if 'default_task_id' in context and \
        #    'default_mo_id' in context and \
        #    'default_big_subassembly_id' in context and \
        #    'default_dept_id' in context:
        if not context:
            context = {}
        if ids:
            task_id = ids[0]
            task = self.browse(cr, uid, task_id, context=context)
            if task:
                new_context = context.copy()
                new_context.update({
                    'default_task_id': task_id,
                    'default_mo_id': task.production_id and task.production_id.id or False,
                    'default_dept_id': task.dept_id and task.dept_id.id or False,
                    'default_big_subassembly_id': task.big_subassembly_id and task.big_subassembly_id.id or False,
                })
                mod_obj = self.pool.get('ir.model.data')
                res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'metro_project_task_completion_form_view')
                res_id = res and res[1] or False
                return {
                    'name':'Task Done Quantity Update',
                    'view_type':'form',
                    'view_mode':'form',
                    'res_model':'project.task.completion',
                    'view_id':res_id,
                    'type':'ir.actions.act_window',
                    'target':'new',
                    'context':new_context,
                }
        return True
    def update_task_line_to_start(self, cr, uid, ids, context=None):
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        task_line_obj = self.pool.get('project.task.line')
        for task in self.browse(cr, uid, ids):
            if task.project_type == 'mfg':
                #Check if drawing order line is approved before continue
                #if task.drawing_order_id.state != 'approved':
                #    raise osv.except_osv(_('Error!'), _('Drawing order must be approved in order to start task!'))
                task_line_has_prepare_qty_ids = task_line_obj.search(cr, uid, [
                                                                               ('task_id','=',task.id),
                                                                               ('prepare_qty','!=',0),
                                                                               ])
                if len(task_line_has_prepare_qty_ids) == 0:
                    raise osv.except_osv(_('Error!'), _('Can not start task. Parts are not available yet!'))
                task_lines_ids = task_line_obj.search(cr, uid, [
                                                                ('task_id','=',task.id),
                                                                ('need_qty','>',0),
                                                                ('state','not in',['on_working','done'])
                                                                ])
                task_line_obj.write(cr, uid, task_lines_ids, {'state': 'on_working'})
                for order_line in task.drawing_order_lines:
                    drawing_order_line_obj.write(cr, uid, [order_line.id],{'status': _('On Working')})
        return True


    def _update_purch_s_qty(self, cr, uid, ids=None, context=None):
        product_obj = self.pool.get('product.product')
        task_line_obj = self.pool.get('project.task.line')
        purch_s_ids = product_obj.search(cr, uid, [('part_type','=', 'PS')])
        task_line_ids = task_line_obj.search(cr, uid, [
            ('state','!=','done'),
            ('product_id','in',purch_s_ids),
        ])
        for task_line in task_line_obj.browse(cr, uid, task_line_ids):
            if task_line.need_qty <= task_line.product_id.qty_available:
                task_line_obj.write(cr, uid, [task_line.id],{'prepare_qty': task_line.need_qty})
            else:
                task_line_obj.write(cr, uid, [task_line.id], {'prepare_qty': task_line.product_id.qty_available})
        return True

    def set_deadline_wizard(self, cr, uid, ids, context=None):
        mod_obj = self.pool.get('ir.model.data')
        res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'view_task_deadline_wizard')
        res_id = res and res[1] or False
        return {
            'name': _('Set Tasks Deadline'),
            'view_type': 'form',
            'view_mode': 'form',
            'src_model': 'project.task',
            'res_model': 'task.deadline.wizard',
            'view_id': res_id,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {'active_ids': ids, 'active_model': 'project.task'},
        }
    def set_deadline(self, cr, uid, ids, deadline, context=None):
        self.write(cr, uid, ids, {'date_deadline': deadline}, context=context)
        return True

    def _generate_warehouse_task_report(self, cr, uid, ids=None,context=None):
        task_obj = self.pool.get('project.task')
        task_ids = task_obj.search(cr, uid, [('dept_code','=','Wa')], context=context)
        for task_id in task_ids:
            self._create_warehouse_task_report(cr, uid, task_id, context=context)
        return True

    def _create_warehouse_task_report(self, cr, uid, task_id, context=None):
        report_line_vals = []
        warehouse_task_report_obj = self.pool.get('warehouse.task.report')
        task_obj = self.pool.get('project.task')
        warehouse_task = task_obj.browse(cr, uid, task_id, context=context)
        for line in warehouse_task.task_lines:
            report_line_vals.append((0, 0, {
                'task_line_id': line.id,
                'part_number': line.part_number,
                'order_line_id': line.order_line_id and line.order_line_id.id or False,
                'prepare_qty': 0,
                'done_qty': 0,
            }))
        warehouse_task_report_vals = {
            'task_id': task_id,
            'report_lines': report_line_vals
        }
        report_id = warehouse_task_report_obj.create(cr, uid, warehouse_task_report_vals, context=context)
        return report_id

    def _generate_warehouse_tasks(self, cr, uid, ids=None, context=None):
        drawing_order_obj = self.pool.get('drawing.order')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        task_line_obj = self.pool.get('project.task.line')
        task_obj = self.pool.get('project.task')

        project_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_project', 'project_mfg')[1]
        dept_obj = self.pool.get('hr.department')
        order_ids = drawing_order_obj.search(cr, uid, [('state','in',['confirmed','approved'])], context=context)
        task_ids = []
        for order_id in order_ids:
            ps_poem_line_ids = drawing_order_line_obj.search(cr, uid, [('part_type','in',['PS','POEM']),
                                                                       ('order_id','=',order_id)], context=context)
            if ps_poem_line_ids:
                order = drawing_order_obj.browse(cr, uid, order_id, context = context)
                if order.mo_id and order.workorder_id:
                    #Search warehouse task id
                    task_ids = task_obj.search(cr, uid, [('workorder_id','=',order.workorder_id.id),
                                                         ('dept_code','=','Wa')], context=context)
                    if not task_ids:
                        dept_ids = dept_obj.search(cr, uid, [
                            ('code', '=', 'Wa')
                        ])
                        if dept_ids:
                            dept = dept_obj.browse(cr, uid, dept_ids[0])
                            task_vals = {
                                'name': dept.name,
                                'workorder_id': order.workorder_id.id,
                                'user_id': uid,
                                'dept_id': dept.id,
                                'dept_mgr_id': dept.manager_id.id,
                                'drawing_order_id': order.id,
                                'project_id': project_id,
                                'sequence': STAGE_SEQUENCES[_('Waiting On Parts')],
                                'company_id': order.company_id and order.company_id.id or False
                            }
                            #Split mfg_ids if more than 2:
                            mfg_ids = [mfg_id.id for mfg_id in order.workorder_id.product_id.mfg_ids]
                            if len(mfg_ids) > 1:
                                for mfg_id in mfg_ids:
                                    task_vals.update({'mfg_ids': [(6,0,[mfg_id])]})
                                    task_id = task_obj.create(cr, uid, task_vals, context=context)
                                    task_ids.append(task_id)
                            else:
                                task_vals.update({'mfg_ids': [(6, 0, mfg_ids)]})
                                task_id = task_obj.create(cr, uid, task_vals, context=context)
                                task_ids.append(task_id)
                    for task_id in task_ids:
                        sequence = 1
                        order_line_ids = drawing_order_line_obj.search(cr, uid, [('order_id','=',order_id),
                                                                                 ('part_type','in',['PS','POEM'])],
                                                                       order='item_no asc',
                                                                       context=context)
                        for order_line_id in order_line_ids:
                            order_line = drawing_order_line_obj.browse(cr, uid, order_line_id, context=context)
                            task_line_ids = task_line_obj.search(cr, uid, [
                                ('task_id', '=', task_id),
                                ('product_id', '=', order_line.product_id.id),
                                ('part_number', '=', order_line.part_number),
                                ('description', '=', order_line.description),
                                ('work_steps', '=', order_line.work_steps)
                            ])
                            if task_line_ids:
                                task_line = task_line_obj.browse(cr, uid, task_line_ids)[0]
                                task_line_obj.write(cr, uid, [task_line_ids[0]], {
                                    'need_qty': order_line.quantity +
                                                task_line.need_qty,
                                })
                                continue
                            task_line_vals = {
                                'task_id': task_id,
                                'order_line_id': order_line.id,
                                'product_id': order_line.product_id.id,
                                'work_steps': order_line.work_steps,
                                'part_number': order_line.part_number,
                                'description': order_line.description,
                                'next_step': order_line.first_step,
                                'sequence': sequence,
                                'item_no': order_line.item_no,
                                'prepare_qty': 0,
                                'done_qty': 0,
                                'need_qty': order_line.quantity,
                            }
                            sequence += 1
                            task_line_obj.create(cr, uid, task_line_vals, context=context)
                        self._create_warehouse_task_report(cr, uid, task_id, context=context)

        self.update_task_state(cr, uid, task_ids, True, context=context)
        return True

    def _update_task_mfg_ids(self, cr, uid, ids=None, context=None):
        task_ids = self.search(cr, uid, [('mfg_ids','=',False),
                                         ('production_id','!=',False)])
        for i in xrange(0, len(task_ids), CHUNK_SIZE):
            for task in self.browse(cr, uid, task_ids[i:i + CHUNK_SIZE], context=context):
                mfg_ids = [mfg_id.id for mfg_id in task.production_id.mfg_ids]
                self.write(cr, uid, [task.id], {
                    'mfg_ids': [(6,0,mfg_ids)],
                })
        return True

    def _separate_mfg_id_warehouse_task(self, cr, uid, ids=None, context=None):
        dept_obj = self.pool.get('hr.department')
        dept_ids = dept_obj.search(cr, uid, [('code','=','Wa')], context=context)
        task_ids = self.search(cr, uid, [('dept_id','in', dept_ids),
                                         ('mfg_ids','!=', False)])

        for i in xrange(0, len(task_ids), CHUNK_SIZE):
            for task in self.browse(cr, uid, task_ids[i:i + CHUNK_SIZE], context=context):
                mfg_ids = [mfg_id.id for mfg_id in task.mfg_ids]
                if len(mfg_ids) > 1:
                    count = 1
                    for mfg_id in mfg_ids:
                        if count != 1:
                            copy_task_id = self.copy(cr, uid, task.id, context=context)
                            self.write(cr, uid, [copy_task_id], {'mfg_ids': [(6,0,[mfg_id])]}, context=context)
                        else:
                            self.write(cr, uid, [task.id], {'mfg_ids': [(6, 0, [mfg_id])]}, context=context)
                        count += 1

        return True

    def _check_missed_dealine(self, cr, uid, ids=None, context=None):
        d = datetime.now().date()
        date_now = datetime.strftime(d, "%Y-%m-%d 00:00:00")
        miss_deadline_task_ids = self.search(cr, uid, [('date_deadline','<=',date_now),
                                    ('date_end','=',False),
                                    ('state','not in',['done','cancelled']),])
        if miss_deadline_task_ids:
            stage_obj = self.pool.get('project.task.type')
            stage_ids = stage_obj.search(cr, uid, [
                                                   ('name','=',_('Missed Deadline')),
                                                   ('project_type','=','mfg'),
                                                   ])
            if stage_ids:
                self.stage_set(cr, uid, miss_deadline_task_ids, stage_ids[0] , context=context)
        return True
    def _update_task_line_sequence(self, cr, uid, ids, context=None):
        for task in self.browse(cr, uid, ids,context=context):
            task_line_obj = self.pool.get('project.task.line')
            task_line_ids = task_line_obj.search(cr, uid, [
                ('task_id','=',task.id)
            ],order = 'need_qty desc, product_id asc')
            sequence = 1
            for line in task_line_obj.browse(cr, uid, task_line_ids):
                task_line_obj.write(cr, uid, [line.id],{
                    'sequence': sequence,
                })
                sequence = sequence + 1
        return True
    def move_part_when_task_line_updated(self, cr, uid, task_ids, update_task_line_ids, context=None):
        task_line_obj = self.pool.get('project.task.line')
        drawing_order_line_obj = self.pool.get('drawing.order.line')
        next_task_to_start_ids = []
        for task_line in task_line_obj.browse(cr, uid, update_task_line_ids):
            task = task_line.task_id
            dept_code = task.dept_code
            #Not move parts if department is warehouse
            if dept_code == 'Wa':
                continue
            is_done = False
            task_line_state = ''
            if task_line.need_qty > 0:
                if task_line.done_qty == task_line.need_qty:
                    is_done = True
                    task_line_state = 'done'
                elif task_line.task_id.state != 'draft':
                    task_line_state = 'on_working'
            task_line_obj.write(cr, uid, [task_line.id], {
                        'state': task_line_state,
            })
            order_line = task_line.order_line_id
            order_line_vals = {}
            order_line_vals.update({'%s_done_qty' % dept_code : task_line.done_qty})
            if dept_code == order_line.last_step and is_done:
                order_line_vals.update({'status': _('Done')})
            elif dept_code != order_line.last_step:
                next_step = task_line.next_step
                if next_step:
                    #TODO: Fix bugs when move duplicate parts from A dept
                    done_qty_to_move = task_line.done_qty
                    if dept_code == 'A':
                        same_part_task_line_ids = task_line_obj.search(cr, uid, [
                            ('id','!=', task_line.id),
                            ('task_id','=', task.id),
                            ('product_id', '=', task_line.product_id.id),
                            ('part_number','=', task_line.part_number),
                            ('description','=', task_line.description),
                            ('work_steps', '=', task_line.work_steps)
                        ])
                        for same_part_task_line in task_line_obj.browse(cr, uid, same_part_task_line_ids):
                            done_qty_to_move += same_part_task_line.done_qty

                    order_line_vals.update({
                                            next_step + '_prepare_qty': done_qty_to_move,
                                            })
                    #Find next step task line
                    next_task_ids = self.search(cr, uid, [
                                                          ('workorder_id','=',task.workorder_id.id),
                                                          ('dept_code','=',next_step)
                                                          ])
                    if task_line.order_line_id:
                        next_task_line_ids = task_line_obj.search(cr, uid, [
                                                                        ('task_id','in',next_task_ids),
                                                                        ('order_line_id','=',task_line.order_line_id.id)
                                                                        ])
                    else:
                        next_task_line_ids = task_line_obj.search(cr, uid, [
                            ('task_id', 'in', next_task_ids),
                            ('item_no', '=', task_line.item_no),
                            ('part_number','=', task_line.part_number),
                            ('product_id','=', task_line.product_id.id)
                        ])
                    if next_task_line_ids:
                        task_line_obj.write(cr, uid, next_task_line_ids,{
                                                                        'prepare_qty': done_qty_to_move
                                                                         })
                        next_task_to_start_ids.extend(next_task_ids)
                drawing_order_line_obj.write(cr, uid, [order_line.id],order_line_vals)
        self.update_task_state(cr, uid, list(set(task_ids + next_task_to_start_ids)), open_task=True)
        self._check_missed_dealine(cr, uid, list(set(task_ids)), context=context)
        return True

    def update_task_state(self, cr, uid, ids, open_task= False, context=None):
        stage_obj = self.pool.get('project.task.type')
        done_task_to_finish_ids = []
        open_task_ids = []
        for task in self.browse(cr, uid, ids):
            prepare_qty = task.prepare_qty
            done_qty = task.done_qty
            need_qty = task.need_qty
            new_stage_id = False
            if need_qty > 0 and prepare_qty > 0:
                stage_ids = False
                if done_qty == 0:
                    stage_ids = stage_obj.search(cr, uid, [('name','=',_('Pending')),
                                                          ('project_type','=','mfg')])
                else:
                    stage_ids = stage_obj.search(cr, uid, [('name','=',_('In Progress')),
                                                          ('project_type','=','mfg')])
                if stage_ids:
                    new_stage_id = stage_ids[0]
            #super(project_task,self).write(cr, uid, [task.id], task_vals)
            if new_stage_id:
                self.stage_set(cr, uid, [task.id], new_stage_id, context=context)
            if done_qty == need_qty and need_qty > 0:
                done_task_to_finish_ids.append(task.id)
            if open_task:
                if task.state == 'draft':
                    if task.prepare_qty > 0:
                        open_task_ids.append(task.id)
                elif task.state == 'done' and task.prepare_qty > task.done_qty:
                    open_task_ids.append(task.id)
        if done_task_to_finish_ids:
            super(project_task,self).do_close(cr, uid, done_task_to_finish_ids, context=context)
            self._email_notify_done(cr, uid, done_task_to_finish_ids, ['group_mrp_supervisor'], context)
        if open_task_ids:
            self.do_open(cr, uid, open_task_ids, context=context)
        return True

    def write(self, cr, uid, ids, vals, context=None):
        """" Override write to check and move parts if finnish """
        if not type(ids) is list:
            ids = [ids]
        #Not allow to change dept_id
        if vals.get('dept_id',False):
            dept_id = vals.get('dept_id')
            for task in self.browse(cr, uid, ids, context=context):
                if task.dept_id and task.dept_id != dept_id and task.project_type == 'mfg':
                    raise osv.except_osv(_('Error!'), _('You are not allow to change task to another department!'))
        result = super(project_task,self).write(cr, uid, ids, vals, context)
        #update_task_lines = vals.get('task_lines',False)
        #if update_task_lines:
        #    update_task_line_ids = []
        #    for update_task_line in update_task_lines:
        #        if update_task_line[2] and 'done_qty' in update_task_line[2]:
        #            update_task_line_ids.append(update_task_line[1])
        #    self.move_part_when_task_line_updated(cr, uid, ids, update_task_line_ids, context=context)
        modifyhistory_obj = self.pool.get('project.task.modifyhistory')
        for task_id in ids:
            modifyhistory_obj.create(cr, uid, {
                'task_id': task_id,
                'user_id': uid,
                'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'content': _('Update Task'),
                'vals': '%s'%(vals),
            })
        return result

    def stage_set(self, cr, uid, ids, stage_id, context=None):
        value = {}
        if hasattr(self, 'onchange_stage_id'):
            value = self.onchange_stage_id(cr, uid, ids, stage_id, context=context)['value']
        value['stage_id'] = stage_id
        stage = self.pool.get('project.task.type').browse(cr, uid, stage_id)
        if stage:

            if stage.name in STAGE_SEQUENCES:
                sequence = STAGE_SEQUENCES[stage.name]
                if stage.name == _('Missed Deadline'):
                    cr.execute("SELECT MIN(sequence) as sequence FROM project_task WHERE project_type = 'mfg'")
                    result = cr.dictfetchall()
                    if result[0]['sequence']:
                        sequence = result[0]['sequence'] - 1
                elif stage.name == _('Cancelled'):
                    cr.execute("SELECT MAX(sequence) as sequence FROM project_task WHERE project_type = 'mfg'")
                    result = cr.dictfetchall()
                    if result[0]['sequence']:
                        sequence = result[0]['sequence'] + 1
                else:
                    cr.execute("SELECT MIN(sequence) as sequence FROM project_task WHERE project_type = 'mfg' and stage_id = %s", (stage.id,))
                    result = cr.dictfetchall()
                    if result[0]['sequence']:
                        sequence = result[0]['sequence']
                value['sequence'] = sequence
                #if stage.name == 'On Working':
                #    cr.execute('SELECT MIN(sequence) as sequence FROM project_task')
                #    result = cr.dictfetchall()
                #    min_sequence = result[0]['sequence']
                #    value['sequence'] = min_sequence - 1
                #elif stage.name == 'Waiting':
                #    cr.execute('SELECT MAX(sequence) as sequence FROM project_task')
                #    result = cr.dictfetchall()
                #    max_sequence = result[0]['sequence']
                #    value['sequence'] = max_sequence + 1
        return super(project_task,self).write(cr, uid, ids, value, context=context)

    def case_set(self, cr, uid, ids, new_state_name=None, values_to_update=None, new_stage_id=None, context=None):
        cases = self.browse(cr, uid, ids, context=context)
        # 1. update the stage
        if new_state_name:
            self.stage_set_with_state_name(cr, uid, cases, new_state_name, context=context)
        elif not (new_stage_id is None):
            self.stage_set(cr, uid, ids, new_stage_id, context=context)
        # 2. update values
        if values_to_update:
            super(project_task,self).write(cr, uid, ids, values_to_update, context=context)
        return True

    def print_warehouse_selected(self, cr, uid, ids, type='fulllist', context=None):
        task_print_obj = self.pool.get('task.print')
        wizard_id = task_print_obj.create(cr, uid, {
            'task_day': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
            'report_mode': 'issue',
            'print_type': 'by_team',
        }, context={'active_model': 'project.task', 'active_ids': ids})
        return task_print_obj.do_print(cr, uid, [wizard_id], context={'active_model': 'project.task',
                                                                      'active_ids': ids,
                                                                      'warehouse_report': type})

    def print_issue_drawing_selected(self, cr, uid, ids, context=None):
        task_print_obj = self.pool.get('task.print')
        wizard_id = task_print_obj.create(cr, uid, {
            'task_day': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
            'report_mode': 'issue',
            'print_type': 'by_team',
        }, context={'active_model':'project.task','active_ids': ids})
        return task_print_obj.do_print(cr, uid, [wizard_id],context={'active_model':'project.task',
                                                                     'active_ids': ids})

    def print_task_list_selected(self, cr, uid, ids, context=None):
        task_print_obj = self.pool.get('task.print')
        wizard_id = task_print_obj.create(cr, uid, {
            'task_day': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
            'report_mode': 'brief',
            'print_type': 'by_team',
        }, context={'active_model': 'project.task', 'active_ids': ids})
        return task_print_obj.do_print(cr, uid, [wizard_id],
                                       context={'active_model': 'project.task', 'active_ids': ids})

    def print_part_done_selected(self, cr, uid, ids, context=None):
        task_print_obj = self.pool.get('task.print')
        wizard_id = task_print_obj.create(cr, uid, {
            'task_day': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
            'report_mode': 'full',
            'print_type': 'by_team',
        }, context={'active_model': 'project.task', 'active_ids': ids})
        return task_print_obj.do_print(cr, uid, [wizard_id],
                                       context={'active_model': 'project.task', 'active_ids': ids})

    def download_all_pdf(self, cr, uid, ids, context):
        order_line_ids = []
        order_name = ''
        for task in self.browse(cr, uid, ids):
            if not order_name:
                order_name = task.drawing_order_id.name
                context.update({'order_name': order_name})
            for order_line in task.drawing_order_lines:
                order_line_ids.append(order_line.id)
        return self.pool.get('drawing.order.line').print_pdf(cr, uid, order_line_ids, context=context)

    def download_list_issued_drawings(self, cr, uid, ids, context ):
        # print(ids)
        # mod_obj = self.pool.get('ir.model.data')
        # res = mod_obj.get_object_reference(cr, uid, 'metro_mrp_drawing', 'view_task_print')
        # res_id = res and res[1] or False
        # return {
        #     'name': _('MFG Tasks'),
        #     'view_type': 'form',
        #     'view_mode': 'form',
        #     'src_model': 'project.task',
        #     'res_model': 'task.print',
        #     'view_id': res_id,
        #     'type': 'ir.actions.act_window',
        #     'target': 'new',
        #     'context': {'active_ids':ids,'default_print_type':'by_team', 'default_report_mode':'issue'},
        # }
        return True


    def download_pdf(self, cr, uid, ids, context):
        order_line_ids = []
        order_name = ''
        for task in self.browse(cr, uid, ids):
            #produce_part_ids = []
            if not order_name:
                date_now = datetime.now().strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
                order_name = u'%s-%s-%s-%s-%s'%(task.id,
                                               task.product.name,
                                               task.big_subassembly_id.name,
                                               task.dept_id.name,
                                               date_now)
                context.update({'order_name': order_name})
            for task_line in task.task_lines:
                if task_line.order_line_id:
                    order_line_ids.append(task_line.order_line_id.id)
                #if task_line.need_qty > 0:
                #    produce_part_ids.append(task_line.product_id.id)
            #for order_line in task.drawing_order_lines:
            #    if order_line.product_id.id in produce_part_ids:
            #        order_line_ids.append(order_line.id)
        return self.pool.get('drawing.order.line').print_pdf_pdftk(cr, uid, order_line_ids, context=context)
project_task()

class mrp_production_workcenter_line(osv.osv):
    _inherit = "mrp.production.workcenter.line"
    _columns = {
        'big_subassembly_id': fields.related('bom_id','product_id',type='many2one',relation='product.product',string='Big Sub Assembly',readonly=True),
        'drawing_order_id': fields.many2one('drawing.order','Drawing Order', readonly=True),
    }
    def action_done(self, cr, uid, ids, context=None):
        """ Check if all tasks are done before call parent action_done"""
        project_task_obj = self.pool.get('project.task')
        not_done_task_ids = project_task_obj.search(cr, uid, [
                                                              ('workorder_id','in',ids),
                                                              ('state','not in',['done','cancelled'])
                                                              ])
        if len(not_done_task_ids) > 0:
            raise osv.except_osv(_('Error!'), _('All tasks must be done to finish this work order!'))
        result = super(mrp_production_workcenter_line,self).action_done(cr, uid, ids, context=context)
        return result
    def start_wo(self, cr, uid, ids, context=None):
        drawing_order_obj = self.pool.get('drawing.order')
        project_task_obj = self.pool.get('project.task')
        for workcenter_line in self.browse(cr, uid, ids):
            #Find drawing order of this wo
            drawing_order_ids = drawing_order_obj.search(cr, uid, [
                                                                   ('mo_id','=',workcenter_line.production_id.id),
                                                                   ('product_id','=',workcenter_line.bom_id.product_id.id)
                                                                   ])
            for drawing_order in drawing_order_obj.browse(cr, uid, drawing_order_ids):
                #Check if drawing order is approved ?
                #if drawing_order.state != 'approved':
                #if drawing_order.state in ['draft','rejected','cancel']:
                #    raise osv.except_osv(_('Error!'), _('Drawing order must be ready, confirmed or approved in order to start work order!'))
                #    return False
                first_part_steps = {}
                for order_line in drawing_order.order_lines:
                    if order_line.first_step not in first_part_steps:
                        first_part_steps.update({order_line.first_step : True})
                start_task_ids = []
                for step in first_part_steps:
                    task_ids = project_task_obj.search(cr, uid, [
                                                                 ('workorder_id','=',workcenter_line.id),
                                                                 ('dept_code','=',step)
                                                                 ])
                    start_task_ids.extend(task_ids)
                #Start first task of each
                project_task_obj.do_open(cr, uid, start_task_ids)

    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        result = []
        for wo in self.browse(cr, user, ids, context=context):
            result.append((wo.id,'[%s] %s'%(wo.code , wo.name)))
        return result

    def action_start_working(self, cr, uid, ids, context=None):
        self.start_wo(cr, uid, ids, context)
        result = super(mrp_production_workcenter_line,self).action_start_working(cr, uid, ids, context=context)
        return result    
mrp_production_workcenter_line()