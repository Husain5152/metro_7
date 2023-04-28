# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp.tools.translate import _
from openerp import netsvc
#the ID for the purchase requisition and the material request
class sale_product(osv.osv):
    _name = "sale.product"
    _description = "MFG ID"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    
    STATES_COL = {'draft':[('readonly',False)]}
    def _has_project(self,cr,uid,ids,fld_name,arg,context=None):
        res = {}
        for mfg_id in self.browse(cr, uid, ids, context=context):
            res[mfg_id.id] = mfg_id.project_ids and len(mfg_id.project_ids) > 0
        return res
    _columns = {
        'name': fields.char('MFG ID', size=8, required=True,readonly=True, states=STATES_COL),
        'note': fields.text('Description', ),
        'create_uid':  fields.many2one('res.users', 'Creator', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'active': fields.boolean('Active', help="If unchecked, it will allow you to hide the product without removing it.", track_visibility='onchange'),
        'source': fields.selection( [('sale', 'Sales'), ('stock', 'Stocking'), ('other', 'Others')],'Source', required=True,readonly=True, states=STATES_COL),
        'so_id':  fields.many2one('sale.order', 'Sales Order', readonly=True),
        'serial_id': fields.many2one('mttl.serials', 'Product Serial',readonly=True, states={'done':[('readonly',False)]}),
        'mto_design_id': fields.many2one('mto.design', 'Configuration', readonly=True, states=STATES_COL),
        'product_id': fields.many2one('product.product',string='Product', track_visibility='onchange',readonly=True, states=STATES_COL,required=True),
        'bom_id': fields.many2one('mrp.bom',string='BOM', track_visibility='onchange',readonly=True, states=STATES_COL),
        'project_ids': fields.many2many('project.project','project_id_rel','mfg_id','project_id',string='Engineering Project',readonly=True, track_visibility='onchange'),
        #used on the view, since the many2many field already return True when test its value
        'has_project': fields.function(_has_project,string='Has Project',type='boolean'),
        'mrp_prod_ids': fields.many2many('mrp.production','mrp_prod_id_rel','mfg_id','mrp_prod_id',string='Manufacture Order',readonly=True, track_visibility='onchange'),
        'state': fields.selection([
                   ('draft','Draft'),
                   ('confirmed','Confirmed'),
                   ('engineer','Engineering'),
                   ('manufacture','Manufacture'),
                   ('done','Done'),
                   ('cancelled','Cancel')], 'Status', track_visibility='onchange'),
        'config_change_ids': fields.related('mto_design_id','change_ids',type='one2many', relation='mto.design.change', string='Changes'),
        'date_planned': fields.date('Scheduled Date', required=True, select=True, readonly=True, states=STATES_COL),    
        'analytic_account_id': fields.many2one('account.analytic.account', 'Contract/Analytic', help="Link this MFG ID to an analytic account if you need financial management on it. ", ondelete="restrict"),
        'priority': fields.selection([('4','Very Low'), ('3','Low'), ('2','Medium'), ('1','Important'), ('0','Very important')], 'Priority', select=True,readonly=False, states={'done':[('readonly',True)],'cancelled':[('readonly',True)]}),    
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'ID must be unique!'),
    ]
    _defaults = {'state':'draft',
                 'active':True,
                 'name':lambda self, cr, uid, obj, ctx=None: self.pool.get('ir.sequence').get(cr, uid, 'sale.product.id') or '/',
                 'priority': '2',}
    _order = 'id desc'
    
    def name_get(self, cr, uid, ids, context=None):
        if context is None or not context.get('full_name',False):
            return super(sale_product,self).name_get(cr, uid, ids, context=context)
        if not ids:
            return []
        if context is None: context = {}
        names = []
        for obj in self.browse(cr, uid, ids, context=context):
            name = '%s-[%s]%s'%(obj.name, obj.product_id.default_code, obj.product_id.name)
            names.append((obj.id,name))     
        return names               
        
    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=100):
        if context is None or not context.get('full_name',False):
            return super(sale_product,self).name_search(cr, user, name, args=args, operator=operator, context=context, limit=limit)
        if not args:
            args = []
        args = args[:]
        ids = []
        if name:
            ids = self.search(cr, user, [('name', '=like', name+"%")]+args, limit=limit)
            if not ids:
                product_ids = self.pool.get('product.product').search(cr, user, ['|','|',('default_code','like',name+'%'),('name','like','%'+name+'%'),('cn_name','like','%'+name+'%')])
                if product_ids:
                    ids = self.search(cr, user, [('product_id', 'in', product_ids)]+ args, limit=limit)
        else:
            ids = self.search(cr, user, args, context=context, limit=limit)
        return self.name_get(cr, user, ids, context=context)
                
    def copy_data(self, cr, uid, id, default=None, context=None):
        res = super(sale_product,self).copy_data(cr, uid, id, default=default, context=context)
        if res:
            res.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'sale.product.id') or '/',
                        'serial_id':None,
                        'project_ids':None,
                        'mrp_prod_ids':None,
                        'so_id':None,})
        return res 
    def create_analytic_account(self, cr, uid, mfg_id, context=None):
        id_data = self.browse(cr, uid, mfg_id, context=context)
        ana_act_id = self.pool.get('account.analytic.account').create(cr, uid, {'name':'ID%s-COST'%(id_data.name,)},context=context)
        return ana_act_id
        
    def create(self, cr, uid, vals, context=None):
        mfg_id = super(sale_product, self).create(cr, uid, vals, context=context)
        ana_act_id = self.create_analytic_account(cr, uid, mfg_id, context=context)
        self.write(cr, uid, [mfg_id], {'analytic_account_id':ana_act_id}, context=context)
        return mfg_id
                
