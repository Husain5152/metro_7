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

import time
from lxml import etree

from openerp.osv import fields, osv
from openerp.tools.translate import _
'''
Report base class, the sub class need todo:
1.Add the default value for the 'type' field
2.Add the search fields that the report need
3.Defined the view xml based on the new class
4.define method run_%type% to report the report line data
5.define _pdf_data() method to return the report name in xml
'''
class rpt_base(osv.osv_memory):
    _name = "rpt.base"
    _description = "Base Report"
    _columns = {
        'name': fields.char('Report Name', size=16, required=False),
        'title': fields.char('Report Title', required=False),
        'type': fields.char('Report Type', size=16, required=True),
        'company_id': fields.many2one('res.company','Company',required=True,),
        #report data lines
        'rpt_lines': fields.one2many('rpt.base.line', 'rpt_id', string='Report Lines'),               
        #show/hide search fields on GUI
        'show_search': fields.boolean('Show Searching', ),   
        #show/hide search result
        'show_result': fields.boolean('Show Result', ),
        #show/hide search result
        'save_pdf': fields.boolean('Can Save PDF', ),
        }
    
    _defaults = {
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.rptcn', context=c),
        'show_search': True,        
        'show_result': False,      
        'save_pdf': False,          
    }
    def default_get(self, cr, uid, fields_list, context=None):
        resu = super(rpt_base,self).default_get(cr, uid, fields_list, context)
        #set default title by i18n
        if context.get('default_title',False):
            resu['title'] = _(context.get('default_title'))        
        return resu    
    def run_report(self, cr, uid, ids, context=None):
        rpt = self.browse(cr, uid, ids, context=context)[0]
        rpt_method = getattr(self, 'run_%s'%(rpt.type,))
        #get report data
        rpt_line_obj,  rpt_lns = rpt_method(cr, uid, ids, context)
        #remove the old lines
        unlink_ids = rpt_line_obj.search(cr, uid, [('rpt_id','=',rpt.id)], context=context)
        rpt_line_obj.unlink(cr ,uid, unlink_ids, context=context)
        #create new lines
        for rpt_line in rpt_lns:
            rpt_line['rpt_id'] = rpt.id
            rpt_line_obj.create(cr ,uid, rpt_line, context=context)  
        #update GUI elements
        self.write(cr, uid, rpt.id, {'show_search':False,'show_result':True,'save_pdf':True},context=context)
        return True
    
    def _pdf_data(self, cr, uid, ids, form_data, context=None):
        raise (_('Error!'), _('Not implemented.'))
        
    def save_pdf(self, cr, uid, ids, context=None):
        if context is None: 
            context = {}
        form_data = self.read(cr, uid, ids[0], context=context)
        rptxml_name = self._pdf_data(cr, uid, ids[0], form_data, context=context)['xmlrpt_name']
        datas = {
                 'model': self._name,
                 'ids': [ids[0]],
                 'form': form_data,
        }
        return {'type': 'ir.actions.report.xml', 'report_name': rptxml_name, 'datas': datas, 'nodestroy': True}    
    
rpt_base()

class rpt_base_line(osv.osv_memory):
    _name = "rpt.base.line"
    _description = "Base report line"
    _order = 'seq'
    _columns = {
        'rpt_id': fields.many2one('rpt.base', 'Report'),
        'seq': fields.integer('Seq', ),
        'code': fields.char('Code', size=64, ),
        'name': fields.char('Name', size=256, ),
        'data_level': fields.char('Data level code', size=64)
        }

rpt_base_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
