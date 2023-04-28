# -*- coding: utf-8 -*-

import math
import time
from datetime import datetime
from openerp.report import report_sxw
from openerp.osv import fields, osv
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
'''
Added SXW PDF util methods
'''
class rml_parser_ext(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(rml_parser_ext, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'select_name': self.select_name,
            'float2time': self.float2time,
            'utc2local': self.utc2local,
            'ids2name': self.ids2name,
            
        })
    def obj_ids_name(self, obj_ids):
        obj_ids_name = [obj.name for obj in obj_ids]
        return ','.join(obj_ids_name)   
    #[[select_name('resource.calendar.attendance','dayofweek',line.p_weekday)]]  
    def select_name(self,model_name,field_name,field_value):
        field_sel = self.pool.get(model_name)._columns[field_name].selection
        trans_src = field_value;
        for sel_item in field_sel:
            if(sel_item[0] == field_value):
                trans_src = sel_item[1]
                break
        trans_obj = self.pool.get('ir.translation')
        trans_name = model_name + ',' + field_name
        trans_result = trans_obj._get_source(self.cr, self.uid, trans_name, 'selection', self.localcontext.get('lang'), trans_src)
        return trans_result
    #[[float2time(line.sign_in)]]
    def float2time(self,float_val,keep_zero=False):
        if float_val == 0.0 and not keep_zero:
            return ''
        hours = math.floor(abs(float_val))
        mins = abs(float_val) - hours
        mins = round(mins * 60)
        if mins >= 60.0:
            hours = hours + 1
            mins = 0.0
        float_time = '%02d:%02d' % (hours,mins)
        return float_time
    def utc2local(self,dt_utc_para):
        dt_utc = dt_utc_para
        if isinstance(dt_utc, (type(u' '), type(' '))):
            dt_utc = datetime.strptime(dt_utc_para,DEFAULT_SERVER_DATETIME_FORMAT)
        dt_local = fields.datetime.context_timestamp(self.cr, self.uid, dt_utc, self.localcontext)
        return dt_local
    #[[ids2name(rpt.emp_ids)]]
    def ids2name(self,obj_ids):
        obj_names = [obj.name for obj in obj_ids]
        return ', '.join(obj_names)
      
    #add the 'idx' field, can be used in the inner of repeatIn loop of rml
    def repeatIn(self, lst, name,nodes_parent=False):
        ret_lst = super(rml_parser_ext,self).repeatIn(lst, name,nodes_parent)
        i = 0
        for obj in ret_lst:
            i = i + 1
            obj.get(name).idx = i
        return ret_lst

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
