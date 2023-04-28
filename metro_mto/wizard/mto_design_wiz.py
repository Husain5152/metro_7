# -*- encoding: utf-8 -*-
from osv import fields,osv,orm
from openerp.tools import resolve_attr 
from tools.translate import translate
from lxml import etree
import openerp.addons.decimal_precision as dp
import time
import random
import base64
from openerp import netsvc

class mto_design_wiz(osv.osv):
    _name = "mto.design.wiz"
    _inherits = {'ir.attachment': 'attachment_id'}
    _columns = {
        'design_tmpl_id': fields.many2one('attribute.set', 'Configuration Template', domain=[('type','=','design')], required=True, select=True),
        'design_id': fields.many2one('mto.design', 'Configuration'),        
        'create_uid': fields.many2one('res.users', 'Creator',readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True), 
        'attachment_id': fields.many2one('ir.attachment', 'Attachment', ondelete="cascade",),
        'store': fields.boolean('Store'),
    }
    _defaults={'name':lambda *args:'TMPCFGLOG_%s'%(str(random.random()*1000000).split('.')[0]),
               'type':'binary',
                    }
    def unlink(self, cr, uid, ids, context=None):
        attachment_ids = []
        #delete the related attachment data
        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.attachment_id:
                attachment_ids.append(wiz.attachment_id.id)
        if attachment_ids:
            self.pool.get('ir.attachment').unlink(cr, uid, attachment_ids, context=context)  
        return super(mto_design_wiz,self).unlink(cr, uid, ids, context=context)
    
    def act_config(self, cr, uid, ids, context=None): 
        this = self.browse(cr, uid, ids)[0]
        tmp_id = this.design_tmpl_id
        #create one product configuration to mto.design
        design_vals = {'name':'TMPCFG_%s'%(str(random.random()*1000000).split('.')[0],),
                       'list_price':tmp_id.price_standard,
                       'weight':tmp_id.weight_standard,
                       'design_tmpl_id':tmp_id.id,
                       'wiz_id':this.id,
                       #for the attachment
                       'type':'binary',}
        design_id = self.pool.get('mto.design').create(cr, uid, design_vals, context=context)
        #write the design if to self
        self.write(cr, uid, [this.id], {'design_id':design_id}, context=context)
        #show the configuration screen        
        ir_model_data_obj = self.pool.get('ir.model.data')
        ir_model_data_id = ir_model_data_obj.search(cr, uid, [['model', '=', 'ir.ui.view'], ['name', '=', 'mto_design_form_view_wiz']], context=context)
        if ir_model_data_id:
            res_id = ir_model_data_obj.read(cr, uid, ir_model_data_id, fields=['res_id'])[0]['res_id']
        grp_ids = self.pool.get('mto.design')._attr_grp_ids(cr, uid, [design_id], [], None, context)[design_id]
        ctx = context.copy()
        ctx.update({'open_attributes': True, 'attribute_group_ids': grp_ids, 'wizard':True})

        return {
            'name': 'Configuration',
            'type': 'ir.actions.act_window',
            'res_model': 'mto.design',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'res_id': design_id,
            'context': ctx,
            'nodestroy': True,
            'target': 'new',
        }
                

class mto_design(osv.osv):
    _inherit = "mto.design"
    _columns = {
        'wiz_id': fields.many2one('mto.design.wiz', 'Configuration Wizard'),
    }

    def update_log(self, cr, uid, ids, filename, filedata, context=None):        
        vals = {'store':True,
                    'datas_fname': filename,
                    'datas': filedata,
                    'res_model': 'mto.design.wiz',
                    'res_id': ids[0],
                    'name':'CFGLOG_%s'%(ids[0],)
                }
        return self.pool.get('mto.design.wiz').write(cr, uid, ids, vals, context=context)
    
    def unlink_log(self, cr, uid, ids, context=None):
        return self.pool.get('mto.design.wiz').unlink(cr, uid, ids, context=context)  
      
    def update_design(self, cr, uid, ids, context=None):
        vals = {'name': 'CFGWIZ_%s'%(ids[0],)}
        return self.write(cr, uid, ids, vals, context=context)
    
    def unlink_design(self, cr, uid, ids, context=None):
        return self.unlink(cr, uid, ids, context=context)
        
    def create_pdf(self, cr, uid, design, context=None):
        report_service = 'report.mto.design.print'
        service = netsvc.LocalService(report_service)
        (result, format) = service.create(cr, uid, [design.id], {'model': 'mto.design'}, context)
        result = base64.b64encode(result)
        report_name = 'ProductionConfiguration_%s.pdf'%(design.name)
        
        return report_name, result
        
    def act_pdf_only(self, cr, uid, ids, context=None):
        design = self.browse(cr, uid, ids[0], context=context)
        #generate a PDF file based on the design        
        filename, filedata = self.create_pdf(cr, uid, design, context)
        #delete the wiz log
        self.unlink_log(cr, uid, [design.wiz_id.id], context)
        #delete the design data
        self.unlink_design(cr, uid, ids, context)
        #go to the file download page
        return self.pool.get('file.down').download_data(cr, uid, filename, filedata, context)

    def act_pdf_log(self, cr, uid, ids, context=None):
        design = self.browse(cr, uid, ids[0], context=context) 
        #generate a PDF file based on the design        
        filename, filedata = self.create_pdf(cr, uid, design, context)        
        #update the wiz log
        self.update_log(cr, uid, [design.wiz_id.id], filename, filedata, context)
        #delete the design data
        self.unlink_design(cr, uid, ids, context)
        #go to the file download page
        return self.pool.get('file.down').download_data(cr, uid, filename, filedata, context)
    
    def act_pdf_configuration(self, cr, uid, ids, context=None): 
        design = self.browse(cr, uid, ids[0], context=context)
        #delete the wiz log
        self.unlink_log(cr, uid, [design.wiz_id.id], context)
        #update the design data
        self.update_design(cr, uid, ids, context=context)
        #generate a PDF file based on the design        
        filename, filedata = self.create_pdf(cr, uid, design, context)
        #go to the file download page
        return self.pool.get('file.down').download_data(cr, uid, filename, filedata, context)
    
    def act_pdf_log_configuration(self, cr, uid, ids, context=None): 
        design = self.browse(cr, uid, ids[0], context=context)
        #update the design data
        self.update_design(cr, uid, ids, context=context)
        #generate a PDF file based on the design        
        filename, filedata = self.create_pdf(cr, uid, design, context)
        #update the wiz log
        self.update_log(cr, uid, [design.wiz_id.id], filename, filedata, context)
        #go to the file download page
        return self.pool.get('file.down').download_data(cr, uid, filename, filedata, context)
    
    def act_cancel(self, cr, uid, ids, context=None): 
        design = self.browse(cr, uid, ids[0], context=context)
        #delete the wiz log
        self.unlink_log(cr, uid, [design.wiz_id.id], context)
        #delete the design data
        self.unlink_design(cr, uid, ids, context=context)
        
        return {'type': 'ir.actions.act_window_close'}                
                