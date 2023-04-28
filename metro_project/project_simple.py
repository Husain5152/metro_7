# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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
from openerp.osv import fields,osv
from openerp.addons.base_status.base_stage import base_stage
from openerp.tools.translate import _
from openerp.addons.project import project as project_super
from openerp.addons.metro_purchase.purchase import deal_args
import threading
from openerp import pooler
from openerp.addons.metro import utils
    
_PROJ_TYPES = [('simple','Simple'),('software','Software'),('engineer','Engineering'),('gtd','GTD'),('mfg','Manufacture')]
import datetime

'''
1.Add 'type' field to extend the project's usage
2.Project can not be closed if there are opening tasks
3.When do creation, set the state list by project_type
'''
class project_project(osv.osv):
    _name = 'project.project'
    _inherit = 'project.project'
    _order = 'id desc'
    _columns = {
        'project_type': fields.selection(_PROJ_TYPES,string='Type',),
    }
    
    def _get_default_states(self, cr, uid, context):
        domain = []
        if context and context.has_key('default_project_type') and context['default_project_type']:
            domain += ['|',('project_type','=',context['default_project_type'])]
        domain +=  ['|',('project_type','=','all'),('case_default','=',1)]
        ids = self.pool.get('project.task.type').search(cr, uid, domain, context=context)
        return ids
    
    _defaults = {'project_type':'simple',
                 'type_ids': _get_default_states,
                 }
    
    #add the ID return in the name
    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        result = []
        for data in self.browse(cr, user, ids, context=context):
            if data.id <= 0:
                result.append((data.id,''))
                continue
            result.append((data.id,'[%s]%s'%(data.id,data.name)))
                          
        return result    
    
    def onchange_project_type(self,cr, uid, ids, project_type, context=None):
        if not project_type:
            return {}
        domain =  ['|','|',('project_type','=',project_type),('project_type','=','all'), ('case_default','=',1)]
        ids = self.pool.get('project.task.type').search(cr, uid, domain, context=context)
        return {'value':{'type_ids': ids}}
            
    def set_done(self, cr, uid, ids, context=None):        
        if isinstance(ids, (int,long)):
            ids = [ids]
        if context == None:
            context = {}
        #the BOM is required when do project done
        for proj in self.browse(cr, uid, ids, context=context):
            for task in proj.tasks:
                if task.state != 'done':
                    raise osv.except_osv(_('Error!'), _('Project "%s" can not be close, the task "%s" is opening.'%(proj.name,task.name)))
        resu = super(project_project,self).set_done(cr, uid, ids, context) 
        return resu
project_project()
'''
1.Sending email to the assignee when creating and writing
2.Imrpove the group by state, to add the 'project_type' domain to return all the states related to the project type
3.Add multi images
'''    
class project_task(base_stage, osv.osv):
    _inherit = "project.task"  
    _name = "project.task"      
    _order = "sequence, date_start, name, id"
    _columns = {
        'project_type': fields.related('project_id', 'project_type', type='selection', 
                                       selection=_PROJ_TYPES, 
                                       string='Project Type', readonly=True, store=True, select=1),
        'multi_images': fields.text("Multi Images"),
        'private': fields.boolean("Private"),     
        'emp_ids': fields.many2many("hr.employee","task_emp","task_id","emp_id",string="Employees"),
        'daily_date':fields.function(lambda *a,**k:{}, type='date',string="Daily Task Date",),
        'stage_color':fields.related('stage_id','color',type='integer'),
    }
    #add the ID return in the name
    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        result = []
        for data in self.browse(cr, user, ids, context=context):
            if data.id <= 0:
                result.append((data.id,''))
                continue
            result.append((data.id,'[%s]%s'%(data.id,data.name)))
                          
        return result
    '''     
    Replaced below code with code in project_simple_view.xml:
    ===========
                    <field name="daily_date" widget="calendar"
                        filter_domain="['|',('date_start','=',False),('date_start','&lt;=', self + ' 23:59:59'),'|',('date_end','=',False),('date_end','&gt;=', self + ' 00:00:00')]"/>
    ===========                       
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)
        idx_daily = 0
        args_daily = []
        for arg in new_args:
            #add the category improving
            if arg[0] == 'daily_date':
                args_daily = ['|',['date_start','=',False],['date_start','<=','%s %s'%(arg[2],'23:59:59')],'|',['date_end','=',False],['date_end','>=','%s %s'%(arg[2],'00:00:00')]]
                new_args.pop(idx_daily)
                new_args += args_daily
                break
            idx_daily += 1                           
        #get the search result        
        ids = super(project_task,self).search(cr, user, new_args, offset, limit, order, context, count)
        return ids 
    ''' 
            
    def default_get(self, cr, uid, fields_list, context=None):
        resu = super(project_task,self).default_get(cr, uid, fields_list, context=context)
        #only keep the default project setting for the simple project