#    def create(self, cr, uid, data, context=None):       
#        if data.get('name','/')=='/':
#            data['name'] = self.pool.get('ir.sequence').get(cr, uid, 'sale.product.id') or '/'
#                        
#        resu = super(sale_product, self).create(cr, uid, data, context)
#        return resu 
    
    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]

        if 'name' in vals.keys():
            stock_moves = self.pool.get('material.request.line').search(cr,uid,[('mr_sale_prod_id','in',ids)],context=context)
            if stock_moves and len(stock_moves) > 0:
                raise osv.except_osv(_('Warning !'), _("You cannot change the ID which contains stock moving!"))
            work_order_cncs = self.pool.get('work.order.cnc').search(cr,uid,[('sale_product_ids','in',ids)],context=context)
            if work_order_cncs and len(work_order_cncs) > 0:
                raise osv.except_osv(_('Warning !'), _("You cannot change the ID which contains CNC work orders!"))    
        resu = super(sale_product, self).write(cr, uid, ids, vals, context=context)
        if 'priority' in vals.keys():
            self.set_priority(cr,uid,ids,vals['priority'],context)
        return resu
    
    def set_priority(self,cr,uid,ids,priority,context=None):
        if context is None:
            context = {}
        #set all of the sub manufacture orders
        set_ids = []
        mo_ids = []
        for mfg_id in self.browse(cr,uid,ids,context=context):
            if mfg_id.state in ('cancelled','done'):
                continue
            set_ids.append(mfg_id.id)
            mo_ids += [mo.id for mo in mfg_id.mrp_prod_ids]
        if set_ids:
            #update MFG ID
            cr.execute("update sale_product set priority=%s where id  = ANY(%s)", (priority, (set_ids,)))             
            #update manufacture order
            self.pool.get('mrp.production').set_priority(cr, uid, mo_ids, priority, context=context)
             
    def product_id_change(self, cr, uid, ids, product_id, context=None):
        """ Finds BOM of changed product.
        @param product_id: Id of changed product.
        @return: Dictionary of values.
        """
        if not product_id:
            return {'value': {
                'bom_id': False,
            }}
        bom_obj = self.pool.get('mrp.bom')
        product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
        bom_id = bom_obj._bom_find(cr, uid, product.id, product.uom_id and product.uom_id.id, [])
        result = {
            'bom_id': bom_id,
        }
        return {'value': result}
    def unlink(self, cr, uid, ids, context=None):
        for sale_product_id in self.browse(cr, uid, ids, context=context):
            if sale_product_id.state != 'draft': 
                raise osv.except_osv(_('Error'),_("Only MFG ID(%s) with Draft state can be delete!"%(sale_product_id.name,)))
            elif sale_product_id.project_ids or sale_product_id.mrp_prod_ids:
                raise osv.except_osv(_('Error'),_("This ID '%s' already have related projects or manufacture order, can not be delete!"%(sale_product_id.name,)))
        return super(sale_product,self).unlink(cr, uid, ids, context=context)
    
    def create_project(self, cr, uid, id, context=None):
        if isinstance(id,list):
            id = id[0]
        sale_product_id = self.browse(cr, uid, id, context=context)
        if not sale_product_id.project_ids:
            vals = {'name':('ENG Project for ID %s'%(sale_product_id.name,)),
                    'project_type':'engineer',
                    'bom_id':sale_product_id.bom_id.id}
            project_id = self.pool.get('project.project').create(cr, uid, vals, context=context)
            vals = {'project_ids':[(4, project_id)]}
            if sale_product_id.state == 'confirmed':
                vals.update({'state':'engineer'})
            self.write(cr, uid, sale_product_id.id, vals,context=context)
            return project_id
        else:
            return sale_product_id.project_ids[0].id

    def create_mfg_order(self, cr, uid, id, context=None):
        sale_product_id = self.browse(cr, uid, id, context=context)
        if sale_product_id.mrp_prod_ids:
            return sale_product_id.mrp_prod_ids[0].id
        if not sale_product_id.product_id or not sale_product_id.bom_id:
            raise osv.except_osv(_('Error'),_("The product and BOM are required for ID to go to Manufacture state!"))
        vals = {'product_id':sale_product_id.product_id.id,
                'bom_id':sale_product_id.bom_id.id,
                'product_qty':1,
                'product_uom':sale_product_id.product_id.uom_id.id,
                'routing_id':sale_product_id.bom_id.routing_id and sale_product_id.bom_id.routing_id.id or False,
                'origin':sale_product_id.name,
                'date_planned':sale_product_id.date_planned,
                'priority':sale_product_id.priority}
        mrp_prod_id = self.pool.get('mrp.production').create(cr, uid, vals, context=context)
        self.write(cr, uid, sale_product_id.id, {'mrp_prod_ids':[(4, mrp_prod_id)]},context=context)  
        return mrp_prod_id
                                            
    def action_confirm(self, cr, uid, ids, context=None):
        id = ids[0]
        sale_product_id = self.browse(cr,uid,id,context=context)
        if not sale_product_id.product_id or not sale_product_id.bom_id:
            raise osv.except_osv(_('Error'),_("The product and BOM are required for ID to confirm!"))
        self.write(cr, uid, ids, {'state':'confirmed'})
        
    def action_engineer(self, cr, uid, ids, context=None):
        mfg_id = ids[0]
        project_id = self.create_project(cr, uid, mfg_id, context=None)
        self.write(cr, uid, [mfg_id], {'state':'engineer'},context=context)
        return project_id
    
    def action_manufacture(self, cr, uid, ids, context=None):
        mfg_id = ids[0] 
        mfg_prod_id = self.create_mfg_order(cr, uid, mfg_id, context=None)
        self.write(cr, uid, ids, {'state':'manufacture'},context=context)
        return mfg_prod_id

    def action_done(self, cr, uid, ids, context=None, no_except=False):
        for sale_product_id in self.browse(cr, uid, ids, context=context):
            for proj in sale_product_id.project_ids:
                if proj.state not in ('close','cancelled'):
                    if not no_except:
                        raise osv.except_osv(_('Error'),_("This ID '%s' already have opening projects, it can not be done!"%(sale_product_id.name,)))
                    else:
                        return False
            for mo in sale_product_id.mrp_prod_ids:
                if mo.state not in ('done','cancel'):
                    if not no_except:
                        raise osv.except_osv(_('Error'),_("This ID '%s' already have opening manufacture order, it can not be done!"%(mo.name,)))
                    else:
                        return False
        self.write(cr,uid,ids,{'state':'done'})
        
        wf_service = netsvc.LocalService("workflow")
        for id in ids:
            wf_service.trg_validate(uid, 'sale.product', id, 'to_done', cr)
        return True
                
    def action_cancel(self, cr, uid, ids, context=None):
        for sale_product_id in self.browse(cr, uid, ids, context=context):
            if sale_product_id.project_ids or sale_product_id.mrp_prod_ids:
                raise osv.except_osv(_('Error'),_("This ID '%s' already have related projects or manufacture order, can not be cancel!"%(sale_product_id.name,)))
        self.write(cr, uid, ids, {'state':'cancelled'})
        
    def wkf_cancel(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService("workflow")
        self.action_cancel(cr, uid, ids, context=context)
        for id in ids:
            wf_service.trg_validate(uid, 'sale.product', id, 'button_cancel', cr)
        return True
                
    def action_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'draft'})
         
    def action_cancel_draft(self, cr, uid, ids, context=None):
        if not len(ids):
            return False
        self.write(cr, uid, ids, {'state':'draft'})
        wf_service = netsvc.LocalService("workflow")
        for p_id in ids:
            # Deleting the existing instance of workflow for PO
            wf_service.trg_delete(uid, 'sale.product', p_id, cr)
            wf_service.trg_create(uid, 'sale.product', p_id, cr)
        return True
                
    def attachment_tree_view(self, cr, uid, ids, context):
        project_ids = self.pool.get('project.project').search(cr, uid, [('mfg_ids', 'in', ids)])
        task_ids = self.pool.get('project.task').search(cr, uid, [('project_id','in',project_ids)])
        domain = [
             '|','|', 
             '&', ('res_model', '=', 'sale.product'), ('res_id', 'in', ids),
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
                
    def cost_detail(self, cr, uid, ids, context):
        act_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'hr_timesheet', 'act_analytic_cost_revenue')
        act_id = act_id and act_id[1] or False
        act_win = self.pool.get('ir.actions.act_window').read(cr, uid, act_id, [], context=context)
        #set the analytic account id            
        analytic_account_id = self.read(cr, uid, ids[0], ['analytic_account_id'], context=context)['analytic_account_id'][0]
        context['active_id'] = analytic_account_id
        act_win['context'] = eval(act_win['context'], context)        
        return act_win
                
    def material_requested(self, cr, uid, ids, context):
        act_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_purchase', 'action_pur_req_line_full')
        act_id = act_id and act_id[1] or False        
        act_win = self.pool.get('ir.actions.act_window').read(cr, uid, act_id, [], context=context)
        act_win['context'] = {'search_default_mfg_ids': ids[0]}
        return act_win
                
    def material_purchased(self, cr, uid, ids, context):
        act_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_purchase', 'metro_po_line_full_action')
        act_id = act_id and act_id[1] or False       
        act_win = self.pool.get('ir.actions.act_window').read(cr, uid, act_id, [], context=context)
        act_win['context'] = {'search_default_mfg_ids': ids[0]}
        return act_win
                
    def material_incoming(self, cr, uid, ids, context):
        act_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'action_reception_picking_move')
        act_id = act_id and act_id[1] or False        
        act_win = self.pool.get('ir.actions.act_window').read(cr, uid, act_id, [], context=context)
        act_win['context'] = {'search_default_mfg_ids': ids[0]}
        return act_win
                
    def material_consumed(self, cr, uid, ids, context):
        act_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_stock', 'action_stock_mt_rpt')
        act_id = act_id and act_id[1] or False        
        act_win = self.pool.get('ir.actions.act_window').read(cr, uid, act_id, [], context=context)
        act_win['context'] = {'search_default_mr_sale_prod_id': ids[0]}
        return act_win
                
#    def product_produced(self, cr, uid, ids, context):
#        act_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_purchase', 'action_pur_req_line_full')
#        act_id = act_id and act_id[1] or False            
#        act_win = self.pool.get('ir.actions.act_window').read(cr, uid, act_id, [], context=context)
#        act_win['context'] = {'search_default_mfg_ids': ids[0]}
#        return act_win
#                
#    def product_delivered(self, cr, uid, ids, context):
#        act_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_purchase', 'action_pur_req_line_full')
#        act_id = act_id and act_id[1] or False           
#        act_win = self.pool.get('ir.actions.act_window').read(cr, uid, act_id, [], context=context)
#        act_win['context'] = {'search_default_mfg_ids': ids[0]}
#        return act_win
                                  
class mttl_serials(osv.osv):
    _inherit = "mttl.serials"
    _columns = {
        'mfg_id_id': fields.many2one('sale.product', 'MFG ID'),
        'mfg_id_product': fields.related('mfg_id_id', 'product_id', type="many2one", relation="product.product", string="Product")
    }       