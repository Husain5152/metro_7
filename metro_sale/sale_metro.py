# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp import netsvc
import openerp.addons.decimal_precision as dp
from openerp.addons.metro.utils import set_seq_o2m
from openerp.tools.translate import _

class sale_order(osv.osv):
    _inherit="sale.order"
    _name="sale.order"
    
    def _order_line_with_configs(self, cr, uid, ids, field_names, args, context=None):
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            design_line_ids = [line.id for line in order.order_line if line.mto_design_id]
            res[order.id] = design_line_ids
        return res
    
    _columns={
        'checkbox':fields.boolean("Include Payment Information"),
        'payinfo_id':fields.many2one("sale.payinfo",string="Payment Information"),
        'contact_log_ids': fields.many2many('contact.log', 'oppor_contact_log_rel','oppor_id','log_id',string='Contact Logs', ),
        #used by PDF  
        'order_line_with_config': fields.function(_order_line_with_configs, type='one2many', relation='sale.order.line', fields_id='order_id', string='Lines with Configuration')
    }
    _defaults={'checkbox':True}
    _order = 'id desc'
    
    def default_get(self, cr, uid, fields, context=None):
        vals = super(sale_order, self).default_get(cr, uid, fields, context=context)
        vals['company_id'] = company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        return vals

    def onchange_partner_id(self, cr, uid, ids, part, context=None):
        resu = super(sale_order,self).onchange_partner_id(cr, uid, ids, part, context)
        if not part:
            return resu

        part = self.pool.get('res.partner').browse(cr, uid, part, context=context)
        #if the chosen partner is not a company and has a parent company, use the parent to choose the delivery, the 
        #invoicing addresses and all the fields related to the partner.
        if part.parent_id and not part.is_company:
            part = part.parent_id
        if part.country_id and part.country_id.currency_id:
            #the SO's pricelist logic: if Canada then is CAD price list, otherwise is USD pricelist
            pricelist_obj = self.pool.get('product.pricelist')
            #get the company id
            company_id = None
            if ids:
                company_id = self.browse(cr, uid, ids[0], context=context).company_id.id
            else:
                company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
            pricelist_ids = pricelist_obj.search(cr, uid, [('type', '=', 'sale'), ('currency_id', '=', part.country_id.currency_id.id), ('company_id', '=', company_id)], context=context)
            if pricelist_ids:
                resu['value']['pricelist_id'] = pricelist_ids[0]
            else:
                pricelist_ids = pricelist_obj.search(cr, uid, [('type', '=', 'sale'), ('currency_id', '=', part.country_id.currency_id.id)], context=context)
                if pricelist_ids:
                    resu['value']['pricelist_id'] = pricelist_ids[0]                  
        return resu
            
    def get_report_name(self, cr, uid, id, rpt_name, context=None):
        state = self.pool.get('sale.order').read(cr, uid, id, ['state'],context=context)['state']
        if state == 'draft' or state == 'sent':
            return "Quote"
        else:
            return "SalesOrder"
        
    def print_quotation(self, cr, uid, ids, context=None):
        '''
        This function prints the sales order and mark it as sent, so that we can see more easily the next step of the workflow
        '''
        assert len(ids) == 1, 'This option should only be used for a single id at a time'
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'sale.order', ids[0], 'quotation_sent', cr)
        datas = {
                 'model': 'sale.order',
                 'ids': ids,
                 'form': self.read(cr, uid, ids[0], context=context),
        }
        return {'type': 'ir.actions.report.xml', 'report_name': 'sale.agreement', 'datas': datas, 'nodestroy': True}            
                           
    def create(self, cr, uid, data, context=None):        
        set_seq_o2m(cr, uid, data.get('order_line'), context=context)
        return super(sale_order, self).create(cr, uid, data, context)
        
    def write(self, cr, uid, ids, vals, context=None):            
        if not isinstance(ids, (int, long)):
            write_id = ids[0]
        else:
            write_id = ids
        set_seq_o2m(cr, uid, vals.get('order_line'), 'sale_order_line', 'order_id', write_id, context=context)  
        resu = super(sale_order, self).write(cr, uid, ids, vals, context=context)
        if 'state' in vals and vals['state'] == 'agreed':
            #check serials
            order_line_obj = self.pool.get('sale.order.line')
            for order in self.browse(cr, uid, ids, context=context):
                for order_line in order.order_line:
                    msg = order_line_obj._check_serial(cr, uid, exclude_soln_id = order_line.id, context=context)
                    if msg:
                        raise osv.except_osv(_('Error'),msg)            
        return resu
    def action_button_confirm(self, cr, uid, ids, context=None):
        #check serials
        order_line_obj = self.pool.get('sale.order.line')
        for order_line in self.browse(cr, uid, ids[0], context=context).order_line:
            msg = order_line_obj._check_serial(cr, uid, exclude_soln_id = order_line.id, context=context)
            if msg:
                raise osv.except_osv(_('Error'),msg)
        return super(sale_order, self).action_button_confirm(cr, uid, ids, context=context)

    def set_agree(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'agreed'}, context=context)
        order_line_obj = self.pool.get('sale.order.line')
        line_ids = order_line_obj.search(cr, uid, [('order_id','in',ids)], context=context)
        order_line_obj.write(cr, uid, line_ids, {'state': 'draft'},context=context)
        return True
                                    
