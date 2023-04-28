# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp.tools.translate import _
from openerp import netsvc
import time
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from lxml import etree
from openerp.addons.mrp.mrp import rounding as mrp_rounding
from openerp import tools
from openerp.tools import float_compare
import openerp.addons.decimal_precision as dp
import xlrd
class mrp_bom(osv.osv):
    _inherit = 'mrp.bom'
    def _get_full_name(self, cr, uid, ids, name=None, args=None, context=None):
        if context == None:
            context = {}
        res = {}
        for elmt in self.browse(cr, uid, ids, context=context):
            res[elmt.id] = self._get_one_full_name(elmt)
        return res

    def _get_one_full_name(self, elmt, level=20):
        if level<=0:
            return '...'
        if elmt.bom_id:
            parent_path = self._get_one_full_name(elmt.bom_id, level-1) + " / "
        else:
            parent_path = ''
        return parent_path + elmt.name  
       
    def _check_product(self, cr, uid, ids, context=None):
        """
            Override original one, only check the duplicated products on same BOM level, the duplicated products under variance BOM level are allowed
        """
        all_prod = []
        res = True
        for bom in self.browse(cr, uid, ids, context=context):
            if bom.product_id.id in all_prod:
                res = False
                break
            all_prod.append(bom.product_id.id)
        return res

    def _domain_bom_routing(self, cr=None, uid=None, ids=None, field_name=None, context=None):
        if cr is None:
            return []
        domain = []
        if field_name == 'bom_routing_ids':
            bom = self.read(cr, uid, ids[0], ['routing_id'],context=context)
            if bom.get('routing_id'):
                domain = domain + [('routing_id','=',bom.get('routing_id')[0])]
        if field_name == 'comp_routing_workcenter_ids':
            bom = self.browse(cr, uid, ids[0], context=context)
            if bom.bom_id and bom.bom_id.routing_id:
                domain = domain + [('routing_id','=',bom.bom_id.routing_id.id)]
        return domain 
    
    _columns = {
                'is_common': fields.boolean('Common?'),
                'clone_bom_ids': fields.one2many('mrp.bom','common_bom_id','Clone BOMs'),
                'common_bom_id': fields.many2one('mrp.bom','Common BOM',ondelete='cascade'),
                'code': fields.char('Reference', size=16, required=True, readonly=True),
                'complete_name': fields.function(_get_full_name, type='char', string='Full Name'),
                #for top bom, define the work cetner and the components relationship
                'bom_routing_ids': fields.one2many('mrp.bom.routing.operation', 'bom_id', string='Routing BOM Matrix', domain_fnct=_domain_bom_routing),
#johnw, 01/10/2015, comment the field 'comp_routing_workcenter_ids', it will cause the table 
#mrp_bom_routing_operation creation without ID
#there are designment issues on this table, so only use it by "bom_routing_ids" now
#the code in mrp_view.xml are comment before, do not know the exact reason                
                #for the component, define the sub components related work center from parent bom's routing definition, 
                #only show for the bom components(bom_id is not false)
                #'comp_routing_workcenter_ids': fields.many2many('mrp.routing.workcenter','mrp_bom_routing_operation','bom_comp_id','routing_workcenter_id',
                #                                                string='Work Centers', domain=_domain_bom_routing),
                #08/21/2014, the direct bom id, will be used in manufacture order, the the action_compute()-->_bom_explode() 
                #1.user set the bom_lines of this bom, then will use bom_lines to explode the products and work centers
                #2.if no bom_lines, then check this field 'direct_bom_id', if there is a bom setted, then use this bom to do _bom_explode
                #3.if no above 2 fields, and the 'addthis' parameter is true, then return the product line  
                'direct_bom_id': fields.many2one('mrp.bom','Direct BOM',domain="[('product_id','=',product_id),('bom_id','=',False)]"),
                #09/12/2014, the flag to tell system do not generate consuming move lines, will be used in manufacture order, the the action_compute()-->_bom_explode()
                'no_consume': fields.boolean('No Consume'),
                }
    _defaults = {
        'is_common' : False,
        'no_consume' : False,
    }
    _order = "sequence asc, id desc"
    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'BOM Reference must be unique!'),
        ('name_uniq', 'unique(bom_id,name)', 'BOM Name must be unique per parent BOM!'),
    ] 
    _constraints = [
        (_check_product, 'BoM line product should not be duplicate under one BoM.', ['product_id']),
        ] 
    def onchange_product_id(self, cr, uid, ids, product_id, name, context=None):
        res = super(mrp_bom,self).onchange_product_id(cr, uid, ids, product_id, name, context)
        if not res.get('value',False):
            res['value']={}
        #set the direct_bom_id
        if product_id:
            direct_bom_id = self._bom_find(cr, uid, product_id, None, properties=None)
            res['value'].update({'direct_bom_id':direct_bom_id})
        return res  
    '''
    SQL to update current code
    update mrp_bom set code = to_char(id,'0000')
    '''
    def default_get(self, cr, uid, fields_list, context=None):
        values = super(mrp_bom,self).default_get(cr, uid, fields_list, context)
        values.update({'code':self.pool.get('ir.sequence').get(cr, uid, 'mrp.bom')})
        return values
    #add the code return in the name
    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        result = []
        for bom in self.browse(cr, user, ids, context=context):
            if bom.id <= 0:
                result.append((bom.id,''))
                continue
            result.append((bom.id,'[%s]%s'%(bom.code,self._get_one_full_name(bom))))
                          
        return result
    #add the code search in the searching
    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if name:
            if 'not' in operator:
                ids = self.search(cr, user, [('code', operator, name), ('name', operator, name)] + args, limit=limit, context=context)
            else:
                ids = self.search(cr, user, [('code','=',name)]+ args, limit=limit, context=context)
                if not ids:
                    ids = self.search(cr, user, [('name','=',name)]+ args, limit=limit, context=context)
                if not ids:
                    ids = set()
                    ids.update(self.search(cr, user, args + [('code',operator,name)], limit=limit, context=context))
                    if not limit or len(ids) < limit:
                        # we may underrun the limit because of dupes in the results, that's fine
                        ids.update(self.search(cr, user, args + [('name',operator,name)], limit=(limit and (limit-len(ids)) or False) , context=context))
                    ids = list(ids)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
        result = self.name_get(cr, user, ids, context=context)
        return result
    def copy_data(self, cr, uid, id, default=None, context=None):
        res = super(mrp_bom,self).copy_data(cr, uid, id, default=default, context=context)
        if res:
            res.update({'clone_bom_ids':False,'bom_id':False,'code':self.pool.get('ir.sequence').get(cr, uid, 'mrp.bom'),'bom_routing_ids':False})
        return res    
    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids,(int,long)):
            ids = [ids]
        comp_to_master = 'bom_id' in vals and vals['bom_id'] == False
        if comp_to_master:
            #For the component changing to master BOM, the common bom id will be clear automatically.
            vals.update({'common_bom_id':False})                
        if 'is_common' in vals or 'bom_id' in vals:
            for bom in self.browse(cr, uid, ids, context=context):
                #Common BOM with clone BOM can not clear the 'common BOM' flag
                if 'is_common' in vals and vals['is_common'] == False and bom.clone_bom_ids:
                    raise osv.except_osv(_('Error!'), _('BOM "%s" can not be set to non common BOM, since there are clone parts generated!'%(bom.name,)))
                #Component BOM can not be set to common BOM
                if 'is_common' in vals and vals['is_common'] == True and bom.bom_id:
                    raise osv.except_osv(_('Error!'), _('BOM Component "%s" can not be set to common bom!'%(bom.name,)))
                #Common BOM only can be master BOM, it is not allow to change from master BOM to components
                if 'bom_id' in vals and not bom.bom_id and bom.is_common == True:
                    raise osv.except_osv(_('Error!'), _('common BOM "%s" can not have parent BOM!'%(bom.name,)))
                
                '''
                For the component changing to master BOM, 
                if it is a common BOM's component and have clone bom IDs, the raise exception, 
                since this will make difference between parent's BOM's structure with parent clone BOM's structure
                '''
                if comp_to_master and bom.clone_bom_ids:
                    raise osv.except_osv(_('Error!'), _('Component BOM "%s" have clone BOM, can not change to have parent BOM!'%(bom.name,)))
                
        resu = super(mrp_bom,self).write(cr, uid, ids, vals, context=context)
        
        #sync the common BOM's updating to the clone BOMs
        for bom in self.browse(cr, uid, ids):
            if not bom.clone_bom_ids:
                continue
            #For the BOM having clone_bom_ids(the common BOM and all of its components), need to update their clone_boms
            #1.for the simple fields
            fields = ['product_id', 'standard_price', 'routing_id', 'type', 'position', 'product_rounding','product_efficiency']
            clone_upt_vals = {}
            for field in fields:
                if field in vals:
                    clone_upt_vals.update({field:vals[field]})
            if len(clone_upt_vals) > 0:
                for bom in self.browse(cr, uid, ids, context=context):
                    if bom.clone_bom_ids:
                        clone_bom_ids = [clone_bom.id for clone_bom in bom.clone_bom_ids]
                        self.write(cr, uid, clone_bom_ids, clone_upt_vals, context=context)
            #2.for the parent field 'bom_id' changing, it is not allowed once there are by the previous checking code
        return resu
    
    def create(self, cr, uid, vals, context=None):
        new_id = super(mrp_bom,self).create(cr, uid, vals, context=context)
        #if new BOM’s parent BOM have clone BOMs, clone the new component BOM, and add to parent BOM’s clone BOM’s component list
        if 'bom_id' in vals and vals['bom_id'] != False:
            bom_parent = self.browse(cr, uid, vals['bom_id'], context=context)
            if bom_parent.clone_bom_ids:
                #loop to clone the new bom, and add to parent BOM’s clone BOM’s component list
                for clone_bom in bom_parent.clone_bom_ids:   
                    new_bom_clone_id = self.copy(cr, uid, new_id, context=context)     
                    upt_data = {'bom_id':clone_bom.id,'is_common':False,'common_bom_id':new_id}
                    self.write(cr, uid, [new_bom_clone_id], upt_data, context=context)
        return new_id
   
    def unlink(self, cr, uid, ids, context=None):
        for bom in self.browse(cr, uid, ids, context):
            if bom.clone_bom_ids:
                if bom.is_common: 
                    raise osv.except_osv(_('Error!'), _('BOM "%s" having clone BOMs, can not be delete!'%(bom.name,)))
        '''
        for the common BOM's comonent unlink, if there are clone_bom_ids, 
        database will delete all of the clone BOMs with cascade setting of column 'common_bom_id'.
        '''
        return super(mrp_bom,self).unlink(cr, uid, ids, context)

    def attachment_tree_view(self, cr, uid, ids, context):
        project_ids = self.pool.get('project.project').search(cr, uid, [('bom_id', 'in', ids)])
        task_ids = self.pool.get('project.task').search(cr, uid, ['|',('bom_id', 'in', ids),('project_id','in',project_ids)])
        domain = [
             '|','|', 
             '&', ('res_model', '=', 'mrp.bom'), ('res_id', 'in', ids),
             '&', ('res_model', '=', 'project.project'), ('res_id', 'in', project_ids),
             '&', ('res_model', '=', 'project.task'), ('res_id', 'in', task_ids)
        ]
        res_id = ids and ids[0] or False
        return {
            'name': _('Attachments'),
            'domain': domain,
            'res_model': 'ir.attachment',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'view_id': False,
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d}" % (self._name, res_id)
        }   
    def _check_bom_recursive(self, bom_point):
        check_product_ids = []
        check_boms = [bom_point]
        while check_boms:
            check_bom = check_boms.pop()
            if check_bom.product_id.id in check_product_ids:
                return True
            check_product_ids.append(check_bom.product_id.id)
            for line in check_bom.bom_lines:
                check_boms.append(line)
        return False

    def _bom_explode(self, cr, uid, bom, factor, properties=None, addthis=False, level=0, routing_id=False):
        """ Finds Products and Work Centers for related BoM for manufacturing order.
        @param bom: BoM of particular product.
        @param factor: Factor of product UoM.
        @param properties: A List of properties Ids.
        @param addthis: If BoM found then True else False.
        @param level: Depth level to find BoM lines starts from 10.
        @return: result: List of dictionaries containing product details.
                 result2: List of dictionaries containing Work Center details.
        """

        #=---End checking bom recursive
        routing_obj = self.pool.get('mrp.routing')
        factor = factor / (bom.product_efficiency or 1.0)
        #+++John Wang+++, 07/10/2014# change to use mrp_rounding refer the mrp.rounding
        factor = mrp_rounding(factor, bom.product_rounding)
        if factor < bom.product_rounding:
            factor = bom.product_rounding
        result = []
        result2 = []
        phantom = False
        if bom.type == 'phantom' and not bom.bom_lines:
            newbom = self._bom_find(cr, uid, bom.product_id.id, bom.product_uom.id, properties)

            if newbom:
                res = self._bom_explode(cr, uid, self.browse(cr, uid, [newbom])[0], factor*bom.product_qty, properties, addthis=True, level=level+10)
                result = result + res[0]
                result2 = result2 + res[1]
                phantom = True
            else:
                phantom = False
        if not phantom:
