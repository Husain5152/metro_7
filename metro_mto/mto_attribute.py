# -*- encoding: utf-8 -*-
from osv import fields,osv,orm
import openerp.addons.decimal_precision as dp
class attribute_set(orm.Model):
    _inherit = "attribute.set"
    _columns = {
        'type': fields.char('Type'),        
        'price_standard': fields.float('Standard Price', digits_compute= dp.get_precision('Product Price')),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),        
        'weight_standard': fields.float('Standard Weight(kg)', digits_compute=dp.get_precision('Product Unit of Measure')),
        'notes': fields.text('Notes'),
        }
    def _get_currency_id(self, cr, uid, context):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        return user.company_id.currency_id.id
        
    _defaults = {
        'currency_id': _get_currency_id,
    }  
class attribute_group(orm.Model):
    _inherit = "attribute.group"
    _columns = {
        'type': fields.char('Type'),
        'notes': fields.text('Notes'),
        }
    _sql_constraints = [
        ('name_model_uniq', 'unique (name, model_id, attribute_set_id)', 'The name of the group has to be unique for a given model''s attribute set !'),
    ]

class attribute_attribute(orm.Model):
    _inherit = "attribute.attribute"
    _columns = {
        'type': fields.char('Type'),
        'standard_option_id': fields.many2one('attribute.option', 'Standard Option', domain="[('attribute_id','=',id)]"),
        #johnw, 12/12/2014, useless fields ,removed     
        #'price_standard': fields.float('Standard Price', digits_compute= dp.get_precision('Product Price')),
        #'weight_standard': fields.float('Standard Weight(kg)', digits_compute=dp.get_precision('Product Unit of Measure')),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'm2m_tags': fields.boolean('Many2Many Tags'),
        'notes': fields.text('Notes'),
        }
   
    def _get_currency_id(self, cr, uid, context):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        return user.company_id.currency_id.id
        
    _defaults = {
        'currency_id': _get_currency_id,
        'm2m_tags': False
    }    
#    def onchange_standard_option(self, cr, uid, ids, standard_option_id, context=None):
#        vals = {'price_standard': 0, 'weight_standard': 0}
#        if standard_option_id and standard_option_id > 0:
#            data = self.pool.get('attribute.option').read(cr, uid, [standard_option_id], ['price','weight'],context=context)
#            vals.update({'price_standard': data[0]['price'], 'weight_standard': data[0]['weight']})
#        return {'value':vals}
    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        def _name_get(d):
            name = d.get('name','')
            type = d.get('attribute_type',False)
            if type and type == 'select':
                #get the standard option name
                s_opt_id = d.get('standard_option_id')
                if s_opt_id:
                    name = '%s [%s]' % (name,s_opt_id.name)
                    #add the price and weight
                    if s_opt_id.price:
                        name = '%s [$%s]' % (name,s_opt_id.price)
                    if s_opt_id.weight:
                        name = '%s [%s]' % (name,s_opt_id.weight)
            '''
            #add the price and weight
            price = d.get('price_standard',0.0)
            weight = d.get('weight_standard',0.0)
            if price > 0:
                name = '%s [$%s]' % (name,price)
            if weight > 0:
                name = '%s [%s]' % (name,weight)
            '''
            return (d['id'], name)

        result = []
        for attr in self.browse(cr, user, ids, context=context):
            mydict = {
                      'id': attr.id,
                      'name': attr.name,
                      'attribute_type': attr.attribute_type,
                      'standard_option_id': attr.standard_option_id,
#                      'price_standard': attr.price_standard,
#                      'weight_standard': attr.weight_standard
                      }
            result.append(_name_get(mydict))
        return result        
   
class attribute_option(orm.Model):
    _inherit = "attribute.option"
    _columns = {
        'price': fields.float('Price', digits_compute= dp.get_precision('Product Price')),
        'weight': fields.float('Weight(kg)', digits_compute=dp.get_precision('Product Unit of Measure')),
    }
    
    _sql_constraints = [
        ('name_attribute_uniq', 'unique (name, attribute_id)', 'The name of the option has to be unique for a given attribute !'),
    ]

    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []

        result = []
        for opt in self.browse(cr, user, ids, context=context):
            name = opt.name
            price_str = ''
            weight_str = ''
            if opt.price and opt.price != 0:
                price_str = '%s%s%s'%((opt.price > 0 and '+' or '-'),opt.attribute_id.currency_id.symbol,abs(opt.price))
            if opt.weight and opt.weight != 0:
                weight_str = '%s%skg'%((opt.weight > 0 and '+' or '-'),abs(opt.weight))
            
            if price_str != '' or weight_str != '':                    
                if weight_str != '':
                    weight_str = '%s%s'%((price_str != '') and "," or "",weight_str)
                name = '%s(%s%s)'%(name,price_str,weight_str)
            result.append((opt.id,name))
        return result
    
    '''
    #price_standard,weight_standard were removed, so the code below is useless
    def write(self, cr, user, ids, vals, context=None):
        resu = super(attribute_option, self).write(cr, user, ids, vals, context)
        if vals.has_key('price') or vals.has_key('weight'):
            #update the associated attribute stand price and weight
            attr_vals = {}
            if vals.has_key('price'):
                attr_vals.update({'price_standard': vals['price']})
            if vals.has_key('weight'):
                attr_vals.update({'weight_standard': vals['weight']})
            attr_obj = self.pool.get('attribute.attribute')
            for id in ids:
                attr_ids = attr_obj.search(cr, user, [('standard_option_id','=',id)],context=context)
                attr_obj.write(cr, user, attr_ids, attr_vals, context=context)
        return resu
    '''

       