sale_order()

class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'
    _columns = {
        'mto_design_id': fields.many2one('mto.design', 'Configuration'),
        'serial_ids': fields.many2many('mttl.serials', 'sale_serial_rel','line_id','serials_id',string='Serials',),        
        'price_unit': fields.float('Unit Price', required=True, digits_compute= dp.get_precision('Product Price Sale'), readonly=True, states={'draft': [('readonly', False)]}),
        #config changing dummy field
        'config_changed':fields.function(lambda *a,**k:{}, type='boolean',string="Config Changed",),        
    }
        
    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'mto_design_id': None,
            'serial_ids': None,
        })         
        return super(sale_order_line, self).copy_data(cr, uid, id, default, context=context)     
           
    def onchange_config(self, cr, uid, ids, config_id, context=None):
        val= {}
        if config_id:
            config = self.pool.get('mto.design').browse(cr, uid, config_id, context=context)
            val = {'product_id':config.product_id.id,
                   'price_unit':config.list_price,
                   'th_weight':config.weight,
                   'name':'%s(%s)'%(config.product_id.name, config.name),
                   'config_changed':True}    
        return {'value':val}
    
    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, packaging=False,
            fiscal_position=False, flag=False, context=None):

        res=super(sale_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty,
            uom, qty_uos, uos, name, partner_id,
            lang, update_tax, date_order, packaging=packaging, fiscal_position=fiscal_position, flag=flag, context=context)
        
        if context.get('config_changed'):
            #if the product changing is triggered by the config changing, then do not change the price and weight
            fields_remove = ['price_unit', 'th_weight', 'name']
            for field in fields_remove:
                if res['value'].has_key(field):
                    res['value'].pop(field)
            res['value']['config_changed'] = False
        
        return res

