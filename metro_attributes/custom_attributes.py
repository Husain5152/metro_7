# -*- encoding: utf-8 -*-
from osv import fields,osv,orm
import openerp.addons.decimal_precision as dp
from openerp.tools import resolve_attr 

from tools.translate import translate
from lxml import etree    
#from openerp.addons.base_custom_attributes import custom_attributes as custom_attr

class attribute_group(orm.Model):
    _inherit = "attribute.group"
    _columns = {
        #make the group title as translatable
        'name': fields.char('Name', size=128, required=True, translate=True),
        }

def _build_attribute_field(self, cr, uid, page, attribute, context=None):
    parent = etree.SubElement(page, 'group', colspan="2", col="4")
    kwargs = {'name': "%s" % attribute.name}
#    if attribute.ttype in ['many2many', 'text']:
    #only the many2many without many2many_tags then need display 'separator', by johnw 04/30/2014
    if (attribute.ttype == 'many2many' and not attribute.m2m_tags) or attribute.ttype == 'text':
        parent = etree.SubElement(parent, 'group', colspan="2", col="4")
        sep = etree.SubElement(parent,
                               'separator',
                                string="%s" % attribute.field_description,
                                colspan="4")

        kwargs['nolabel'] = "1"
    if attribute.ttype in ['many2one', 'many2many']:
        if attribute.relation_model_id:
            if attribute.domain:
                kwargs['domain'] = attribute.domain
            else:
                ids = [op.value_ref.id for op in attribute.option_ids]
                kwargs['domain'] = "[('id', 'in', %s)]" % ids
        else:
            kwargs['domain'] = "[('attribute_id', '=', %s)]" % attribute.attribute_id.id
    #set the 'many2many_tags' widget for the multiselect attribute, by johnw 04/30/2014
    if attribute.ttype == 'many2many' and attribute.m2m_tags:
        kwargs['widget'] = "many2many_tags"
    #Add the field's description as the field label
#    field = etree.SubElement(parent, 'field', **kwargs)    
    field = etree.SubElement(parent, 'field', string="%s" % attribute.field_description, **kwargs)
    orm.setup_modifiers(field, self.fields_get(cr, uid, attribute.name, context))
    return parent 

def _build_attributes_notebook(self, cr, uid, attribute_group_ids, context=None, notebook = None, attr_holder_name = None):
#    notebook = etree.Element('notebook', name="attributes_notebook", colspan="4")
    #begin by johnw 04/30/2014
    #add the logic to consider the existing notebook and the position in the notebook by attr_holder_name
    nb_pg_idx = 0
    if notebook is None:
        #if there is no notebook parameter, then create one new 
        notebook = etree.Element('notebook', name="attributes_notebook", colspan="4")
    else:
        #if insert into an existing notebook, then find the position need to insert by parameter: attr_holder_name
        if attr_holder_name is not None:            
            idx = 0
            for em in notebook.getchildren():
                if em.get('name','') ==  attr_holder_name:
                    nb_pg_idx = idx
                    break
                idx = idx + 1
    #end
    toupdate_fields = []
    grp_obj = self.pool.get('attribute.group')
    for group in grp_obj.browse(cr, uid, attribute_group_ids, context=context):
#        page = etree.SubElement(notebook, 'page', string=group.name.capitalize())
        #begin by johnw 04/30/2014, insert the page to the position by the parameter
        page = etree.Element('page', string=group.name.capitalize())
        notebook.insert(nb_pg_idx,page)
        #end        
        for attribute in group.attribute_ids:
            if attribute.name not in toupdate_fields:
                toupdate_fields.append(attribute.name)
                self._build_attribute_field(cr, uid, page, attribute, context=context)
    return notebook, toupdate_fields
#custom_attr.attribute_attribute._build_attribute_field =  _build_attribute_field
#custom_attr.attribute_attribute._build_attributes_notebook = _build_attributes_notebook          
