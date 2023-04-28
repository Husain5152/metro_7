# -*- encoding: utf-8 -*-
from osv import fields,osv,orm
from openerp.tools import resolve_attr 
from tools.translate import translate
from lxml import etree
import openerp.addons.decimal_precision as dp
import time

class mto_design(osv.osv):
    _name = "mto.design"
    _columns = {
        'name': fields.char('Configuration#', size=64,required=True,readonly=False),
        'list_price': fields.float('Sale Price', digits_compute=dp.get_precision('Product Price Sale'), required=True),
        'weight': fields.float('Gross Weight', digits_compute=dp.get_precision('Product UoS')),
        'description': fields.text('Description'),
        'multi_images': fields.text("Multi Images"),
        'design_tmpl_id': fields.many2one('attribute.set', 'Template', domain=[('type','=','design')], required=True),
        'change_ids': fields.one2many('mto.design.change','mto_design_id', string='Changes'),
        'product_id': fields.many2one('product.product', string='Product'),
        'print_price': fields.boolean('Print Price'),
        'print_weight': fields.boolean('Print Weight'),
        #common, sale
        'type': fields.char('Type')
    }    
    _defaults={'name':'/', 'type':'common'}
    def _attr_grp_ids(self, cr, uid, ids, field_names, arg=None, context=None):
        res = {}
        for design in self.browse(cr, uid, ids, context=context):
            design_attr_groups = [ag.id for ag in design.design_tmpl_id.attribute_group_ids]
            res[design.id] = design_attr_groups
        return res
    
    def open_designment(self, cr, uid, ids, context=None):
        ir_model_data_obj = self.pool.get('ir.model.data')
        ir_model_data_id = ir_model_data_obj.search(cr, uid, [['model', '=', 'ir.ui.view'], ['name', '=', 'mto_design_form_view_normal']], context=context)
        if ir_model_data_id:
            res_id = ir_model_data_obj.read(cr, uid, ir_model_data_id, fields=['res_id'])[0]['res_id']
        id = None
        if isinstance(ids, list):
            id = ids[0]
        else:
            id = ids
        grp_ids = self._attr_grp_ids(cr, uid, [id], [], None, context)[id]
        ctx = {'open_attributes': True, 'attribute_group_ids': grp_ids}

        return {
            'name': 'Designment',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'res_model': self._name,
            'context': ctx,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'res_id': id or False,
        }

    def _fix_size_bug(self, cr, uid, result, context=None):
    #When created a field text dynamicaly, its size is limited to 64 in the view.
    #The bug is fixed but not merged
    #https://code.launchpad.net/~openerp-dev/openerp-web/6.1-opw-579462-cpa/+merge/128003
    #TO remove when the fix will be merged
        for field in result['fields']:
            if result['fields'][field]['type'] == 'text':
                if 'size' in result['fields'][field]: del result['fields'][field]['size']
        return result    
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}

        def translate_view(source):
            """Return a translation of type view of source."""
            return translate(
                cr, None, 'view', context.get('lang'), source
            ) or source

        result = super(mto_design, self).fields_view_get(cr, uid, view_id,view_type,context,toolbar=toolbar, submenu=submenu)
        
        if view_type == 'form' and context.get('attribute_group_ids'):
            eview = etree.fromstring(result['arch'])
            #for the usage with existing notebook by name 'attributes_notebook', and the position by 'attributes_placeholder'
            notebook = eview.xpath("//notebook[@string='attributes_notebook']")[0]
            attributes_notebook, toupdate_fields = self.pool.get('attribute.attribute')._build_attributes_notebook(cr, uid, context['attribute_group_ids'], context=context, notebook=notebook, attr_holder_name='attributes_placeholder')
            result['fields'].update(self.fields_get(cr, uid, toupdate_fields, context))

            #for the usage with new notebook