#    def _check_serial(self, cr, uid, exclude_soln_ids, exclude_so_states=None, context=None):
#        '''
#        Check the SO serials existance
#        @param serial_ids: one list of serial ids to check
#        @exclude_soln_ids: the sale order line ids to exclude
#        '''
#        if not exclude_soln_ids:
#            return False
#        #get the serial ids to check from the exclude_soln_ids
#        serial_ids = []
#        for line in self.read(cr, uid, exclude_soln_ids, ['serial_ids'], context=context):
#            serial_ids.extend(line['serial_ids'])
#        if not serial_ids:
#            #no to check serials found then return
#            return False
#            
#        sql = '''
#        select d.serial,  c.id as so_id, c.name as so_name, b.id as so_line_id, b.name as so_line_name, e.default_code as prod_code, f.name as prod_name
#        from sale_serial_rel a
#        join sale_order_line b on a.line_id = b.id
#        join sale_order c on b.order_id = c.id
#        join mttl_serials d on a.serials_id = d.id
#        left join product_product e on b.product_id = e.id
#        left join product_template f on e.product_tmpl_id = f.id
#        where b.id not in %s and d.id in %s
#        '''
#        where_params = [tuple(exclude_soln_ids), tuple(serial_ids)]
#        if exclude_so_states:
#            sql += " and c.state not in %s"
#            where_params.append(tuple(exclude_so_states))            
#        #d.id = ANY(%s)',(ids,)) 
#        #id IN %s', (tuple(ids),))        
#        cr.execute(sql, tuple(where_params))
#        res = cr.dictfetchall()
#        if not res:
#            return False
#        msg = 'Serials on multi orders error:\n\n'
#        for serial in res:
#            msg += 'Serial#: %s SaleOrder: %s\n Product: %s\n'%(serial['serial'],serial['so_name'],serial['so_line_name'])
#        return msg

    def _check_serial(self, cr, uid, exclude_soln_id, exclude_so_states=None, context=None):
        '''
        Do not use the original SQL checking reason, is that the delete/update can not affect to DB before transaction commit.
        Check the SO serials existance
        @param serial_ids: one list of serial ids to check
        @exclude_soln_id: the sale order line id to exclude
        '''
        if not exclude_soln_id:
            return False
        #get the serial ids to check from the exclude_soln_id
        serial_ids = []
        exclude_line = self.read(cr, uid, exclude_soln_id, ['serial_ids','name'], context=context)
        serial_ids.extend(exclude_line['serial_ids'])
        if not serial_ids:
            #no to check serials found then return
            return False
        #search the serials
        domain = [('serial_ids','in',serial_ids), ('id', '!=', exclude_soln_id)]
        if exclude_so_states:
            domain.append(('order_id.state', 'not in', exclude_so_states))
        order_line_ids = self.search(cr, uid, domain, context=context)
        if order_line_ids:
            msg = 'Duplicated serials assignment on %s\n\nExisting orders:\n'%(exclude_line['name'])
            for line in self.browse(cr, uid, order_line_ids, context=context):
                exist_serial_ids = [serial_id.serial for serial_id in line.serial_ids if serial_id.id in serial_ids]
                exist_serials = ','.join(exist_serial_ids)
                msg += 'Serial#: %s SaleOrder: %s\n Line: %s\n'%(exist_serials, line.order_id.name, line.name)
            return msg
        else:
            return False
                    
    def create(self, cr, uid, vals, context=None):            
        new_id = super(sale_order_line, self).create(cr, uid, vals, context)
        #check serials
        if 'serial_ids' in vals:
            msg = self._check_serial(cr, uid, exclude_soln_id = new_id, exclude_so_states=['draft','sent','cancel'], context=context)
            if msg:
                raise osv.except_osv(_('Error'),msg)
        #auto copy the common mto design to a new design
        line = self.browse(cr, uid, new_id, context=context)
        if line.mto_design_id and line.mto_design_id.type == 'common':
            config_obj = self.pool.get('mto.design')
            name = '%s-%s-%s'%(line.mto_design_id.name, line.order_id.name, line.sequence)
            config_new_id = config_obj.copy(cr, uid, line.mto_design_id.id, context=context)
            config_obj.write(cr, uid, config_new_id, {'name':name, 'type':'sale'}, context=context)
            self.write(cr, uid, line.id, {'mto_design_id': config_new_id}, context=context)
        return new_id
        
    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        config_old_datas = self.read(cr, uid, ids, ['mto_design_id'], context=context)            
        resu = super(sale_order_line, self).write(cr, uid, ids, vals, context=context)
        #check serials
        if 'serial_ids' in vals:
            for line_id in ids:
                msg = self._check_serial(cr, uid, exclude_soln_id = line_id, exclude_so_states=['draft','sent','cancel'], context=context)
                if msg:
                    raise osv.except_osv(_('Error'),msg)
        #deal the mto_design_id     
        if 'mto_design_id' in vals:
            lines = self.browse(cr, uid, ids, context)
            config_olds = {}
            for config in config_old_datas:
                config_old_id = config['mto_design_id'] and config['mto_design_id'][0] or None
                config_olds[config['id']] = config_old_id
            config_obj = self.pool.get('mto.design')
            for line in lines:
                config_old_id = config_olds[line.id]
                #clear config, #assign new config,  #change config
                if not line.mto_design_id or not config_old_id or line.mto_design_id.id != config_old_id:
                    if config_old_id:
                        #if old config is for sale, then delete it
                        config_old_type = config_obj.read(cr, uid, config_old_id, ['type'], context=context)                        
                        if config_old_type['type'] == 'sale':
                            config_obj.unlink(cr, uid, config_old_id, context=context)
                    #if new config is common, then do copy
                    if line.mto_design_id and line.mto_design_id.type == 'common':                        
                        context['default_type'] = 'sale'
                        config_new_id = config_obj.copy(cr, uid, line.mto_design_id.id, context=context)
                        name = '%s-%s-%s'%(line.mto_design_id.name, line.order_id.name, line.sequence)
                        config_obj.write(cr, uid, config_new_id, {'name':name, 'type':'sale'}, context=context)     
                        self.write(cr, uid, line.id, {'mto_design_id': config_new_id})
                
        return resu
    
    def edit_config(self, cr, uid, ids, context=None):
        if not context.get('config_id'):
            return False
        return self.pool.get('mto.design').open_designment(cr, uid, context.get('config_id'), context=context)           
    
    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        result = []
        for line in self.browse(cr, user, ids, context=context):
            result.append((line.id, '%s@%s'%(line.name, line.order_id.name)))
        return result    
    