#            if addthis and not bom.bom_lines:
            #+++John Wang, 09/21/2014+++# add the direct_bom_id checking
            if addthis and not bom.bom_lines and not bom.direct_bom_id and not bom.no_consume:
                #+++John Wang, 07/10/2014+++# add the bom_id and parent_bom_id to supply the product's bom info
#                result.append(
#                {
#                    'name': bom.product_id.name,
#                    'product_id': bom.product_id.id,
#                    'product_qty': bom.product_qty * factor,
#                    'product_uom': bom.product_uom.id,
#                    'product_uos_qty': bom.product_uos and bom.product_uos_qty * factor or False,
#                    'product_uos': bom.product_uos and bom.product_uos.id or False,
#                })
                result.append(
                {
                    'parent_bom_id': bom.bom_id and bom.bom_id.id or False,
                    'bom_id': bom.id,
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
                    #+++John Wang, 07/10/2014+++# add the routing_workcenter_id to supply the routing operation's info later.
#                    result2.append({
#                        'name': tools.ustr(wc_use.name) + ' - '  + tools.ustr(bom.product_id.name),
#                        'workcenter_id': wc.id,
#                        'sequence': level+(wc_use.sequence or 0),
#                        'cycle': cycle,
#                        'hour': float(wc_use.hour_nbr*mult + ((wc.time_start or 0.0)+(wc.time_stop or 0.0)+cycle*(wc.time_cycle or 0.0)) * (wc.time_efficiency or 1.0)),
#                    })
                    #+++John Wang, 09/12/2014+++# get the routing work center tasks.
                    wc_tasks = []
                    project_mfg_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_project', 'project_mfg')[1]
                    for wc_task in wc_use.wc_task_ids:
                        emp_ids = self.pool.get('hr.employee').search(cr, uid, [('department_id','=',wc_task.dept_id.id)])
                        emp_ids = [(4,emp_id) for emp_id in emp_ids]
                        wc_task = {'project_id':project_mfg_id,
                                   'sequence':wc_task.sequence,
                                   'dept_id':wc_task.dept_id.id,
                                   'dept_mgr_id':wc_task.dept_id.manager_id.id,
                                   'emp_ids':emp_ids,
                                   'name':wc_task.name,
                                   'planned_hours':wc_task.planned_hours,}
                        wc_tasks.append((0,0,wc_task))
                    result2.append({
                        'bom_id': bom.id,
                        'routing_id': wc_use.routing_id.id,
                        'routing_operation_id': wc_use.id,
                        #+++ HoangTK - 01/04/2016 : Remove Work center name
                        #'name': tools.ustr(wc_use.name) + ' - '  + tools.ustr(bom.name),
                        'name': tools.ustr(bom.name),
                        #--- HoangTK - 01/04/2016 : Remove Work center name
                        'workcenter_id': wc.id,
                        'sequence': level+(wc_use.sequence or 0),
                        'cycle': cycle,
                        'hour': float(wc_use.hour_nbr*mult + ((wc.time_start or 0.0)+(wc.time_stop or 0.0)+cycle*(wc.time_cycle or 0.0)) * (wc.time_efficiency or 1.0)),
                        'task_ids': wc_tasks
                    })
            for bom2 in bom.bom_lines:
                # +++HoangTK, 03/26/2019# check for bom recursive before proceed
                if self._check_bom_recursive(bom2):
                    raise osv.except_osv(_('Error'), _('Bom can not include itself as a child'))
                res = self._bom_explode(cr, uid, bom2, factor, properties, addthis=True, level=level+10)
                result = result + res[0]
                result2 = result2 + res[1]
            #+++John Wang, 08/21/2014+++# add the direct_bom_id field handling code
            ###begin###
            if not bom.bom_lines and bom.direct_bom_id:
                # +++HoangTK, 03/26/2019# check for bom recursive before proceed
                if self._check_bom_recursive(bom.direct_bom_id):
                    raise osv.except_osv(_('Error'), _('Direct bom can not include itself as a child'))
                res = self._bom_explode(cr, uid, bom.direct_bom_id, factor, properties, addthis=True, level=level+10)
                result = result + res[0]
                result2 = result2 + res[1]
            ###end###
                                
        return result, result2        
'''
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        result = super(mrp_bom,self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type=='form':
            eview = etree.fromstring(result['arch'])
            fields = result['fields'].keys()
            attrs = "{'readonly':[('common_bom_id','!=',False)]}"
            editable_fields = ['quantity','name','reference','sequence','date_start','date_stop']
            for field in fields:
                if field in editable_fields:
                    continue
                elems = eview.xpath("//field[@name='%s']"%(field,))
                if not elems:
                    continue
                elem_fld = elems[0]
                elem_fld.set('attrs',attrs)
            result['arch'] = etree.tostring(eview, pretty_print=True)
                        
        return result        
'''  

class mrp_bom_routing_operation(osv.osv):
    _name = 'mrp.bom.routing.operation'
    _order = 'id desc'
    _rec_name = 'bom_comp_id'
    '''
    bom_comp_id:
    the component is the BOM that need manufacture, can be:
    1.same as bom_id
    2.the sub bom_id's sub BOM having bom_lines
    '''    
    _columns = {
        'bom_id': fields.many2one('mrp.bom', string='BOM', required=True),
        'routing_id': fields.many2one('mrp.routing', string='Routing', required=True),
        'routing_workcenter_id': fields.many2one('mrp.routing.workcenter', string='Routing Work Center', required=True ),
        'bom_comp_id': fields.many2one('mrp.bom', string='BOM Component', required=True ),
        'consume_material': fields.boolean('Consume Material')
    }
    _sql_constraints = [
        ('routing_wc_comp_uniq', 'unique(routing_workcenter_id,bom_comp_id)', 'You can not add duplicated "Routing Work Center"-"Component" with same BOM and Routing!'),
    ]
    _defaults = {'consume_material': True}
    def create(self, cr, uid, vals, context=None):
        if vals.has_key('bom_comp_id'):
            #added from the bom components screen
            if not vals.has_key('bom_id'):
                bom_comp = self.pool.get('mrp.bom').browse(cr, uid, vals['bom_comp_id'],context=context)
                vals['bom_id'] = bom_comp.bom_id.id
                vals['routing_id'] = bom_comp.bom_id.routing_id
        super(mrp_bom_routing_operation,self).create(cr, uid, vals, context=context)
class mrp_routing(osv.osv):
    _inherit = 'mrp.routing'
    _sql_constraints = [
        ('name', 'unique(name)', 'Routing name must be unique!'),
        ('code', 'unique(code)', 'Routing code must be unique!'),
    ]
class mrp_routing_workcenter(osv.osv):
    _inherit = 'mrp.routing.workcenter'
    _columns = {
        'oper_pre_ids': fields.many2many('mrp.routing.workcenter', 'route_oper_flow','oper_next_id','oper_pre_id', string='Previous Workcenters', domain="[('routing_id','=',routing_id)]"),
        'oper_next_ids': fields.many2many('mrp.routing.workcenter', 'route_oper_flow','oper_pre_id','oper_next_id', string='Next Workcenters', domain="[('routing_id','=',routing_id)]"),
        'wc_task_ids': fields.one2many('mrp.routing.workcenter.task','routing_wc_id',string='Work center tasks')
    }
    _sql_constraints = [
        ('name', 'unique(routing_id,name)', 'Routing work center name must be unique under one routing!'),
    ]    
class mrp_routing_workcenter_task(osv.osv):        
    _name = 'mrp.routing.workcenter.task'
    _description = "Routing work center's task"
    _columns = {
                'routing_wc_id': fields.many2one('mrp.routing.workcenter', 'Parent Work Center', select=True, ondelete='cascade',),
                'name': fields.char('Task Summary', size=128, required=True, select=True),
                'sequence': fields.integer('Sequence', select=True, help="Gives the sequence order when displaying a list of tasks."),
                'dept_id':fields.many2one('hr.department',string='Team',),
                'planned_hours': fields.float('Planned Hours'),
                }
class mrp_production(osv.osv):
    _inherit = 'mrp.production'
    _order = 'id desc, priority, date_planned asc';
    _columns = {
        'mfg_ids': fields.many2many('sale.product', 'mrp_prod_id_rel','mrp_prod_id','mfg_id',string='MFG IDs', readonly=True, states={'draft':[('readonly',False)]}),
        'location_src_id': fields.property(
            'stock.location',
            type='many2one',
            relation='stock.location',
            string="Raw Materials Location",
            view_load=True,
            required=True,
            readonly=True, 
            states={'draft':[('readonly',False)]},
            help="Location where the system will look for components."),
        'location_dest_id': fields.property(
            'stock.location',
            type='many2one',
            relation='stock.location',
            string="Finished Products Location",
            view_load=True,
            required=True,
            readonly=True, 
            states={'draft':[('readonly',False)]},
            help="Location where the system will stock the finished products."),
        'move_lines': fields.many2many('material.request.line', 'mrp_production_move_ids', 'production_id', 'move_id', 'Products to Consume',
            domain=[('state','not in', ('done', 'cancel'))], readonly=True, states={'draft':[('readonly',False)]}),
        'move_lines2': fields.many2many('material.request.line', 'mrp_production_move_ids', 'production_id', 'move_id', 'Consumed Products',
            domain=[('state','in', ('done', 'cancel'))], readonly=True, states={'draft':[('readonly',False)]}),
        'comp_lines': fields.one2many('mrp.wo.comp', 'mo_id', string='Components'),  
        'priority': fields.selection([('4','Very Low'), ('3','Low'), ('2','Medium'), ('1','Important'), ('0','Very important')], 'Priority', 
                                     select=True,  readonly=False, states=dict.fromkeys(['cancel', 'done'], [('readonly', True)])),
        'task_mgr_id': fields.many2one('res.users', 'Task Manager'),           
        #+++ HoangTK - 11/16/2015: Add reference to bigsubassembly
        'drawing_order_ids': fields.one2many('drawing.order','mo_id',string='Drawing Orders'),
        'date_planned': fields.datetime('Scheduled Date', required=True, select=1, readonly=False, states={'done':[('readonly',True)]}),
        'name': fields.char('Reference', size=64, required=True, readonly=False,
                            states={'done': [('readonly', True)]}),
        'date_start': fields.datetime('Start Date', select=True, readonly=False,states={'done': [('readonly', True)]}),
        'date_finished': fields.datetime('End Date', select=True, readonly=False,states={'done': [('readonly', True)]}),

        #--- HoangTK - 11/16/2015
    }
    _defaults={'priority': '2',
                'task_mgr_id': lambda obj, cr, uid, context: uid,
                'date_planned': lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
               }
    #add the 'update=True, mini=True' inhreited from mrp_operations.mrp_production
    def write(self, cr, uid, ids, vals, context=None, update=True, mini=True):
        resu = super(mrp_production, self).write(cr, uid, ids, vals, context=context,update=update,mini=mini)        
        if 'priority' in vals.keys():
            self.set_priority(cr,uid,ids,vals['priority'],context)
        return resu

    def action_in_production(self, cr, uid, ids):
        """ Changes state to In Production and writes starting date.
        @return: True
        """
        # obj = self.browse(cr, uid, ids)[0]
        # workcenter_pool = self.pool.get('mrp.production.workcenter.line')
        # wf_service = netsvc.LocalService("workflow")
        # for prod in self.browse(cr, uid, ids):
        #     if prod.workcenter_lines:
        #         wf_service.trg_validate(uid, 'mrp.production.workcenter.line', prod.workcenter_lines[0].id,
        #                                 'button_start_working', cr)
        # return super(mrp_production, self).action_in_production(cr, uid, ids)
        return self.write(cr, uid, ids, {'state': 'in_production', 'date_start': time.strftime('%Y-%m-%d %H:%M:%S')})

    def set_priority(self,cr,uid,ids,priority,context=None):
        if context is None:
            context = {}
        #set all of the sub manufacture orders, work orders, MFG tasks priority
        set_ids = []
        wo_ids = []
        for mo in self.browse(cr,uid,ids,context=context):
            if mo.state in ('cancel','done'):
                continue
            set_ids.append(mo.id)
            wo_ids += [wo.id for wo in mo.workcenter_lines]
        if set_ids:
            #update manufacture order
            cr.execute("update mrp_production set priority=%s where id  = ANY(%s)", (priority, (set_ids,)))
            #update manufacture order
            self.pool.get('mrp.production.workcenter.line').set_priority(cr, uid, wo_ids, priority, context=context)
    
    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default.update({
            'workcenter_lines' : [],
            'date_start' : None,
            'date_finished' : None,
            'workcenter_lines' : [],
        })
        return super(mrp_production, self).copy(cr, uid, id, default, context)
    
    def _make_production_consume_line(self, cr, uid, production_line, parent_move_id, source_location_id=False, context=None):
        stock_move = self.pool.get('stock.move')
        production = production_line.production_id
        # Internal shipment is created for Stockable and Consumer Products
        if production_line.product_id.type not in ('product', 'consu'):
            return False
        destination_location_id = production.product_id.property_stock_production.id
        if not source_location_id:
            source_location_id = production.location_src_id.id
        move_id = stock_move.create(cr, uid, {
            'name': production.name,
            'date': production.date_planned,
            'product_id': production_line.product_id.id,
            'product_qty': production_line.product_qty,
            'product_uom': production_line.product_uom.id,
            'product_uos_qty': production_line.product_uos and production_line.product_uos_qty or False,
            'product_uos': production_line.product_uos and production_line.product_uos.id or False,
            'location_id': source_location_id,
            'location_dest_id': destination_location_id,
            'move_dest_id': parent_move_id,
            'state': 'waiting',
            'company_id': production.company_id.id,
        })
        #add by johnw, 07/10/2014, add the MFG ID for material requisition
        if production_line.mfg_id:
            self.pool.get('material.request.line').write(cr, uid, [move_id], {'mr_sale_prod_id':production_line.mfg_id.id},context=context)
        production.write({'move_lines': [(4, move_id)]}, context=context)
        return move_id
    def _make_production_internal_shipment(self, cr, uid, production, context=None):
        ir_sequence = self.pool.get('ir.sequence')
        stock_picking = self.pool.get('stock.picking')
        routing_loc = None
        pick_type = 'internal'
        partner_id = False

        # Take routing address as a Shipment Address.
        # If usage of routing location is a internal, make outgoing shipment otherwise internal shipment
        if production.bom_id.routing_id and production.bom_id.routing_id.location_id:
            routing_loc = production.bom_id.routing_id.location_id
            if routing_loc.usage != 'internal':
                pick_type = 'out'
            partner_id = routing_loc.partner_id and routing_loc.partner_id.id or False

        # Take next Sequence number of shipment base on type
#        pick_name = ir_sequence.get(cr, uid, 'stock.picking.' + pick_type)
        #johnw, 07/11/2014, fix the picking name getting issue, the 'internal' sequence name should be 'stock.picking'
        #begin
        pick_seq_name = pick_type=='internal' and 'stock.picking' or 'stock.picking.' + pick_type
        pick_name = ir_sequence.get(cr, uid, pick_seq_name)
        #end

        picking_id = stock_picking.create(cr, uid, {
            'name': pick_name,
            'origin': (production.origin or '').split(':')[0] + ':' + production.name,
            'type': pick_type,
            'move_type': 'one',
            'state': 'auto',
            'partner_id': partner_id,
            'auto_picking': self._get_auto_picking(cr, uid, production),
            'company_id': production.company_id.id,
        })
        production.write({'picking_id': picking_id}, context=context)
        return picking_id    
    '''
    1.add the 'consume_move_id' when matching the wo.product_lines and consume moves
    '''
    def action_produce(self, cr, uid, production_id, production_qty, production_mode, context=None):
        """ To produce final product based on production mode (consume/consume&produce).
        If Production mode is consume, all stock move lines of raw materials will be done/consumed.
        If Production mode is consume & produce, all stock move lines of raw materials will be done/consumed
        and stock move lines of final product will be also done/produced.
        @param production_id: the ID of mrp.production object
        @param production_qty: specify qty to produce
        @param production_mode: specify production mode (consume/consume&produce).
        @return: True
        """
        stock_mov_obj = self.pool.get('stock.move')
        production = self.browse(cr, uid, production_id, context=context)
        # HoangTK - Check if this MO can set to done state
        drawing_order_obj = self.pool.get('drawing.order')
        task_obj = self.pool.get('project.task')
        stage_obj = self.pool.get('project.task.type')
        order_ids = drawing_order_obj.search(cr, uid, [('mo_id','=',production_id),
                                                       ('state','not in',['approved','rejected','cancel'])], context=context)
        if order_ids:
            raise osv.except_osv(_('Error'),_('All drawing orders have to be approved, rejected or cancelled  to be able to proceed'))
        stage_ids = stage_obj.search(cr, uid, [('state','in',['done','cancelled'])], context=context)
        task_ids = task_obj.search(cr, uid, [('production_id','=',production_id),
                                             ('stage_id','not in',stage_ids)
                                             ], context=context)
        if task_ids:
            raise osv.except_osv(_('Error'), _('All tasks must be closed or cancelled to be able to proceed'))

        produced_qty = 0
        for produced_product in production.move_created_ids2:
            if (produced_product.scrapped) or (produced_product.product_id.id != production.product_id.id):
                continue
            produced_qty += produced_product.product_qty
        if production_mode in ['consume','consume_produce']:
            consumed_data = {}

            # Calculate already consumed qtys
            for consumed in production.move_lines2:
                if consumed.scrapped:
                    continue
                if not consumed_data.get(consumed.product_id.id, False):
                    consumed_data[consumed.product_id.id] = 0
                consumed_data[consumed.product_id.id] += consumed.product_qty

            # Find product qty to be consumed and consume it
            for scheduled in production.product_lines:

                # total qty of consumed product we need after this consumption
                total_consume = ((production_qty + produced_qty) * scheduled.product_qty / production.product_qty)

                # qty available for consume and produce
                qty_avail = scheduled.product_qty - consumed_data.get(scheduled.product_id.id, 0.0)

                if qty_avail <= 0.0:
                    # there will be nothing to consume for this raw material
                    continue

#                raw_product = [move for move in production.move_lines if move.product_id.id==scheduled.product_id.id]
                #johnw, 07/11/2014, add the 'consume_move_id' when matching the wo.product_lines and consume moves
                #begin
                raw_product = [move for move in production.move_lines if move.product_id.id==scheduled.product_id.id and move.id==scheduled.consume_move_id.id]
                #end
                if raw_product:
                    # qtys we have to consume
                    qty = total_consume - consumed_data.get(scheduled.product_id.id, 0.0)
                    if float_compare(qty, qty_avail, precision_rounding=scheduled.product_id.uom_id.rounding) == 1:
                        # if qtys we have to consume is more than qtys available to consume
                        prod_name = scheduled.product_id.name_get()[0][1]
                        raise osv.except_osv(_('Warning!'), _('You are going to consume total %s quantities of "%s".\nBut you can only consume up to total %s quantities.') % (qty, prod_name, qty_avail))
                    if qty <= 0.0:
                        # we already have more qtys consumed than we need
                        continue
                    #below calling method will cause some stock_move's sub classes can not be called, like metro_stock.stock_move.action_done(),_create_account_move_line()
#                    raw_product[0].action_consume(qty, raw_product[0].location_id.id, context=context)
                    stock_mov_obj.action_consume(cr, uid, [raw_product[0].id], qty, raw_product[0].location_id.id, context=context)

        if production_mode == 'consume_produce':
            # To produce remaining qty of final product
            #vals = {'state':'confirmed'}
            #final_product_todo = [x.id for x in production.move_created_ids]
            #stock_mov_obj.write(cr, uid, final_product_todo, vals)
            #stock_mov_obj.action_confirm(cr, uid, final_product_todo, context)
            produced_products = {}
            for produced_product in production.move_created_ids2:
                if produced_product.scrapped:
                    continue
                if not produced_products.get(produced_product.product_id.id, False):
                    produced_products[produced_product.product_id.id] = 0
                produced_products[produced_product.product_id.id] += produced_product.product_qty

            for produce_product in production.move_created_ids:
                produced_qty = produced_products.get(produce_product.product_id.id, 0)
                subproduct_factor = self._get_subproduct_factor(cr, uid, production.id, produce_product.id, context=context)
                rest_qty = (subproduct_factor * production.product_qty) - produced_qty

                if rest_qty < production_qty:
                    prod_name = produce_product.product_id.name_get()[0][1]
                    raise osv.except_osv(_('Warning!'), _('You are going to produce total %s quantities of "%s".\nBut you can only produce up to total %s quantities.') % (production_qty, prod_name, rest_qty))
                if rest_qty > 0 :
                    stock_mov_obj.action_consume(cr, uid, [produce_product.id], (subproduct_factor * production_qty), context=context)

        for raw_product in production.move_lines2:
            new_parent_ids = []
            parent_move_ids = [x.id for x in raw_product.move_history_ids]
            for final_product in production.move_created_ids2:
                if final_product.id not in parent_move_ids:
                    new_parent_ids.append(final_product.id)
            for new_parent_id in new_parent_ids:
                stock_mov_obj.write(cr, uid, [raw_product.id], {'move_history_ids': [(4,new_parent_id)]})

        # TODO: Close all related PRs, unreserve all
        pur_req_obj = self.pool.get('pur.req')
        req_ids = pur_req_obj.search(cr, uid, [('mo_id','=',production_id),
                                               ('state','not in',['done','cancel'])],context=context)
        if req_ids:
            pur_req_obj.action_unreserved_products(cr, uid, req_ids, context=context)
            pur_req_obj.action_force_done(cr, uid, req_ids, context=context)
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'mrp.production', production_id, 'button_produce_done', cr)
        return True    

    def action_compute(self, cr, uid, ids, properties=None, context=None):
        resu = super(mrp_production,self).action_compute(cr, uid, ids, properties, context)
        #generate work order's components
        bom_oper_obj = self.pool.get('mrp.bom.routing.operation')
        wo_comp_obj = self.pool.get('mrp.wo.comp')
        for mo in self.browse(cr, uid, ids, context=context):
            if not mo.workcenter_lines:
                continue            
            for wo in mo.workcenter_lines:
                domain = [('bom_id','=',wo.bom_id.id),('routing_id','=',wo.routing_id.id,),('routing_workcenter_id','=',wo.routing_operation_id.id)]                
                comp_ids = bom_oper_obj.search(cr, uid, domain, context=context)
                for comp in bom_oper_obj.browse(cr, uid, comp_ids, context=context):
                    vals = {'mo_id':mo.id, 'wo_id':wo.id, 'comp_id': comp.bom_comp_id.id, 'bom_route_oper_id': comp.id, 'qty': comp.bom_comp_id.product_qty*mo.product_qty}
                    wo_comp_obj.create(cr, uid, vals, context=context)
        #+++ HoangTK - 11/23/2015: Link drawing order lines to task
        drawing_order_obj = self.pool.get("drawing.order")
        task_obj = self.pool.get("project.task")
        for mo_id in self.browse(cr, uid, ids):
            for wo in mo_id.workcenter_lines:
                big_subassembly_id = wo.big_subassembly_id.id
                #Search drawing order for this big_subassembly_id
                drawing_order_ids = drawing_order_obj.search(cr, uid, [
                                                                       ('mo_id','=',mo_id.id),
                                                                       ('product_id','=',big_subassembly_id)
                                                                       ])
                if drawing_order_ids:
                    drawing_order_id = drawing_order_ids[0]
                    task_ids = []
                    for task_id in wo.task_ids:
                        task_ids.append(task_id.id)
                    task_obj.write(cr, uid, task_ids, {
                                                       'drawing_order_id' : drawing_order_id,
                                                       })
                    
        #--- HoangTK - 11/23/2015 
        return resu
    
    def action_production_end(self, cr, uid, ids, context=None):
        """ Call the MFG ID's action_done method
        """        
        resu = super(mrp_production,self).action_production_end(cr, uid, ids)
        #comment the code temporary, since user may can not create all of the manufacture orders for one ID at one time, 
        #they may need create another manufacture order for one ID again
        '''
        mo = self.browse(cr, uid, ids)[0]
        mfgid_obj = self.pool.get('sale.product')
        #set the no_except parameter then no exception will be throw if ID can not be close
        for mfg_id in mo.mfg_ids:
            mfgid_obj.action_done(cr, uid, [mfg_id.id],context=context,no_except=True)
        '''
        return resu

class mrp_wo_comp(osv.osv):
    _name = 'mrp.wo.comp'    
    _columns = {
        'mo_id': fields.many2one('mrp.production', string='Manufacture Order', required=True),
        'wo_id': fields.many2one('mrp.production.workcenter.line', string='Work Order', required=True),
        'comp_id': fields.many2one('mrp.bom', string='Component', required=True ),
        #related bom/routing matrix id, can be empty if user add this component manually
        'bom_route_oper_id': fields.many2one('mrp.bom.routing.operation', string='Bom Routing Matrix'),
        #quantity need to be manufacture, from the bom definition if craeated by system
        'qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
        #quantity done
        'qty_done': fields.float('Quantity Done', digits_compute=dp.get_precision('Product Unit of Measure')),
        'state': fields.selection([('draft','Draft'),('cancel','Cancelled'),('startworking', 'In Progress'),('done','Finished')], string = 'Status'),
        'note': fields.text('Description', ),
        'mfg_ids': fields.related('mo_id','mfg_ids',type='many2many',relation='sale.product', rel='mrp_prod_id_rel',id1='mrp_prod_id',id2='mfg_id',string='MFG IDs',),
    }
    _sql_constraints = [
        ('wo_comp_uniq', 'unique(wo_id,comp_id)', 'You can not add duplicated "Work Order Component" with same WorkOrder and Component!'),
    ]
                  
from openerp.addons.mrp.mrp import mrp_production as mrp_prod_patch        
def mrp_prod_action_confirm(self, cr, uid, ids, context=None):
    """ Confirms production order.
    @return: Newly generated Shipment Id.
    """
    shipment_id = False
    wf_service = netsvc.LocalService("workflow")
    uncompute_ids = filter(lambda x:x, [not x.product_lines and x.id or False for x in self.browse(cr, uid, ids, context=context)])
    self.action_compute(cr, uid, uncompute_ids, context=context)
    for production in self.browse(cr, uid, ids, context=context):
        shipment_id = self._make_production_internal_shipment(cr, uid, production, context=context)
        produce_move_id = self._make_production_produce_line(cr, uid, production, context=context)

        # Take routing location as a Source Location.
        source_location_id = production.location_src_id.id
        if production.bom_id.routing_id and production.bom_id.routing_id.location_id:
            source_location_id = production.bom_id.routing_id.location_id.id

        for line in production.product_lines:
            consume_move_id = self._make_production_consume_line(cr, uid, line, produce_move_id, source_location_id=source_location_id, context=context)
            #johnw, 07/10/2014, update mrp_production_product_line.consume_move_id once get the consume move
            #begin
            self.pool.get('mrp.production.product.line').write(cr, uid, line.id, {'consume_move_id':consume_move_id},context=context)
            #end 
            shipment_move_id = self._make_production_internal_shipment_line(cr, uid, line, shipment_id, consume_move_id,\
                             destination_location_id=source_location_id, context=context)
            self._make_production_line_procurement(cr, uid, line, shipment_move_id, context=context)

        wf_service.trg_validate(uid, 'stock.picking', shipment_id, 'button_confirm', cr)
        production.write({'state':'confirmed'}, context=context)
    return shipment_id

mrp_prod_patch.action_confirm = mrp_prod_action_confirm

def mrp_prod_action_compute(self, cr, uid, ids, properties=None, context=None):
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
        cr.execute('delete from mrp_production_product_line where production_id=%s', (production.id,))
        cr.execute('delete from mrp_production_workcenter_line where production_id=%s', (production.id,))
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
        '''
        by johnw, 07/10/2014, the mfg ids are required and the number of ID must be equal to the produtc quantity, 
        then the next step, the ID can be put to the material request line correctly
        '''
        #begin
        if not production.mfg_ids or production.product_qty % len(production.mfg_ids) != 0.0 :
            raise osv.except_osv(_('Error!'), _("MFG IDs are required and the product quantity %s must be equal or multiple to the number of them IDs."%(production.product_qty,)))
        mfg_id_cnt = len(production.mfg_ids)
        #end
        factor = uom_obj._compute_qty(cr, uid, production.product_uom.id, production.product_qty, bom_point.product_uom.id)
        # +++HoangTK, 03/26/2019# check for bom recursive before proceed
        if bom_obj._check_bom_recursive(bom_point):
            raise osv.except_osv(_('Error'), _('Bom can not include itself as a child'))
        res = bom_obj._bom_explode(cr, uid, bom_point, factor / bom_point.product_qty, properties, routing_id=production.routing_id.id)
        results = res[0]
        results2 = res[1]
        
        for line in results:
#            line['production_id'] = production.id
#            prod_line_obj.create(cr, uid, line)
            '''
            by johnw, 07/10/2014, create the product lines by ID
            '''
            line['production_id'] = production.id
            line['product_qty'] = line['product_qty']/mfg_id_cnt
            if line.get('product_uos_qty'):
                line['product_uos_qty'] = line['product_uos_qty']/mfg_id_cnt
            for mfg_id in production.mfg_ids:
                line['mfg_id'] = mfg_id.id
                prod_line_obj.create(cr, uid, line)
        wo_ids = []
        for line in results2:
            line['production_id'] = production.id
            line['priority'] = production.priority
            mfg_ids = [(4,mfg_id.id) for mfg_id in production.mfg_ids]
            line['mfg_ids'] = mfg_ids
            for wc_task in line['task_ids']:
                wc_task[2].update({'priority':production.priority, 
                                   'user_id':production.task_mgr_id.id,
                                   'mfg_ids':mfg_ids})
            wo_new_id = workcenter_line_obj.create(cr, uid, line)
            wo_ids.append(wo_new_id)
        #add by johnw@07/1102014, update the wo_pre_ids and wo_next_ids
        #========begin=========
        sql = '''
        select a.id as pre_id, e.id as next_id
        from mrp_production_workcenter_line a
        join mrp_routing_workcenter b on a.routing_operation_id  = b.id 
        join route_oper_flow c on b.id = c.oper_pre_id 
        join mrp_routing_workcenter d on c.oper_next_id = d.id  
        join mrp_production_workcenter_line e 
            on e.routing_operation_id = d.id
            and a.production_id = e.production_id
            and a.bom_id = e.bom_id
            and a.routing_id = e.routing_id
        where a.id = ANY(%s)
        order by a.id,e.id
        '''
        cr.execute(sql, (wo_ids,))
        wo_ids_flow = dict.fromkeys(wo_ids,False)
        #retrieve data, store to the dict
        for data in cr.fetchall():
            wo_pre_id = data[0]
            wo_next_id = data[1]
            if not wo_ids_flow[wo_pre_id]:
                wo_ids_flow[wo_pre_id] = []
            wo_ids_flow[wo_pre_id].append((4,wo_next_id))
            
        #loop to update wo_next_ids, since the many2many is two-way, so the wo_pre_ids will be updated automatically.
        for wo_id, wo_next_ids in wo_ids_flow.items():
            workcenter_line_obj.write(cr, uid, [wo_id], {'wo_next_ids':wo_next_ids}, context=context)
        #========end=========
         
    return len(results)

mrp_prod_patch.action_compute = mrp_prod_action_compute

from openerp.addons.mrp_operations.mrp_operations import mrp_production_workcenter_line as mrp_prod_wc
mrp_prod_wc._order = 'id desc, priority, production_id desc, sequence asc'
        
class mrp_production_workcenter_line(osv.osv):
    _inherit = 'mrp.production.workcenter.line'
    '''
    Get one work order's stock moving by the bom/routing/operation, join with mrp_bom_routing_operation, mrp_production_product_line
    These moves are the moves can make material requistion
    Since one bom component can have more than one routing operation, so one stock move may be occured under several work orders \
    but they are one move in fact. 
    '''
    def _move_lines(self, cr, uid, ids, field_name, arg, context=None):
        res=dict((id,[]) for id in ids)
        sql = '''
        select b.id, c.consume_move_id
        from mrp_bom_routing_operation a
        join mrp_production_workcenter_line b 
            on a.bom_id = b.bom_id and a.routing_id = b.routing_id and a.routing_workcenter_id = b.routing_operation_id and a.consume_material = true
        join mrp_production_product_line c
            on b.production_id = c.production_id and a.bom_comp_id = c.parent_bom_id
        where b.id = ANY(%s)
        '''
        cr.execute(sql, (ids,))
        for data in cr.fetchall():
            res[data[0]].append(data[1])
        return res
    
    def _has_pre_wo(self, cr, uid, ids, field_name, arg, context=None):
        res = dict.fromkeys(ids,False)
        for wo in self.browse(cr, uid, ids, context=context):
            if wo.wo_pre_ids:
                res[wo.id] = True
        return res    
            
    _columns = {
        'code': fields.char('Reference', size=16, required=True, readonly=True),
        'bom_id': fields.many2one('mrp.bom', string='BOM', readonly=True),
        'routing_id': fields.many2one('mrp.routing', string='Routing', readonly=True),
        'routing_operation_id': fields.many2one('mrp.routing.workcenter', string='Routing Operation', readonly=True ),
        'stock_move_ids': fields.function(_move_lines, relation='material.request.line', type='one2many', string='Material'),
        'has_pre_ids': fields.function(_has_pre_wo, type='boolean', string='Has Pre WO'),
        'wo_pre_ids': fields.many2many('mrp.production.workcenter.line', 'mrp_wo_flow','wo_next_id','wo_pre_id', string='Previous WOs', domain="[('production_id','=',production_id),('bom_id','=',bom_id),]"),
        'wo_next_ids': fields.many2many('mrp.production.workcenter.line', 'mrp_wo_flow','wo_pre_id','wo_next_id', string='Next WOs', domain="[('production_id','=',production_id),('bom_id','=',bom_id),]"),
        #add 'ready' state
        'state': fields.selection([('draft','Draft'),('ready','Ready'),('cancel','Cancelled'),('pause','Pending'),('startworking', 'In Progress'),('done','Finished')],'Status', readonly=True,
                                 help="* When a work order is created it is set in 'Draft' status.\n" \
                                       "* When user sets work order in start mode that time it will be set in 'In Progress' status.\n" \
                                       "* When work order is in running mode, during that time if user wants to stop or to make changes in order then can set in 'Pending' status.\n" \
                                       "* When the user cancels the work order it will be set in 'Canceled' status.\n" \
                                       "* When order is completely processed that time it is set in 'Finished' status."),
        #the work order related components from bom, can generated from mrp_bom_workcenter_operation when executing action_compute()
        'comp_lines': fields.one2many('mrp.wo.comp', 'wo_id', string='Components'),
        #'mfg_ids': fields.related('production_id','mfg_ids', type='many2many', relation='sale.product',rel='mrp_prod_id_rel',id1='mrp_prod_id',id2='mfg_id',string='MFG IDs', readonly=True),
        #+++ HoangTK - 11/23/2015: Chage back mfg_ids to related
        #'mfg_ids': fields.many2many(obj='sale.product',rel='mrp_wo_id_rel',id1='wo_id',id2='mfg_id',string='MFG IDs', readonly=False),
        'mfg_ids': fields.related('production_id','mfg_ids',type="many2many",  relation="sale.product", string="MFG IDs",readonly=True),  
        #--- HoangTK - 11/23/2015
        'priority': fields.selection([('4','Very Low'), ('3','Low'), ('2','Medium'), ('1','Important'), ('0','Very important')], 'Priority', select=True),
    }
    _defaults = {'code':lambda self, cr, uid, obj, ctx=None: self.pool.get('ir.sequence').get(cr, uid, 'mrp.production.workcenter.line') or '/',
                 'priority': '2',}
                 
    #add the code return in the name
    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        result = []
        for wo in self.browse(cr, user, ids, context=context):
            if wo.id <= 0:
                result.append((wo.id,''))
                continue
            #+++ HoangTK - 11/19/2015: Remove the code before name
            #result.append((wo.id,'[%s]%s'%(wo.code,wo.name)))
            result.append((wo.id,'%s'%(wo.name)))
            #--- HoangTK - 11/19/2015
                          
        return result
    #add the code search in the searching
    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if name:
            if 'not' in operator:
                ids = self.search(cr, user, [('code', operator, name), ('name', operator, name)] + args, limit=limit, context=context)
            else:
                ids = self.search(cr, user, [('code',operator,name)]+ args, limit=limit, context=context)
                if not ids:
                    ids = self.search(cr, user, [('name',operator,name)]+ args, limit=limit, context=context)
                if not ids:
                    ids = set()
                    ids.update(self.search(cr, user, args + [('code',operator,name)], limit=limit, context=context))
                    if not limit or len(ids) < limit:
                        # we may underrun the limit because of dupes in the results, that's fine
                        ids.update(self.search(cr, user, args + [('name',operator,name)], limit=(limit and (limit-len(ids)) or False) , context=context))
                    ids = list(ids)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
        result = self.name_get(cr, user, ids, context=context)

        return result     
    def wo_docs(self, cr, uid, ids, context):
        bom_ids = [wo.bom_id.id for wo in self.browse(cr, uid, ids, context=context) if wo.bom_id]
        return self.pool.get('mrp.bom').attachment_tree_view(cr, uid, bom_ids, context=context) 
        
    #improve the action_done() in mrp_operations
    def action_done(self, cr, uid, ids, context=None):
        resu = super(mrp_production_workcenter_line,self).action_done(cr, uid, ids, context)
        '''
        Trigger all of the next workorder to go to the 'ready' state, this will call the wo.is_ready() by the workflow definition 
        '''
        wf_service = netsvc.LocalService("workflow")
        for wo in self.browse(cr, uid, ids, context=context):
            if wo.wo_next_ids:
                for wo_next in wo.wo_next_ids:
                    wf_service.trg_validate(uid, 'mrp.production.workcenter.line', wo_next.id, 'ready_to_start', cr)
        return resu    
    
    def is_ready(self, cr, uid, ids):
        """
        @return: True or False
        """
        res = True
        for wo in self.browse(cr, uid, ids):
            #if there are previous WO, only when all of them are done, then this WO is ready to start
            if wo.wo_pre_ids:
                for wo_pre in wo.wo_pre_ids:
                    if wo_pre.state != 'done':
                        res = False
                        break
        return res

    def onchange_mo(self, cr, uid, ids, production_id, context=None):
        resu = {}
        if production_id:
            wo = self.pool.get('mrp.production').read(cr, uid, production_id, ['mfg_ids'],context=context)
            value={'mfg_ids':wo['mfg_ids']}
            resu['value'] = value
        return resu
    def _check_before_save(self, cr, uid, ids, vals, context=None):
        assert ids == None or len(ids) == 1, 'This option should only be used for a single work order update at a time'
        '''
        from GUI: [[6, False, [418, 416]]]
        from code to create: [(4, 418)(4, 416)]
        Only check from GUI: len(vals['mfg_ids']) == 1 and 
        '''
        if 'mfg_ids' in vals and len(vals['mfg_ids']) == 1 and len(vals['mfg_ids'][0]) == 3:
            mo = None
            #get the workorder data
            if not 'production_id' in vals:
                task = self.browse(cr, uid, ids[0], context=context)
                mo = task.production_id
            else:
                mo = self.pool.get('mrp.production').browse(cr,uid,vals['production_id'],context=context)
            #get the manufacture order's MFG ID's ID&Name list
            mo_mfg_ids = []
            mo_mfg_names = []
            for mfg_id in mo.mfg_ids:
                mo_mfg_ids.append(mfg_id.id)
                mo_mfg_names.append(mfg_id.name)
            #loop to check make sure the MFG IDs of work order belongs to manufacture order's MFG IDs
            for wo_mfg_id in vals['mfg_ids'][0][2]:
                if not wo_mfg_id in mo_mfg_ids:
                    wo_mfg_name = self.pool.get('sale.product').read(cr, uid, wo_mfg_id, ['name'], context=context)['name']
                    raise osv.except_osv(_('Invalid Action!'), _('The task MFG IDs:%s must match the manufacture order''s MFG IDs:%s')%(wo_mfg_name,','.join(mo_mfg_names)))
        return True
    
    def write(self, cr, uid, ids, vals, context=None, update=True):
        self._check_before_save(cr, uid, ids, vals, context=context)
        return super(mrp_production_workcenter_line,self).write(cr, uid, ids, vals, context=context, update=True)
        
    def create(self, cr, uid, vals, context=None):
        self._check_before_save(cr, uid, None, vals, context=context)
        return super(mrp_production_workcenter_line,self).create(cr, uid, vals, context=context)
                    
class mrp_production_product_line(osv.osv):
    _inherit = 'mrp.production.product.line'
    _columns = {
        'parent_bom_id': fields.many2one('mrp.bom', string='Parent BOM', readonly=True),
        'bom_id': fields.many2one('mrp.bom', string='BOM', readonly=True),
        'consume_move_id': fields.many2one('stock.move', string='Consume Move', readonly=True),
        'mfg_id': fields.many2one('sale.product', string='MFG ID', readonly=True),
    }

class mrp_workcenter(osv.osv):
    _inherit = 'mrp.workcenter'
    _columns = {
        'manager_id': fields.many2one('res.users', 'Manager'),
        'members': fields.many2many('hr.employee', 'wc_emp_rel', 'wc_id', 'emp_id', 'Work Center Members',
            help="Work Center's members are employees who can have an access to the work orders related to this work center.", ),
                }
class product_product(osv.osv):
    _inherit = "product.product"
        
    _columns = {
        'material': fields.char(string=u'Material', size=32, help="The material of the product"),
    }