#        if context.get('default_project_type') and context.get('default_project_type') != 'simple' and resu.get('project_id'):
#            resu.pop('project_id')
            
        if context.get('default_project_type') and not resu.get('project_id'):
            default_project_type = context.get('default_project_type')
            type_xmls = {'simple':'project_simple',
                         'gtd':'project_gtd',
                         'software':'project_software',
                         'mfg':'project_mfg',}
            proj_xml_id = type_xmls.get(default_project_type)
            if proj_xml_id:
                result = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_project', proj_xml_id)
                resu.update({'project_id':result[1]})
        return resu
    
    def create(self, cr, uid, vals, context=None):
        new_id = super(project_task,self).create(cr, uid, vals ,context)
        if self.browse(cr,uid,new_id,context=context).project_type != 'mfg':
            if 'user_id' in vals:
                email_vals = {'email_user_id':vals['user_id'],'email_template_name':'project_task_assignee'}
                utils.email_send_template(cr, uid, [new_id], email_vals, context)
#            self.email_send(cr, uid, [new_id],vals,context)
        return new_id
            
    def write(self, cr, uid, ids, vals, context=None):
        resu = super(project_task,self).write(cr, uid, ids, vals ,context)
        if 'user_id' in vals:
            email_vals = {'email_user_id':vals['user_id'],'email_template_name':'project_task_assignee'}
            utils.email_send_template(cr, uid, ids, email_vals, context)
#        self.email_send(cr, uid, ids,vals,context)
        return resu     
    def unlink(self, cr, uid, ids, context=None):
        if context == None:
            context = {}
        for task_state in self.read(cr, uid, ids, ['name','state','project_type']):
            if task_state['project_type'] != 'mfg' and task_state['state'] not in ('cancelled','draft'):
                raise osv.except_osv(_('Error!'), _('Task "%s" can not be delete, only task with Draft&Cancel states can be delete.'%(task_state['name'],)))
        res = super(project_task, self).unlink(cr, uid, ids, context)
        return res    
    def fields_get(self, cr, uid, allfields=None, context=None, write_access=True):
        resu = super(project_task,self).fields_get(cr, uid, allfields,context,write_access)
        #set  the 'project_id' domain dynamically by the default_project_type
        default_project_type = context and context.get('default_project_type', False) or False
        if resu.has_key('project_id') and default_project_type:            
            project_ids = self.pool.get('project.project').search(cr, uid, [('project_type','=',default_project_type)], context=context)
            resu['project_id']['domain'] = [('id','in',project_ids)]
        return resu 
         
    def _resolve_project_type_from_context(self, cr, uid, context=None):
        """ Returns the project_type from the type context
            key. Returns None if it cannot be resolved.
        """
        if context is None:
            context = {}
        return context.get('default_project_type')   
     
    def _read_group_stage_ids(self, cr, uid, ids, domain, read_group_order=None, access_rights_uid=None, context=None):
        stage_obj = self.pool.get('project.task.type')
        order = stage_obj._order
        access_rights_uid = access_rights_uid or uid
        if read_group_order == 'stage_id desc':
            order = '%s desc' % order
        search_domain = []
        project_id = self._resolve_project_id_from_context(cr, uid, context=context)
        if project_id:
            search_domain += ['|', ('project_ids', '=', project_id)]
        search_domain += [('id', 'in', ids)]
        # johnw, 07/22/2014, retrieve type from the context (if set: choose 'type' or 'both')
        #begin                
        project_type = self._resolve_project_type_from_context(cr, uid, context=context)
        if type:
            type_domain = ['|', ('project_type', '=', project_type), ('project_type', '=', 'all')]
            search_domain.insert(0, '|')
            search_domain += type_domain
        #end
        stage_ids = stage_obj._search(cr, uid, search_domain, order=order, access_rights_uid=access_rights_uid, context=context)
        result = stage_obj.name_get(cr, access_rights_uid, stage_ids, context=context)
        # restore order of the search
        result.sort(lambda x,y: cmp(stage_ids.index(x[0]), stage_ids.index(y[0])))
    
        fold = {}
        for stage in stage_obj.browse(cr, access_rights_uid, stage_ids, context=context):
            fold[stage.id] = stage.fold or False
        return result, fold  
    
    _group_by_full = {
        'stage_id': _read_group_stage_ids,
        'user_id': project_super.task._read_group_user_id,
    }     
#    _defaults = {
#        'date_start': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')         
#        }
project_task()
class project_task_type(osv.osv):
    _inherit = 'project.task.type'
    _columns = {
        'project_type': fields.selection(_PROJ_TYPES+[('all','All')],string='Type',),
        'color': fields.integer('Color Index'),
    }      
    _defaults={'project_type':'simple',
                    'color':0}
#    def name_get(self, cr, uid, ids, context=None):
#        if not ids:
#            return []
#        if isinstance(ids, (int, long)):
#                    ids = [ids]
#        reads = self.read(cr, uid, ids, ['name', 'project_type'], context=context)
#        res = []
#        for record in reads:
#            name = record['name']
#            if record['project_type']:
#                name +=  '[' + record['project_type'] + ']'
#            res.append((record['id'], name))
#        return res    
    def write(self, cr, user, ids, vals, context=None):
        resu = super(project_task_type,self).write(cr,user,ids,vals,context=context)
        return resu