class mto_design(osv.osv):
    _inherit = "mto.design"
    def _so_line_id(self, cr, uid, ids, field_names, args, context=None):
        res = dict.fromkeys(ids,None)
        for id in ids:
            so_ids = self.pool.get('sale.order.line').search(cr, uid, [('mto_design_id','=',id)])
            if so_ids:
                res[id] = so_ids[0]
        return res
    _columns = {'so_line_id': fields.function(_so_line_id, string='SO Line', type='many2one', relation='sale.order.line', store=True)}
    
class account_invoice(osv.osv):

    _inherit="account.invoice"
    _name="account.invoice"
    _columns={
        'check':fields.boolean("Include Payment Information"),
        'payinfo_id':fields.many2one("sale.payinfo",string="Payment Information"),
        'sale_order_ids': fields.many2many('sale.order', 'sale_order_invoice_rel', 'invoice_id', 'order_id', 'Sale Orders'),
    }
	
    def invoice_print(self, cursor, user, ids, context=None):
        res = super(account_invoice, self).invoice_print(cursor, user, ids, context)
        res['report_name']='account.invoice.metro'
        return res
    
    def get_report_name(self, cr, uid, id, rpt_name, context=None):
        if rpt_name is None or rpt_name != 'account.invoice.metro':
            return 'Invoice'
        inv = self.pool.get('account.invoice').read(cr, uid, id, ['number','origin'],context=context)
        if inv['origin'] and inv['origin'].startswith('SO'):
            #get the '0015' in 'Invoice SAJ/2014/0015'
            idx = inv['number'].find('/')
            inv_number = inv['number'][idx+6:]
            return 'Invoice_%s_%s.pdf'%(inv['origin'], inv_number)
        else:
            return "Invoice"
        
account_invoice()

class sale_payinfo(osv.osv):
    _name = "sale.payinfo"
    _columns = {
        'company_id':fields.many2one('res.company', string='Company', required=True, ondelete='cascade'),
        'name':fields.char('Name', size=64, required=True),
        'content': fields.text('Content', required=True),
    }
    
class res_company(osv.osv):
    _inherit="res.company"
    _name="res.company"
    _columns={
        'info':fields.text("Wire Transfer Information"),
        'sale_payinfo_ids':fields.one2many('sale.payinfo', 'company_id', 'Sale Payment Information')
    }   
        
res_company()