#            attributes_notebook, toupdate_fields = self.pool.get('attribute.attribute')._build_attributes_notebook(cr, uid, context['attribute_group_ids'], context=context)
#            result['fields'].update(self.fields_get(cr, uid, toupdate_fields, context))
#            placeholder = eview.xpath("//separator[@string='attributes_placeholder']")[0]
#            placeholder.getparent().replace(placeholder, attributes_notebook)

            result['arch'] = etree.tostring(eview, pretty_print=True)
            result = self._fix_size_bug(cr, uid, result, context=context)
        return result    
    
    def save_and_close_design(self, cr, uid, ids, context=None):
        return {'type': 'ir.actions.act_window_close'}
    def act_pdf(self, cr, uid, ids, context=None):
        if not ids:
            return False 
        if context is None:
            context = {}        
        datas = {
                 'model': 'mto.design',
                 'ids': ids,
                 'form': self.read(cr, uid, ids[0], context=context),
#                'form': self.browse(cr, uid, ids[0], context=context),
        }
        return {'type': 'ir.actions.report.xml', 'report_name': 'mto.design.print', 'datas': datas, 'nodestroy': True}
        
    def onchange_template(self, cr, uid, ids, design_tmpl_id, context=None):
        vals = {'list_price': 0, 'weight': 0}
        if design_tmpl_id and design_tmpl_id > 0:
            data = self.pool.get('attribute.set').read(cr, uid, [design_tmpl_id], ['price_standard','weight_standard'],context=context)
            vals.update({'list_price': data[0]['price_standard'], 'weight': data[0]['weight_standard']})
        return {'value':vals}
                    
    def create(self, cr, uid, data, context=None):        
        attr_set_id = data['design_tmpl_id']
        attr_set = self.pool.get("attribute.set").browse(cr, uid, attr_set_id, context=context)
        #set the selection parameter's standard option as the default value 
        for grp in attr_set.attribute_group_ids:
            for attr in grp.attribute_ids:
                if attr.attribute_type == "select" and attr.standard_option_id:
                    data.update({attr.name:attr.standard_option_id.id})

        if data.get('name','/')=='/':
            data['name'] = self.pool.get('ir.sequence').get(cr, uid, 'mto.design') or '/'
                        
        resu = super(mto_design, self).create(cr, uid, data, context)
        return resu
    
    def write(self, cr, uid, ids, vals, context=None):        
        resu = super(mto_design, self).write(cr, uid, ids, vals, context=context)
        self.update_price(cr, uid, ids, context)
        return resu

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default['name'] = self.pool.get('ir.sequence').get(cr, uid, 'mto.design')
        return super(mto_design, self).copy(cr, uid, id, default, context=context)
        
    def _get_attr_pw_name(self, design, attr):
        price_attr, weight_attr = self._get_attr_pw(design, attr)
        name = attr.field_description
        price_str = ''
        weight_str = ''
        if price_attr and price_attr != 0:
            price_str = '%s%s%s'%((price_attr > 0 and '+' or '-'),attr.currency_id.symbol,abs(price_attr))
        if weight_attr and weight_attr != 0:
            weight_str = '%s%skg'%((weight_attr > 0 and '+' or '-'),abs(weight_attr))
        if price_str != '' or weight_str != '':                    
            if weight_str != '':
                weight_str = '%s%s'%((price_str != '') and "," or "",weight_str)
            name = '%s(%s%s)'%(name,price_str,weight_str)
        return name           
    #get one attribute's price and weight
    def _get_attr_pw(self, design, attr):
        price = 0
        weight = 0
        if attr.attribute_type == "select":
            price = resolve_attr(design,'%s.price'%(attr.name))
            weight = resolve_attr(design,'%s.weight'%(attr.name))
        elif attr.attribute_type == "multiselect":
            options = resolve_attr(design,attr.name)
            for opt in options:
                price = price + resolve_attr(opt,'price')
                weight = weight + resolve_attr(opt,'weight')
        if price is None:
            price = 0
        if weight is None:
            weight = 0            
        return price, weight
    #get one group's price and weight
    def _get_attr_grp_pw(self, design, grp):
        price = 0
        weight = 0
        for attr in grp.attribute_ids:
            price_attr, weight_attr = self._get_attr_pw(design, attr)
            price += price_attr
            weight += weight_attr
        return price, weight      
    def update_price(self, cr, uid, ids, context=None):
        #update the price and weight by  the selected options
        if isinstance(ids,(int,long)):
            ids = [ids] 
        designs = self.browse(cr, uid, ids, context=context)
        for design in designs:
            price_total = 0
            weight_total = 0
            for grp in design.design_tmpl_id.attribute_group_ids:
                price_grp, weight_grp = self._get_attr_grp_pw(design, grp)
                price_total = price_total + price_grp
                weight_total = weight_total + weight_grp
            price_total = design.design_tmpl_id.price_standard + price_total
            weight_total = design.design_tmpl_id.weight_standard + weight_total
            cr.execute("""update mto_design set
                    list_price=%s, weight=%s where id=%s""", (price_total, weight_total, design.id))    
            #update related so lies, johnw, 12/13/2014
            cr.execute("""update sale_order_line set
                    price_unit=%s, th_weight=%s where mto_design_id=%s""", (price_total, weight_total, design.id))    
    def copy_data(self, cr, uid, id, default=None, context=None):
        res = super(mto_design,self).copy_data(cr, uid, id, default=default, context=context)
        if res:
            res.update({'change_ids':False})
        return res  
    def get_report_name(self, cr, uid, id, rpt_name, context=None):
        return "Product Configuration"    
                
class mto_design_change(osv.osv):
    _name = "mto.design.change"
    _description = "Product Configuration Changing Log"
    _order = "change_date desc"
    _columns = {
        'mto_design_id': fields.many2one('mto.design','Configuration',required=True),
        'name': fields.char('Reason', size=128,required=True),
        'source_id': fields.many2one('mto.design.change.source','Source',required=True),
        'change_date': fields.date('Change Date',required=True),
        'user_id': fields.many2one('res.users','Responsible User',required=False),
        'cost_diff': fields.float('Cost Changing'),
        'change_list': fields.text('Changing List',required=True),      
    }
    _defaults={'change_date': lambda *args: time.strftime('%Y-%m-%d'),
               'user_id':lambda obj, cr, uid, context: uid,}
        
class mto_design_change_source(osv.osv):
    _name = "mto.design.change.source"
    _description = "Changing Sources"
    _columns = {
        'name': fields.char('Source Name', size=64, required=True),
        'active': fields.boolean('Active'),
    }
    _defaults = {
        'active': lambda *a: 1,
    }         