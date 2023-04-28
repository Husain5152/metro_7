#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    d$
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

import time
from datetime import date
from datetime import datetime
from datetime import timedelta
from dateutil import relativedelta
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT

from openerp import netsvc
from openerp.osv import fields, osv
from openerp import tools
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

from openerp.tools.safe_eval import safe_eval as eval

# TODO: HoangTK move this value to a setting
SICK_PAY_PER_DAY = 58.08

class hr_emppay_alwded(osv.osv):
    """
    Salary allowance and the deduction
    """

    _name = 'hr.emppay.alwded'
    _description = 'Salary allowance and the deduction'
    _order = 'type, sequence'
    
    def _alwded_field_get(self, cr, uid, context=None):
        mf = self.pool.get('ir.model.fields')
        ids = mf.search(cr, uid, [('model','=', 'hr.rpt.attend.month.line'), ('ttype','=','float'), '|', ('name','like','alw_%'), ('name','like','ded_%')], context=context)
        res = []
        for field in mf.browse(cr, uid, ids, context=context):
            res.append((field.name, field.field_description))
        return res
    
    _columns = {
        'sequence': fields.integer('#', required=True),
        'code':fields.char('Code', size=64, required=True, select=True),
        'name':fields.char('Name', size=256, required=True),
        'type':fields.selection([('alw','Allowance'),('ded','Deduction'),('alw_inwage','Allowance In Wage')], string='Type', required=True ),
        'type_calc':fields.selection([('fixed','Fixed'),('by_attend','By Attendance')], string='Calculation Type', required=True ),
        'amount':fields.float('Amount', digits_compute=dp.get_precision('Payroll'), required=True),
        'company_id':fields.many2one('res.company', 'Company', required=True),
        #fields related to hr_rpt_attend_month_line
        "attend_field" : fields.selection(_alwded_field_get, "Attend Field", size=32, help="Associated field in the attendance report."),
    }
    
    _defaults={
               'type_calc':'fixed',
               'company_id':lambda self, cr, uid, context: self.pool.get('res.users').browse(cr, uid, uid,context=context).company_id.id,
               }
    _sql_constraints = [
        ('code_uniq', 'unique(code, type)', 'Name must be unique per Type!'),
    ]
    
    def write(self, cr, user, ids, vals, context=None):
        resu = super(hr_emppay_alwded, self).write(cr, user, ids, vals, context=context)
        '''
        Auto update the hr.contract.alwded data having same with current old data
        '''        
        #check if there are data that need sync to hr contract
        field_names = ['sequence', 'type', 'type_calc', 'amount', 'attend_field']
        field_names_deal = []
        for field_name in field_names:
            if field_name in vals:
                field_names_deal.append(field_name)
        #sync data to contract
        if field_names_deal:            
            contract_alwded_obj = self.pool.get('hr.contract.alwded')
            #field values will be update
            field_vals_upt = {}            
            for field_name in field_names_deal:
                field_vals_upt[field_name] = vals[field_name]
            #loop to update the data
            for id in ids:
                #old field values
                old_vals = self.read(cr, user, id, field_names_deal, context=context)
                #only the contract data that same with the alwded's old data will be update, if user changed the contract data, then do not update them automatically 
                field_names_domain = [('alwded_id', '=', id)]
                for field_name in field_names_deal:
                    field_names_domain.append((field_name, '=', old_vals[field_name]))
                upt_contract_alwded_ids = contract_alwded_obj.search(cr, user, field_names_domain, context=context)
                #do update
                if upt_contract_alwded_ids:
                    contract_alwded_obj.write(cr, user, upt_contract_alwded_ids,  field_vals_upt, context=context)
        
        return resu

class hr_contract_alwded(osv.osv):
    """
    Contract's Salary allowance and the deduction
    """
    _name = 'hr.contract.alwded'
    _description = 'Contact Salary''s allowance and the deduction'
    _order = 'type, sequence'
            
    def _alwded_field_get(self, cr, uid, context=None):
        mf = self.pool.get('ir.model.fields')
        ids = mf.search(cr, uid, [('model','=', 'hr.rpt.attend.month.line'), ('ttype','=','float'), '|', ('name','like','alw_%'), ('name','like','ded_%')], context=context)
        res = []
        for field in mf.browse(cr, uid, ids, context=context):
            res.append((field.name, field.field_description))
        return res
    
    _columns = {
        'contract_id': fields.many2one('hr.contract', 'Contract', select=True, ondelete='cascade'),
        'alwded_id': fields.many2one('hr.emppay.alwded', 'Allowance/Deduction', required=True),
        'sequence': fields.integer('#', required=True),
        'type':fields.selection([('alw','Allowance'),('ded','Deduction'),('alw_inwage','Allowance In Wage')], string='Type', required=True ),
        'type_calc':fields.selection([('fixed','Fixed'),('by_attend','By Attendance')], string='Calculation Type', required=True ),
        'amount':fields.float('Amount', digits_compute=dp.get_precision('Payroll'), required=True),
        #fields related to hr_rpt_attend_month_line
        "attend_field" : fields.selection(_alwded_field_get, "Attend Field", size=32, help="Associated field in the attendance report."),
                
    }
    
    _defaults={
               'type_calc':'fixed',
               }
    def onchange_alwded_id(self, cr, uid, ids, alwded_id, context=None):
        alwded = self.pool.get('hr.emppay.alwded').browse(cr, uid, alwded_id, context=context)
        vals = {'sequence':alwded.sequence, 'type':alwded.type, 'type_calc':alwded.type_calc, 'amount':alwded.amount, 'attend_field':alwded.attend_field}
        return {'value':vals}
        
class hr_emppay_si(osv.osv):
    """
    Salary Social Insurance
    """
    _name = 'hr.emppay.si'
    _description = 'Salary Social Insurance'
    def _amount_all(self, cr, uid, ids, field_names, args, context=None):
        res = dict((id,dict((field_name,None) for field_name in field_names)) for id in ids)
        for si in self.browse(cr, uid, ids, context=context):
            if 'amount_company' in field_names:
                res[si.id]['amount_company'] = si.amount_base * si.rate_company/100.00
            if 'amount_personal' in field_names:
                res[si.id]['amount_personal'] = si.amount_base * si.rate_personal/100.00
        return res
    
    _columns = {
        'sequence': fields.integer('#', required=True, select=True),
        'code':fields.char('Code', size=64, required=True),
        'name':fields.char('Name', size=256, required=True),
        'amount_base':fields.float('Base Amount', digits_compute=dp.get_precision('Payroll'), required=True),
        'rate_company':fields.float('Company Rate', digits_compute=dp.get_precision('Payroll'), required=True),
        'rate_personal':fields.float('Personal Rate', digits_compute=dp.get_precision('Payroll'), required=True),
        'amount_company':fields.function(_amount_all, string='Company Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_all"),
        'amount_personal':fields.function(_amount_all, string='Personal Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_all"),
        'company_id':fields.many2one('res.company', 'Company', required=True),
    }
    
    _defaults={
               'company_id':lambda self, cr, uid, context: self.pool.get('res.users').browse(cr, uid, uid,context=context).company_id.id,
               }    


    def write(self, cr, user, ids, vals, context=None):
        resu = super(hr_emppay_si, self).write(cr, user, ids, vals, context=context)
        '''
        Auto update the hr.contract.si data having same with current old data
        '''
        #check if there are data that need sync to hr contract
        field_names = ['sequence', 'amount_base', 'rate_company', 'rate_personal']
        field_names_deal = []
        for field_name in field_names:
            if field_name in vals:
                field_names_deal.append(field_name)
        #sync data to contract
        if field_names_deal:            
            contract_si_obj = self.pool.get('hr.contract.si')
            #field values will be update
            field_vals_upt = {}            
            for field_name in field_names_deal:
                field_vals_upt[field_name] = vals[field_name]
            #loop to update the data
            for id in ids:
                #old field values
                old_vals = self.read(cr, user, id, field_names_deal, context=context)
                #only the contract data that same with the alwded's old data will be update, if user changed the contract data, then do not update them automatically 
                field_names_domain = [('alwded_id', '=', id)]
                for field_name in field_names_deal:
                    field_names_domain.append((field_name, '=', old_vals[field_name]))
                upt_contract_alwded_ids = contract_si_obj.search(cr, user, field_names_domain, context=context)
                #do update
                if upt_contract_alwded_ids:
                    contract_si_obj.write(cr, user, upt_contract_alwded_ids,  field_vals_upt, context=context)
        
        return resu
    
class hr_contract_si(osv.osv):
    """
    Contract's Salary Social Insurance
    """
    _name = 'hr.contract.si'
    _description = 'Contact''s Salary Social Insurance'
    def _amount_all(self, cr, uid, ids, field_names, args, context=None):
        res = dict((id,dict((field_name,None) for field_name in field_names)) for id in ids)
        for si in self.browse(cr, uid, ids, context=context):
            if 'amount_company' in field_names:
                res[si.id]['amount_company'] = si.amount_base * si.rate_company/100.00
            if 'amount_personal' in field_names:
                res[si.id]['amount_personal'] = si.amount_base * si.rate_personal/100.00
        return res    
    
    _order = 'sequence'
    
    _columns = {
        'contract_id': fields.many2one('hr.contract', 'Contract', select=True, ondelete='cascade'),
        'si_id': fields.many2one('hr.emppay.si', 'Social Insurance', required=True),
        'sequence': fields.related('si_id', 'sequence', type='integer', string='#', store=True, readonly=True),
        #default get from hr_salary_si, user can change
        'amount_base':fields.float('Base Amount', digits_compute=dp.get_precision('Payroll'), required=True),
        'rate_company':fields.float('Company Rate', digits_compute=dp.get_precision('Payroll'), required=True),
        'rate_personal':fields.float('Personal Rate', digits_compute=dp.get_precision('Payroll'), required=True),
        'amount_company':fields.function(_amount_all, string='Company Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_all"),
        'amount_personal':fields.function(_amount_all, string='Personal Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_all"),
    }
    def onchange_si_id(self, cr, uid, ids, si_id, context=None):
        si = self.pool.get('hr.emppay.si').browse(cr, uid, si_id, context=context)
        vals = {'sequence':si.sequence, 
                'amount_base':si.amount_base, 
                'rate_company':si.rate_company, 
                'rate_personal':si.rate_personal,
                'amount_company':si.amount_company, 
                'amount_personal':si.amount_personal}
        return {'value':vals}
    
class hr_contract(osv.osv):
    _inherit = 'hr.contract'
    
    def _amount_si(self, cr, uid, ids, field_names, args, context=None):
        res = dict((id,dict((field_name,None) for field_name in field_names)) for id in ids)
        for contract in self.browse(cr, uid, ids, context=context):
            #for ths SI data
            si_total_company = 0.0
            si_total_personal = 0.0
            for si in contract.si_ids:
                si_total_company += si.amount_company
                si_total_personal += si.amount_personal
            if 'si_total_company' in field_names:
                res[contract.id]['si_total_company'] = si_total_company
            if 'si_total_personal' in field_names:
                res[contract.id]['si_total_personal'] = si_total_personal
        return res
            
    def si_dict(self, cr, uid, contract_id, context=None):
        lines = []
        if not contract_id:
            return lines
        contract = self.browse(cr, uid, contract_id, context=context)
        for item in contract.si_ids:
            line = {'sequence':item.sequence,
                    'code':item.si_id.code,
                    'name':item.si_id.name,
                    
                    'amount_base':item.amount_base,
                    'rate_company':item.rate_company,
                    'rate_personal':item.rate_personal,
                    'amount_company':item.amount_company,
                    'amount_personal':item.amount_personal,
                    }
            lines.append(line)
        return lines 
        
    _OTPAY_SEL = [('wage', 'Wage'),('wage2', 'Basic Wage'),('fixed', 'Fixed Amount')]
    

    '''
        加班小时工资设置:
        正常加班小时工资: 默认-按实际工资(正常工资/应出勤天数/8), 倍数1
        周末加班小时工资: 默认-按实际工资(正常工资/应出勤天数/8), 倍数1
        节假日加班小时工资: 默认-按实际工资(正常工资/应出勤天数/8), 倍数1
        5天制正常加班小时工资: 默认-按基本工资(基本工资/应出勤天数/8), 倍数1
        5天制周末加班小时工资: 默认-按基本工资(基本工资/应出勤天数/8), 倍数2
        5天制节假日加班小时工资: 默认-按基本工资(基本工资/应出勤天数/8), 倍数3
        可设置选项:
        按实际工资(正常工资/应出勤天数/8), 倍数
        按基本工资(基本工资/应出勤天数/8), 倍数
        按固定金额,金额
    '''    
    _columns = {
        'alwded_ids': fields.one2many('hr.contract.alwded', 'contract_id', 'Allowance&Deduction'),
        'si_ids': fields.one2many('hr.contract.si', 'contract_id', 'Social Insurance'),
        'si_total_company':fields.function(_amount_si, string='Company Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_si"),
        'si_total_personal':fields.function(_amount_si, string='Personal Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_si"),
        
        'wage2':fields.float('Wage2', digits_compute=dp.get_precision('Payroll')),
        'have_pit':fields.boolean('Have PIT'),
        'pit_base':fields.float('PIT Start Point', digits_compute=dp.get_precision('Payroll')),
        
        #OT pay setting
        'ot_pay_normal':fields.selection(_OTPAY_SEL,'Normal OT Pay'),
        'ot_pay_normal_multi':fields.float('Multiple', digits_compute=dp.get_precision('Payroll')),
                
        'ot_pay_weekend':fields.selection(_OTPAY_SEL,'Weekend OT Pay'),
        'ot_pay_weekend_multi':fields.float('Multiple', digits_compute=dp.get_precision('Payroll')),
        
        'ot_pay_holiday':fields.selection(_OTPAY_SEL,'Holiday OT Pay'),
        'ot_pay_holiday_multi':fields.float('Multiple', digits_compute=dp.get_precision('Payroll')),
        
        'ot_pay_normal2':fields.selection(_OTPAY_SEL,'Normal OT Pay by five days'),
        'ot_pay_normal2_multi':fields.float('Multiple', digits_compute=dp.get_precision('Payroll')),
        
        'ot_pay_weekend2':fields.selection(_OTPAY_SEL,'Weekend OT Pay by five days'),
        'ot_pay_weekend2_multi':fields.float('Multiple', digits_compute=dp.get_precision('Payroll')),
        
        'ot_pay_holiday2':fields.selection(_OTPAY_SEL,'Holiday OT Pay by five days'),
        'ot_pay_holiday2_multi':fields.float('Multiple', digits_compute=dp.get_precision('Payroll')),
    }
        
    _defaults={
        'have_pit':True,
        
        'ot_pay_normal': 'wage',
        'ot_pay_normal_multi': 1,
        'ot_pay_weekend': 'wage',
        'ot_pay_weekend_multi': 2,
        'ot_pay_holiday': 'wage',
        'ot_pay_holiday_multi': 3,
        
        'ot_pay_normal2': 'wage2',
        'ot_pay_normal2_multi': 1.5,
        'ot_pay_weekend2': 'wage2',
        'ot_pay_weekend2_multi': 2,
        'ot_pay_holiday2': 'wage2',
        'ot_pay_holiday2_multi': 3,               
        }
        
            
    def default_get(self, cr, uid, fields_list, context=None):
        defaults = super(hr_contract, self).default_get(cr, uid, fields_list, context=context)
        user_comp = self.pool.get('res.users').browse(cr, uid, uid,context=context).company_id
        defaults.update({'wage2':user_comp.emppay_wage2, 'pit_base':user_comp.emppay_pit_base})
        return defaults
        
    def get_emp_contract(self, cr, uid, employee_id, date_from, date_to, context=None):
        """
        @param employee: browse record of employee
        @param date_from: date field
        @param date_to: date field
        @return: returns the ids of all the contracts for the given employee that need to be considered for the given dates
        """
        contract_obj = self.pool.get('hr.contract')
        #a contract is valid if it ends between the given dates
        clause_1 = ['&',('date_end', '<=', date_to),('date_end','>=', date_from)]
        #OR if it starts between the given dates
        clause_2 = ['&',('date_start', '<=', date_to),('date_start','>=', date_from)]
        #OR if it starts before the date_from and finish after the date_end (or never finish)
        clause_3 = [('date_start','<=', date_from),'|',('date_end', '=', False),('date_end','>=', date_to)]
        clause_final =  [('employee_id', '=', employee_id),'|','|'] + clause_1 + clause_2 + clause_3
        contract_ids = contract_obj.search(cr, uid, clause_final, context=context)
        return contract_ids    
    
class res_company(osv.osv):
    _inherit = "res.company"
    _columns = {
        'emppay_wage2':fields.float('Wage2', digits_compute=dp.get_precision('Payroll')),
        'emppay_pit_base':fields.float('PIT Start Point', digits_compute=dp.get_precision('Payroll')),
        'emppay_pit_formula':fields.char('PIT Formula', size=128),
    }
    _defaults={'emppay_pit_base':3500,
                    'emppay_pit_formula':'[(0.03, 0), (0.1, 105), (0.2, 555), (0.25, 1005), (0.3, 2755), (0.35, 5505), (0.45, 13505)]'}

class hr_rpt_attend_month(osv.osv):
    _inherit = 'hr.rpt.attend.month'
    _columns = {
        'emppay_sheet_ids': fields.one2many('hr.emppay.sheet', 'attend_month_id', string='Payroll', readonly=True),
    }
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default['emppay_sheet_ids'] = None
        return super(hr_rpt_attend_month, self).copy(cr, uid, id, default, context)
    
    def wkf_done(self, cr, uid, ids, context=None):        
        resu = super(hr_rpt_attend_month,self).wkf_done(cr, uid, ids, context=context)
        for attend_id in ids:
            self.new_payroll(cr, uid, attend_id, context=None)
        return resu
        
    def wkf_cancel(self, cr, uid, ids, context=None):
        for rpt in self.browse(cr, uid, ids, context=context):
            if rpt.emppay_sheet_ids:
                for emppay_sheet in rpt.emppay_sheet_ids:
                    if emppay_sheet.state != 'cancel':
                        raise osv.except_osv(_('Error!'),_('There are related payrolls, please cancel or delete them first!'))
        return super(hr_rpt_attend_month, self).wkf_cancel(cr, uid, ids, context=context)
    
    #view monthly report
    def view_payroll(self, cr, uid, ids, context=None):
        rpt_id = ids[0]
        #read daily report data, create new monthly report based on it.
        rpt = self.read(cr, uid, rpt_id, ['emppay_sheet_ids'], context=context)
        payroll_ids = rpt['emppay_sheet_ids']
        if not payroll_ids:
            raise osv.except_osv(_('Error!'),_('No payroll generated!'))
        if len(payroll_ids) > 1:
            #got to list page
            act_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_hr', 'action_hr_emppay_sheet')
            act_id = act_id and act_id[1] or False            
            act_win = self.pool.get('ir.actions.act_window').read(cr, uid, act_id, [], context=context)
            act_win['context'] = {'search_default_attend_month_id': rpt['id']}
            return act_win
        else:
            #go to form page
            form_view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'metro_hr', 'hr_emppay_sheet_form')
            form_view_id = form_view and form_view[1] or False
            return {
                'name': _('Payroll'),
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [form_view_id],
                'res_model': 'hr.emppay.sheet',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': payroll_ids[0],
            }
                    
    #generate a new payroll
    def new_payroll(self, cr, uid, attend_id, context=None):
        payroll_data = self._payroll_data(cr, uid, attend_id, context=context)
        payroll_obj = self.pool.get('hr.emppay.sheet')
        #convert to the format for one2many to save by dict
        emppay_ids = [(0,0,slip) for slip in payroll_data['emppay_ids']]
        payroll_data['emppay_ids'] = emppay_ids
        payroll_id = payroll_obj.create(cr, uid, payroll_data, context=context)
        return payroll_id
    
    #add data to exist payroll
    def add_payroll(self, cr, uid, attend_id, payroll_id, remove_old_slips = False, context=None):
        payroll_data = self._payroll_data(cr, uid, attend_id, context=context)
        payroll_obj = self.pool.get('hr.emppay.sheet')
        #remove slips data
        if remove_old_slips:
            payslip_obj = self.pool.get('hr.emppay')
            unlink_ids = payslip_obj.search(cr, uid, [('emppay_sheet_id','=',payroll_id)], context=context)
            payslip_obj.unlink(cr ,uid, unlink_ids, context=context)
        #convert to the format for one2many to save by dict
        emppay_ids = [(0,0,slip) for slip in payroll_data['emppay_ids']]
        payroll_data['emppay_ids'] = emppay_ids
        payroll_obj.write(cr, uid, [payroll_id], payroll_data, context=context)
        return True
        
    def _payroll_data(self, cr, uid, attend_id, payroll_id = False, context=None):
        if isinstance(attend_id, list):
            attend_id = attend_id[0]
        attend = self.browse(cr, uid, attend_id, context=context)
        date_from = fields.datetime.context_timestamp(cr, uid, datetime.strptime(attend.date_from,DEFAULT_SERVER_DATETIME_FORMAT), context=context)
        date_to = fields.datetime.context_timestamp(cr, uid, datetime.strptime(attend.date_to,DEFAULT_SERVER_DATETIME_FORMAT), context=context)
        #payroll data
        emppay_sheet = {'attend_month_id':attend.id,
                            'date_from':date_from, 
                            'date_to':date_to}
        #payslips
        slips = []
        contract_obj = self.pool.get('hr.contract')
        #loop to add slip lines
        for attend_line in attend.rpt_lines:
            emp_id = attend_line.emp_id.id
            contract_ids = contract_obj.get_emp_contract(cr, uid, emp_id, attend.date_from, attend.date_to, context=context)
            if not contract_ids:
                raise osv.except_osv(_('Error!'), _('Generate payroll failed, no validate contracts were found for employee %s, please set contract and try again!')%(attend_line.emp_id.name))
                continue
            contract_id = contract_ids[0]
            contract = contract_obj.browse(cr, uid, contract_id, context=context)
            slip_alws, slip_deds, slip_alws_inwage = self.emp_attend_alwded(cr, uid, attend_line, contract=contract, calc_method='base_attend', context=context)
            slip_sis = contract_obj.si_dict(cr, uid, contract_id, context=context)
            slip = {'attend_id':attend_line.id,
                    'employee_id': emp_id,
                    'contract_id': contract.id,
                    #HoangTK : Add default value for house fund
                    'house_rent_fund': contract.house_rent_fund,
                    'company_house_rent_fund': contract.company_house_rent_fund,
                    'date_from': date_from,
                    'date_to': date_to,
#                    18:22 wage/wage2 are changed to float already, do not use related fields now
#                    17:30 wage/wage2 are related fields with store=True, others are changed to store=False
#                    for the related fields with store=True, we need assign the value when creating by code,
#                    otherwise if the next code in same DB transaction can not get the data by browse(...),
#                    On this sample is the hr_emppay._wage_all() method can not get the wage/wage2 data
                    'wage':contract.wage,
                    'wage2':contract.wage2,
                    #the allowance, deduction and sodical insurance
                    'alw_ids': [(0,0,item) for item in slip_alws],
                    'alw_inwage_ids': [(0,0,item) for item in slip_alws_inwage],
                    'ded_ids': [(0,0,item) for item in slip_deds],
                    'si_ids': [(0,0,item) for item in slip_sis],
                    
                    #Below fields are related fields without store=False, so no need to assign, no the issue with wage/wage2 above
                    #Below from attend data, user can not change, 数据为只读
#                    'days_work': attend_line.days_work,
#                    'days_attend': attend_line.days_attend,
#                    'hours_ot': attend_line.hours_ot,
#                    'hours_ot_we': 0,
#                    'hours_ot_holiday': 0,
                    #下面相关字段的显示使用组来限制
#                    'days_work2': attend_line.days_work2,
#                    'days_attend2': attend_line.days_attend2,
#                    'hours_ot2': attend_line.hours_ot2_nonwe,
#                    'hours_ot_we2': attend_line.hours_ot2_we,
#                    'hours_ot_holiday2': 0
                    }
            slips.append(slip)
        #set slips and return
        emppay_sheet['emppay_ids'] = slips
        return emppay_sheet
    
    def emp_attend_alwded(self, cr, uid, attend_line, contract=None, calc_method='calculate', context=None):
        '''
        Get employee allowance/deduction list by attendance and contract
        @param attend_line: attendance data of hr_rpt_attend_month_line, emp_attend_alwded() will use it to calculate the amount of 'by_attendance' alw/ded
        @param contract: employee contract instance of  hr.contract
        @param calc_method: the data getting direction, defaulr is 'to_attend'
            calculate: calcuate the amount based on alw/ded's 'type_calc' and attended days
            base_attend: update the amount based on attend_line's alw/ded fields and alw/ded item's  attend_field
        @return: one list containing three list: lines_alw, lines_ded, lines_alw_inwage
        '''
        lines_alw = []
        lines_deb = []
        lines_alw_inwage = []
        emp_id = attend_line.emp_id.id
        #get employee contract
        if not contract:
            contract_obj = self.pool.get('hr.contract')        
            contract_ids = contract_obj.get_emp_contract(cr, uid, emp_id, attend_line.rpt_id.date_from, attend_line.rpt_id.date_to, context=context)
            if not contract_ids:
                return lines_alw, lines_deb, lines_alw_inwage
            contract_id = contract_ids[0]
            contract = contract_obj.browse(cr, uid, contract_id, context=context)
        #get allowance and deductions from contract
        for item in contract.alwded_ids:
            line = {'sequence':item.sequence,
                    'code':item.alwded_id.code,
                    'name':item.alwded_id.name,
                    'type':item.type,
                    'type_calc':item.type_calc,
                    'amount':item.amount,
                    'attend_field':item.attend_field}            
            if not item.attend_field  \
                or calc_method == 'calculate' \
                or (calc_method == 'base_attend' and not hasattr(attend_line, item.attend_field)):
                if item.type_calc == 'by_attend':                
                    #do the amount calculation by attendance
                    if attend_line.days_work != 0:
                        if  item.type == 'alw_inwage':
                            line['amount'] = item['amount']*attend_line.days_attend2_real/attend_line.days_work2
                        else:
                            line['amount'] = item['amount']*attend_line.days_attend/attend_line.days_work
                    else:
                        line['amount'] = 0
                else:
                    line['amount'] = item.amount
            else:
                #calc_method is  'base_attend', and attendance has the field from 'attend_field' value
                line['amount'] = getattr(attend_line, item.attend_field)                
                #the alwded's currency is not local currency, need convert the local amount on attend line to the foreign currency
                line['currency_id'] = item.currency_id and item.currency_id.id or None
                if item.currency_id and item.currency_id.id != attend_line.rpt_id.company_id.currency_id.id:
                    line['amount_local'] = line['amount']
                    line['amount'] = self.pool.get('res.currency').compute(cr, uid, attend_line.rpt_id.company_id.currency_id.id, item.currency_id.id, line['amount'], context=context)                
                
            if item.type == 'alw':
                lines_alw.append(line)
            elif item.type == 'ded':
                lines_deb.append(line)
            elif item.type == 'alw_inwage':
                lines_alw_inwage.append(line)
        return lines_alw, lines_deb, lines_alw_inwage
    
    def emp_attend_alwded_by_field(self, cr, uid, attend_line, attend_fields, context=None):
        '''
        Get employee allowance/deduction value by attendance
        @param attend_line: attendance data of hr_rpt_attend_month_line, emp_attend_alwded() will use it to calculate the amount of 'by_attendance' alw/ded
        @param attend_fields: a field name list of table  hr_rpt_attend_month_line
        @return: one dict field values list: {filed_name1:value1, filed_name2:value2...}
        '''
        field_values = dict.fromkeys(attend_fields, 0)
        lines_alw, lines_deb, lines_alw_inwage = self.emp_attend_alwded(cr, uid, attend_line, context=context)
        lines_alwded = lines_alw + lines_deb + lines_alw_inwage
        for alwded in lines_alwded:
            field_name = alwded['attend_field']
            if field_name and field_name in attend_fields:
                field_values[field_name] = alwded['amount']
        return field_values
                    
class hr_emppay_sheet(osv.osv):
    _name = 'hr.emppay.sheet'
    _description = 'Payroll'
    _inherit = ['mail.thread']
    _order = 'id desc'
    
    def _wage_all(self, cr, uid, ids, field_names, arg, context=None):
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = dict.fromkeys(field_names,0.0)
            for line in order.emppay_ids:
                for field_name in field_names:
                    res[order.id][field_name] += getattr(line,field_name)            
        return res
    
    def _get_sheet(self, cr, uid, ids, context=None):
        keys = []
        for line in self.pool.get('hr.emppay').browse(cr, uid, ids, context=context):
            if line.emppay_sheet_id and line.emppay_sheet_id.id not in keys:
                keys.append(line.emppay_sheet_id.id)
        return keys
        
    _columns = {
        'name': fields.char('Name', size=64, required=False, readonly=True, states={'draft': [('readonly', False)]}),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('verified', 'Verified'),
            ('approved', 'Approved'),
            ('paid', 'Paid'),
        ], 'Status', select=True, readonly=True, track_visibility='onchange'),
        'date_from': fields.date('Date From', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date_to': fields.date('Date To', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'emppay_ids': fields.one2many('hr.emppay', 'emppay_sheet_id', 'Payslips', required=False, readonly=True, states={'draft': [('readonly', False)]}),
        'attend_month_id': fields.many2one('hr.rpt.attend.month', 'Attendance Report'),
        'note': fields.text('Description', readonly=True, states={'draft':[('readonly',False)]}),
        'company_id': fields.many2one('res.company', 'Company', required=False, readonly=True, states={'draft': [('readonly', False)]}),
        'account_period_id': fields.many2one('account.period', string='Account Period', readonly=True, states={'draft': [('readonly', False)]}, required=True),
        #total amount
        'wage_work': fields.function(_wage_all, digits_compute= dp.get_precision('Payroll'), string='Work Wage',
            store={
                'hr.emppay': (_get_sheet, None, 10),
            }, multi="sums", readonly=1),
        'alw_total': fields.function(_wage_all, digits_compute= dp.get_precision('Payroll'), string='Allowance',
            store={
                'hr.emppay': (_get_sheet, None, 10),
            }, multi="sums", readonly=1),
        'wage_total': fields.function(_wage_all, digits_compute= dp.get_precision('Payroll'), string='Total Wage',
            store={
                'hr.emppay': (_get_sheet, None, 10),
            }, multi="sums", readonly=1),  
        'ded_total': fields.function(_wage_all, digits_compute= dp.get_precision('Payroll'), string='Deduction',
            store={
                'hr.emppay': (_get_sheet, None, 10),
            }, multi="sums", readonly=1),  
        'si_total_personal': fields.function(_wage_all, digits_compute= dp.get_precision('Payroll'), string='SI(Personal)',
            store={
                'hr.emppay': (_get_sheet, None, 10),
            }, multi="sums", readonly=1),  
        'si_total_company': fields.function(_wage_all, digits_compute= dp.get_precision('Payroll'), string='SI(Company)',
            store={
                'hr.emppay': (_get_sheet, None, 10),
            }, multi="sums", readonly=1),  
        'money_borrow_deduction': fields.function(_wage_all, digits_compute= dp.get_precision('Payroll'), string='Borrow Deduction',
            store={
                'hr.emppay': (_get_sheet, None, 10),
            }, multi="sums", readonly=1),                       
        'wage_pay': fields.function(_wage_all, digits_compute= dp.get_precision('Payroll'), string='Wage Should Pay',
            store={
                'hr.emppay': (_get_sheet, None, 10),
            }, multi="sums", readonly=1),  
        'pit': fields.function(_wage_all, digits_compute= dp.get_precision('Payroll'), string='PIT',
            store={
                'hr.emppay': (_get_sheet, None, 10),
            }, multi="sums", readonly=1),  
        'wage_net': fields.function(_wage_all, digits_compute= dp.get_precision('Payroll'), string='Net Wage',
            store={
                'hr.emppay': (_get_sheet, None, 10),
            }, multi="sums", readonly=1),
        #HoangTK - 06/22/2016
        'sick_pay': fields.function(_wage_all, digits_compute= dp.get_precision('Payroll'), string='Injury Pay',
            store={
                'hr.emppay': (_get_sheet, None, 10),
            }, multi="sums", readonly=1),
        'house_rent_fund': fields.function(_wage_all, digits_compute= dp.get_precision('Payroll'), string='Individual Housing Fund',
            store={
                'hr.emppay': (_get_sheet, None, 10),
            }, multi="sums", readonly=1),
        'company_house_rent_fund': fields.function(_wage_all, digits_compute=dp.get_precision('Payroll'),
                                           string='Company Housing Fund',
                                           store={
                                               'hr.emppay': (_get_sheet, None, 10),
                                           }, multi="sums", readonly=1),
    }
    _defaults = {
        'state': 'draft'
    }
    def _get_period_id(self, cr, uid, dt_val, context=None):
        account_period_id = None
        period_ids = self.pool.get('account.period').find(cr,uid,dt_val,context=context)
        if period_ids:
            account_period_id = period_ids[0]            
        return account_period_id
    
    def default_get(self, cr, uid, fields_list, context=None):
        defaults = super(hr_emppay_sheet, self).default_get(cr, uid, fields_list, context=context)
        if not defaults:
            defaults = {}
        date_from = time.strftime('%Y-%m-01'),
        date_to = str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10],
        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        account_period_id = self._get_period_id(cr, uid, date_to, context=context)            
        defaults.update({'date_from': date_from, 'date_to': date_to,'company_id': company_id,'account_period_id':account_period_id})
        return defaults
    
    def onchange_date(self, cr, uid, ids, date_from, date_to, context=None):
        res = {'value':{}}         
        if not isinstance(date_from,type(' ')) or  not isinstance(date_to,type(' ')):
            return res
        account_period_id = self._get_period_id(cr, uid, date_to, context=context)            
        if account_period_id:
            res['value'] = {'account_period_id': account_period_id}
        return res
    
    def create(self, cr, uid, values, context=None):
        if not 'name' in values or values['name'] == '':
            name = self.pool.get('ir.sequence').get(cr, uid, 'emppay.payroll')
            if values['attend_month_id']:
                attendance_name = self.pool.get('hr.rpt.attend.month').read(cr, uid, values['attend_month_id'], ['name'], context=context)['name']
                if attendance_name:
                    name += '-' + attendance_name
            values['name'] = name
        if not 'account_period_id' in values:
            account_period_id = self._get_period_id(cr, uid, values['date_to'], context=context)            
            if account_period_id:
                values['account_period_id'] = account_period_id
        new_id = super(hr_emppay_sheet,self).create(cr, uid, values, context=context)                
        return new_id
        
    def recompute(self, cr, uid, ids, context=None):
        slip_ids = []
        for sheet in self.browse(cr, uid, ids, context=context):
            slip_ids += [slip.id for slip in sheet.emppay_ids]
        self.pool.get('hr.emppay').recompute(cr, uid, slip_ids, context=context)
        return True
        
    def unlink(self, cr, uid, ids, context=None):
        for rpt in self.read(cr, uid, ids, ['state'], context=context):
            if rpt['state'] not in ('draft'):
                raise osv.except_osv(_('Error'),_('Only order with Draft state can be delete!'))
        
        return super(hr_emppay_sheet, self).unlink(cr, uid, ids, context=context)
        
    def action_draft(self, cr, uid, ids, context=None):
        return self._set_state(cr, uid, ids, 'draft', context)

    def action_verify(self, cr, uid, ids, context=None):
        return self._set_state(cr, uid, ids, 'verified', context)
    
    def action_approve(self, cr, uid, ids, context=None):
        return self._set_state(cr, uid, ids, 'approved', context)
    
    def action_pay(self, cr, uid, ids, context=None):
        return self._set_state(cr, uid, ids, 'paid', context)
            
    def _set_state(self, cr, uid, ids, state, context=None):
        return self.write(cr, uid, ids, {'state': state}, context=context)
        emppay_ids = []
        for order in self.browse(cr, uid, ids, context=context):
            emppay_ids += [emppay.id for emppay in order.emppay_ids]
        self.pool.get('hr.emppay').write(cr, uid, emppay_ids, {'state':state}, context=context)
        return True

    #HoangTK - 06/22/2016 - Get injury days from approved leave requests
    def get_injury_days(self, cr, uid, ids, context=None):
        holiday_obj = self.pool.get('hr.holidays')
        holiday_status_obj = self.pool.get('hr.holidays.status')
        hr_emp_obj = self.pool.get('hr.emppay')
        injury_status_ids = holiday_status_obj.search(cr, uid, [
            '|',('name','like','工伤'),
            ('name','like','Injury'),
            ])
        for sheet in self.browse(cr, uid, ids, context=context):
            for slip in sheet.emppay_ids:
                leave_ids = holiday_obj.search(cr, uid, [
                    ('holiday_status_id','in',injury_status_ids),
                    ('employee_id','=',slip.employee_id.id),
                    ('date_from','>=','%s 00:00:00'%sheet.date_from),
                    ('date_to','<=','%s 23:59:59'%sheet.date_to),
                    ('state','=','validate')
                ])
                if len(leave_ids) > 0:
                    leaves = holiday_obj.browse(cr, uid, leave_ids)
                    sick_days = 0.0
                    for leave in leaves:
                        sick_days += leave.number_of_days_temp
                    hr_emp_obj.write(cr, uid, [slip.id],{
                        'sick_days': sick_days,
                        'sick_pay': sick_days * SICK_PAY_PER_DAY,
                    })

        return True

    def add_from_att_report(self, cr, uid, ids, context=None):
        order = self.browse(cr,uid,ids[0],context=context)
        if not order.attend_month_id:
            raise osv.except_osv(_('Invalid Action!'), _('Please set the Attendance Report first.'))
        #add new payslip data and remove the old payslips
        return self.pool.get('hr.rpt.attend.month').add_payroll(cr, uid, order.attend_month_id.id, ids[0], remove_old_slips = True, context=context)        
    
    def print_sheet_slip(self, cr, uid, ids, context=None):
        if context is None: 
            context = {}
        order = self.browse(cr, uid, ids[0], context=context)
        emppay_ids = [emppay.id for emppay in order.emppay_ids]
        return self.pool.get('hr.emppay').print_slip(cr, uid, emppay_ids, context=context)
    
    def print_sheet_slip_sign(self, cr, uid, ids, context=None):
        if context is None: 
            context = {}
        form_data = self.read(cr, uid, ids[0], context=context)
        datas = {
                 'model': self._name,
                 'ids': [ids[0]],
                 'form': form_data,
        }
        return {'type': 'ir.actions.report.xml', 'report_name': 'hr.emppay.slip.sign', 'datas': datas, 'nodestroy': True} 
        
    def print_sheet_slip_india(self, cr, uid, ids, context=None):
        if context is None: 
            context = {}
        order = self.browse(cr, uid, ids[0], context=context)
        emppay_ids = [emppay.id for emppay in order.emppay_ids]
        return self.pool.get('hr.emppay').print_slip_india(cr, uid, emppay_ids, context=context)
    
    def print_sheet_slip_sign_india(self, cr, uid, ids, context=None):
        if context is None: 
            context = {}
        form_data = self.read(cr, uid, ids[0], context=context)
        datas = {
                 'model': self._name,
                 'ids': [ids[0]],
                 'form': form_data,
        }
        return {'type': 'ir.actions.report.xml', 'report_name': 'hr.emppay.slip.sign.india', 'datas': datas, 'nodestroy': True} 
    
hr_emppay_sheet()

'''
from openerp.report import report_sxw
from openerp.addons.metro.rml import rml_parser_ext
class payslip_print(rml_parser_ext):
    def __init__(self, cr, uid, name, context):
        super(payslip_print, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'list_alw':self.list_alw,
            'list_ded':self.list_ded,
        })
    def list_alw(self,slip):
        ret = ''
        for alw in slip.alw_ids:
            ret += '%s: %s; '%(alw.name,alw.amount)
        return ret
    def list_ded(self,slip):
        ret = ''
        for item in slip.ded_ids:
            ret += '%s: %s; '%(item.name,item.amount)
#        ret += '%s: %s'%(u'社保(SI)',slip.si_total_personal)
        return ret
'''    
#report_sxw.report_sxw('report.hr.emppay.sheet.slip', 'hr.emppay.sheet', 'addons/metro_hr/emppay/hr_emppay_sheet_slip.rml', parser=payslip_print, header='internal landscape')

class hr_emppay_ln_alwded(osv.osv):
    """
    Payslip's line of allowance or deduction
    Most same structure with hr_emppay_alwded
    The reason to use this structure is that if user did adjustion to the hr_emppay_alwded globally, the salary history data won't be affected
    """

    _name = 'hr.emppay.ln.alwded'
    _description = 'Salary allowance and the deduction'
    _order = 'type, sequence'
    _columns = {
        'emppay_id': fields.many2one('hr.emppay', 'Payslip', required=True, select=True, ondelete='cascade'),
        'sequence': fields.integer('#', required=True),
        'code':fields.char('Code', size=64, required=True, select=True),
        'name':fields.char('Name', size=256, required=True),
        'type':fields.selection([('alw','Allowance'),('ded','Deduction'),('alw_inwage','Allowance In Wage')], string='Type', required=True ),
        'type_calc':fields.selection([('fixed','Fixed'),('by_attend','By Attendance')], string='Calculation Type', required=True ),
        'amount':fields.float('Amount', digits_compute=dp.get_precision('Payroll'), required=True),
    }
    
    _defaults={
               'type_calc':'fixed',
               }
    

class hr_emppay_ln_si(osv.osv):
    """
    Payslip's line of Social Insurance
    Most same structure with hr_emppay_si
    The reason to use this structure is that if user did adjustion to the hr_emppay_si globally, the salary history data won't be affected
    """
    _name = 'hr.emppay.ln.si'
    _description = 'Salary Social Insurance'
    def _amount_all(self, cr, uid, ids, field_names, args, context=None):
        res = dict((id,dict((field_name,None) for field_name in field_names)) for id in ids)
        for si in self.browse(cr, uid, ids, context=context):
            if 'amount_company' in field_names:
                res[si.id]['amount_company'] = si.amount_base * si.rate_company/100.00
            if 'amount_personal' in field_names:
                res[si.id]['amount_personal'] = si.amount_base * si.rate_personal/100.00
        return res
    
    _columns = {
        'emppay_id': fields.many2one('hr.emppay', 'Payslip', required=True, select=True, ondelete='cascade'),
        'sequence': fields.integer('#', required=True, select=True),
        'code':fields.char('Code', size=64, required=True),
        'name':fields.char('Name', size=256, required=True),
        'amount_base':fields.float('Base Amount', digits_compute=dp.get_precision('Payroll'), required=True),
        'rate_company':fields.float('Company Rate', digits_compute=dp.get_precision('Payroll'), required=True),
        'rate_personal':fields.float('Personal Rate', digits_compute=dp.get_precision('Payroll'), required=True),
        'amount_company':fields.function(_amount_all, string='Company Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_all"),
        'amount_personal':fields.function(_amount_all, string='Personal Amount', type='float', digits_compute=dp.get_precision('Payroll'), multi="_amount_all"),
    }
        
class hr_emppay(osv.osv):
    '''
    Pay Slip
    '''    
    _name = 'hr.emppay'
    _description = 'Pay Slip'

    def _ot_pay_info(self, cr, uid, contract, wage_days, wage2_days=None,  wage=None, wage2=None, context=None):
        if not contract or not wage_days or wage_days <= 0 or (wage2_days and wage2_days <=0):
            return False
        if isinstance(contract,(int,long)):
            contract = self.pool.get('hr.contract').browse(cr, uid, contract, context=context)
        if not wage:
            wage = contract.wage
        if not wage2:
            wage2 = contract.wage2
        if not wage2_days:
            wage2_days = wage_days
            
        curr_convert = False
        if contract.wage_currency_id and contract.wage_currency_id.id != contract.employee_id.company_id.currency_id.id:
            curr_convert = True
            curr_obj = self.pool.get('res.currency')
            curr_from_id = contract.wage_currency_id.id
            curr_to_id = contract.employee_id.company_id.currency_id.id
                
        fld_list = [{'opt':'ot_pay_normal','multi':'ot_pay_normal_multi'},{'opt':'ot_pay_weekend','multi':'ot_pay_weekend_multi'},{'opt':'ot_pay_holiday','multi':'ot_pay_holiday_multi'},
                    {'opt':'ot_pay_normal2','multi':'ot_pay_normal2_multi'},{'opt':'ot_pay_weekend2','multi':'ot_pay_weekend2_multi'},{'opt':'ot_pay_holiday2','multi':'ot_pay_holiday2_multi'}]
        ot_pays = {}
        for fld in fld_list:
            ot_pay_rate = 0.0
            fld_opt = fld['opt']
            fld_multi = fld['multi']
            ot_pay_opt = getattr(contract, fld_opt)
            if ot_pay_opt == 'wage':
                ot_pay_rate = (wage/wage_days/8.0)*getattr(contract,fld_multi) 
            if ot_pay_opt == 'wage2':
                ot_pay_rate = (wage2/wage2_days/8.0)*getattr(contract,fld_multi)
            if ot_pay_opt == 'fixed':
                ot_pay_rate = getattr(contract,fld_multi)
#            if curr_convert:
#                ot_pay_rate = curr_obj.compute(cr, uid, curr_from_id, curr_to_id, ot_pay_rate, context=context)
            ot_pays[fld_opt] = ot_pay_rate
                
        
        return ot_pays                            
            
    def _wage_compute(self, cr, uid, ids, field_names, args, context=None):
        res = dict((id,dict((field_name,None) for field_name in field_names)) for id in ids)
        for slip in self.browse(cr, uid, ids, context=context):
            wage_attend = 0.0
            wage_ot = 0.0
            month_attend_days_law = slip.company_id.month_attend_days_law
            ot_pays = self._ot_pay_info(cr, uid, slip.contract_id, slip.days_work, month_attend_days_law, wage=slip.wage, wage2=slip.wage2,context=context)
            if slip.days_work and slip.days_work != 0:
                wage_attend = slip.wage*slip.days_attend/slip.days_work
                wage_ot = ot_pays['ot_pay_normal'] * slip.hours_ot
                wage_ot_we = ot_pays['ot_pay_weekend'] * slip.hours_ot_we
                wage_ot_holiday = ot_pays['ot_pay_holiday'] * slip.hours_ot_holiday
                wage_ot_total = wage_ot + wage_ot_we + wage_ot_holiday
                
                wage_work = wage_attend + wage_ot_total
            
            alw_total = 0.0
            for alw in slip.alw_ids:
                alw_total += alw.amount
                
            ded_total = 0.0
            for ded in slip.ded_ids:
                ded_total += ded.amount
                
            si_total_personal = 0.0
            si_total_company = 0.0
            for si in slip.si_ids:
                si_total_personal += si.amount_personal
                si_total_company += si.amount_company
                
            #HoangTK 22/06/2016 Add sick pay to wage
            sick_pay = slip.sick_days * SICK_PAY_PER_DAY
            wage_attend += sick_pay
            #wage_total = wage_attend + wage_ot + alw_total
            #HoangTK 16/09/2016 Change forumla of wage total & wage for tax
            wage_total = wage_work + alw_total
            #johnw, 01/21/2015, add money_borrow_deduction       
            money_borrow_original = slip.employee_id.money_residual
            money_borrow_deduction = slip.money_borrow_deduction
            money_borrow_residual = money_borrow_original - money_borrow_deduction            
            #money_borrow_deduction is in local currency, need convert it to foreign currency and do calculation later
            if money_borrow_deduction !=0 and slip.currency_id and slip.currency_id.id != slip.company_id.currency_id.id:
                curr_from_id = slip.company_id.currency_id.id
                curr_to_id = slip.currency_id.id
                money_borrow_deduction = self.pool.get('res.currency').compute(cr, uid, curr_from_id, curr_to_id, money_borrow_deduction, context=context)            
            #HoangTK - 06/23/2016 Minus house rent fund into deduction total
            #wage_pay = wage_total - ded_total - si_total_personal - money_borrow_deduction
            ded_total += slip.house_rent_fund
            wage_pay = wage_total - ded_total - si_total_personal - money_borrow_deduction
            #wage_tax = wage_total - si_total_personal
            #wage_tax = wage_pay
            #HoangTK 16/09/2016 Change forumla of wage total & wage for tax
            wage_tax = wage_total - slip.house_rent_fund - si_total_personal
            pit = 0.0
            if slip.contract_id.have_pit:
                pit_formula = slip.company_id.emppay_pit_formula
                if not pit_formula:
                    pit_formula = "[(0.03, 0), (0.1, 105), (0.2, 555), (0.25, 1005), (0.3, 2755), (0.35, 5505), (0.45, 13505)]"
                pit_rates = eval(pit_formula)
                pit = max([(wage_tax - slip.contract_id.pit_base)*rate[0]-rate[1]  for rate in pit_rates])
                pit = max([pit,0])  
            
            wage_net = wage_pay - pit
                        
            '''
            The reason use 'month_attend_days_law' is that the days_attends is based on the month_attend_days_law
            see below code in hr_rpt_attend_month:
                days_attend2 = days_attend2/days_work2*month_attend_days_law
            '''                                        
            wage_attend2 = slip.wage2*slip.days_attend2/month_attend_days_law
            wage_ot2 = ot_pays['ot_pay_normal2'] * slip.hours_ot2
            wage_ot_we2 = ot_pays['ot_pay_weekend2'] * slip.hours_ot_we2
            wage_ot_holiday2 = ot_pays['ot_pay_holiday2'] * slip.hours_ot_holiday2
            wage_ot_total2 = wage_ot2 + wage_ot_we2 + wage_ot_holiday2

            alw_inwage_total = 0.0
            for alw_inwage in slip.alw_inwage_ids:
                alw_inwage_total += alw_inwage.amount
            
            wage_work2 = wage_work
            wage_work2_subtotal = wage_work2 - wage_ot_total2
            wage_bonus2 = wage_work2_subtotal - alw_inwage_total - wage_attend2

            res[slip.id].update({'wage_attend':wage_attend,
                               'wage_ot':wage_ot,
                               'wage_ot_we':wage_ot_we,
                               'wage_ot_holiday':wage_ot_holiday,
                               'wage_ot_total':wage_ot_total,
                               'wage_work':wage_work,
                               'alw_total':alw_total,
                               'wage_total':wage_total,
                               'ded_total':ded_total,
                               'si_total_personal':si_total_personal,                               
                               'si_total_company':si_total_company,
                               'money_borrow_original':money_borrow_original,
                               'money_borrow_residual':money_borrow_residual,
            
                               'wage_pay':wage_pay,
                               
                               'wage_tax':wage_tax,
                               'pit':pit,
                               
                               'wage_net':wage_net,  
                               
                               'wage_attend2':wage_attend2, 
                               'wage_ot2':wage_ot2,
                               'wage_ot_we2':wage_ot_we2,
                               'wage_ot_holiday2':wage_ot_holiday2,
                               'wage_ot_total2':wage_ot_total2,
                               'wage_bonus2':wage_bonus2,  
                               'alw_inwage_total':alw_inwage_total, 
                               'wage_work2_subtotal':wage_work2_subtotal,
                               'wage_work2':wage_work2,
                                 #HoangTK - Calculate sick pays:
                                'sick_pay': sick_pay,
                                #HoangTK - Add house rent fund:
                                # 'house_rent_fund': slip.contract_id.house_rent_fund,
                                # 'company_house_rent_fund': slip.contract_id.company_house_rent_fund,
                               })              
        return res
    
    def _wage_all(self, cr, uid, ids, field_names, args, context=None):
        '''
        For the function's field method reuse, call another _wage_compute, and override it on hr_emppay_currency.py 
        '''
        return self._wage_compute(cr, uid, ids, field_names, args, context=context)
            
    def _emp_year_total(self, cr, uid, ids, fields, args, context=None):
        res = dict.fromkeys(ids, None)
        emppay_total_obj = self.pool.get('hr.emppay.rpt.emp.year')
        for emppay in self.browse(cr, uid, ids, context=context):
            total_ids = emppay_total_obj.search(cr, uid, [('employee_id','=',emppay.employee_id.id), ('fiscalyear_id','=',emppay.emppay_sheet_id.account_period_id.fiscalyear_id.id)])
            if total_ids:
                res[emppay.id] = total_ids[0]
        return res
    
    _columns = {
        'name': fields.char('Name', size=64, required=False, readonly=True, states={'draft': [('readonly', False)]}),   
        'employee_id': fields.many2one('hr.employee', 'Employee', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'contract_id': fields.many2one('hr.contract', 'Contract', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date_from': fields.date('Date From', readonly=True, states={'draft': [('readonly', False)]}, required=True),
        'date_to': fields.date('Date To', readonly=True, states={'draft': [('readonly', False)]}, required=True),        
        'emppay_year_id': fields.function(_emp_year_total, string='Employee Year Total', type='many2one', relation='hr.emppay.rpt.emp.year', readonly=True),
        
        #Below from employee contract, 数据为只读
        #contract.wage
        'wage':fields.float('Contract Wage', digits_compute=dp.get_precision('Payroll')),
        #contract.wage2
        'wage2':fields.float('Contract Wage2', digits_compute=dp.get_precision('Payroll')),     
        #attendance report line id
        'attend_id':fields.many2one('hr.rpt.attend.month.line', 'Attendance'),
        
        #Below from attend data, user can change, 数据为只读
        'days_work': fields.related('attend_id','days_work',type='float',string='Work Days',  readonly=True), #attend_line_id.days_work
        'days_attend': fields.related('attend_id','days_attend',type='float',string='Days Attended',  readonly=True),#attend_line_id.days_attend
        'hours_ot': fields.related('attend_id','hours_ot',type='float',string='Hours OT(Normal)',  readonly=True),#attend_line_id.hours_ot
        'hours_ot_we': fields.float('Hours OT(Week End)', readonly=True),#0
        'hours_ot_holiday': fields.float('Hours OT(Law Holiday)', readonly=True), #0
        #Below from attend data, user can change, 数据为只读, 下面相关字段的显示使用组来限制
        'days_work2': fields.related('attend_id','days_work2',type='float',string='Work Days2',  readonly=True), #attend_line_id.days_work2
        'days_attend2_real': fields.related('attend_id','days_attend2_real',type='float',string='Days Attended2 Real',  readonly=True),#attend_line_id.days_attend2
        #days by 21.75
        'days_attend2': fields.related('attend_id','days_attend2',type='float',string='Days Attended2',  readonly=True),#attend_line_id.days_attend2
        'hours_ot2': fields.related('attend_id','hours_ot2_nonwe',type='float',string='Hours OT(Normal)2',  readonly=True),#attend_line_id.hours_ot2_nonwe
        'hours_ot_we2': fields.related('attend_id','hours_ot2_we',type='float',string='Hours OT(Week End)2',  readonly=True),#attend_line_id.hours_ot2_we
        'hours_ot_holiday2': fields.float('Hours OT(Law Holiday)', readonly=True), #0   
        
        #copy from contract_id.alwded_ids
        'alw_ids': fields.one2many('hr.emppay.ln.alwded', 'emppay_id', string='Allowance', required=False, readonly=True, 
                                   states={'draft': [('readonly', False)]}, domain=[('type','=','alw')]),
        'ded_ids': fields.one2many('hr.emppay.ln.alwded', 'emppay_id', string='Deduction', required=False, readonly=True, 
                                   states={'draft': [('readonly', False)]}, domain=[('type','=','ded')]),
        #the allowance including in wage_work2
        'alw_inwage_ids': fields.one2many('hr.emppay.ln.alwded', 'emppay_id', string='Allowance', required=False, readonly=True, 
                                   states={'draft': [('readonly', False)]}, domain=[('type','=','alw_inwage')]),
                
        #copy from contract_id.si_ids
        'si_ids': fields.one2many('hr.emppay.ln.si', 'emppay_id', 'Social Insurance', required=False, readonly=True, states={'draft': [('readonly', False)]}),
        
        #wage items, calculated based on atttendance, wage, alw_ids, ded_ids, si_ids        
        'wage_attend':fields.function(_wage_all, string='Wage(attend)', type='float', store=True,
                                      digits_compute=dp.get_precision('Payroll'), multi="_wage_all"), 
        'wage_ot':fields.function(_wage_all, string='Wage(OT)', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'wage_ot_we':fields.function(_wage_all, string='Wage(OT Weekend)', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'wage_ot_holiday':fields.function(_wage_all, string='Wage(OT Holiday)', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),                
        'wage_ot_total':fields.function(_wage_all, string='Wage(OT Total)', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                  help="Wage(OT) + Wage(OT Weekend) + Wage(OT Holiday)"),
        'wage_work':fields.function(_wage_all, string='Wage(Work)', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                  help="Wage(attend) + Wage(OT)"),
        'alw_total':fields.function(_wage_all, string='Allowance', type='float',  store=True,
                                    digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        #wage_attend + wage_ot + alw_total
        'wage_total':fields.function(_wage_all, string='Wage(total)', type='float',  store=True,
                                     digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                     help="Wage(attend) + Wage(OT) + Allowance"),
        'ded_total':fields.function(_wage_all, string='Deduction', type='float',  store=True,
                                    digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'si_total_personal':fields.function(_wage_all, string='SI(Personal)', type='float',  store=True,
                                            digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'si_total_company':fields.function(_wage_all, string='SI(Company)', type='float',  store=True,
                                           digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        #employee borrowing
        'money_borrow_original':fields.function(_wage_all, string='Borrowed Money', type='float',  store=True,
                                    digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'money_borrow_deduction':fields.float('Borrow Deduction', digits_compute=dp.get_precision('Payroll')),
        'money_borrow_residual':fields.function(_wage_all, string='Borrowed Residual', type='float',  store=True,
                                    digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        #wage_total - ded_total - si_total_personal - money_borrow_deduction
        'wage_pay':fields.function(_wage_all, string='Wage(Pay)', type='float',  store=True,
                                     digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                     help="Wage(total) - Deduction - SI(Personal) - Borrow Deduction"),
        #wage_attend + wage_ot + alw_total - si_total_personal
        'wage_tax':fields.function(_wage_all, string='Wage(for tax)', type='float',  store=True,
                                   digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                     help="Wage(total) - SI(Personal)"),
        'pit':fields.function(_wage_all, string='PIT', type='float',  store=True,
                              digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        #wage_pay - PIT
        'wage_net':fields.function(_wage_all, string='Wage(Net)', type='float',  store=True,
                                   digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                     help="Wage(Pay) - PIT"),  
        #wages for 2
        'wage_attend2':fields.function(_wage_all, string='Wage(attend)2', type='float', store=True,
                                      digits_compute=dp.get_precision('Payroll'), multi="_wage_all"), 

        'wage_ot2':fields.function(_wage_all, string='Wage(OT)2', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'wage_ot_we2':fields.function(_wage_all, string='Wage(OT Weekend)2', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'wage_ot_holiday2':fields.function(_wage_all, string='Wage(OT Holiday)2', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),            
        #wage_ot2 +  wage_ot_we2 + wage_ot_holiday2
        'wage_ot_total2':fields.function(_wage_all, string='Wage(OT Total)2', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                  help="Wage(OT)2 + Wage(OT Weekend)2 + Wage(OT Holiday)2"),
        #total of the alw_ids_inwage        
        'alw_inwage_total':fields.function(_wage_all, string='Allowage In Wage', type='float',  store=True,
                                    digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        #wage_work2 - wage_ot_total2
        'wage_work2_subtotal':fields.function(_wage_all, string='Wage2 Subtotal', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),                
        #wage_work2_subtotal - wage_attend2 - alw_inwage_total
        'wage_bonus2':fields.function(_wage_all, string='Wage(Bonus)2', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        #=wage_work
        'wage_work2':fields.function(_wage_all, string='Wage(Work)2', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                  help="Wage(attend)2 + Wage(OT Total)2 + Wage(Bonus)2"),                                               
        'state': fields.selection([
            ('draft', 'Draft'),
            ('verified', 'Verified'),
            ('approved', 'Approved'),
            ('paid', 'Paid'),
        ], 'Status', select=True, readonly=True,
            help='* When the payslip is created the status is \'Draft\'.\
            \n* If the payslip is verified, the status is \'Verified\'. \
            \n* If the payslip is paid then status is set to \'Paid\'.'),
        'company_id': fields.many2one('res.company', 'Company', required=False, readonly=True, states={'draft': [('readonly', False)]}),
        'company_currency_id': fields.related('company_id','currency_id',string='Company Currency', type='many2one', relation='res.currency', readonly=True),
        'note': fields.text('Description', readonly=True, states={'draft':[('readonly',False)]}),
        'emppay_sheet_id': fields.many2one('hr.emppay.sheet', 'Payroll', readonly=True, states={'draft': [('readonly', False)]}, ondelete='cascade'),
        'emp_took': fields.boolean('Slip Took'),
        #HoangTK - Add column sick days and sick pay and house rent fund
        'sick_days': fields.float('Injury Days'),
        'sick_pay': fields.function(_wage_all, string='Injury Pay', type='float',  store=True,
                                  digits_compute=dp.get_precision('Payroll'), multi="_wage_all",
                                  help="Sick Pays * 58.08"),
        'house_rent_fund': fields.float('Individual Housing Fund'),
        'company_house_rent_fund': fields.float('Company Housing Fund'),
    }
    _defaults = {
        'date_from': lambda *a: time.strftime('%Y-%m-01'),
        'date_to': lambda *a: str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10],
        'state': 'draft',
        'company_id': lambda self, cr, uid, context: \
                self.pool.get('res.users').browse(cr, uid, uid,
                    context=context).company_id.id,
        'house_rent_fund': 0,
        'company_house_rent_fund': 0,
        'sick_days': 0.0,
    }

    def _check_dates(self, cr, uid, ids, context=None):
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.date_from > payslip.date_to:
                return False
        return True

    _constraints = [(_check_dates, "Payslip 'Date From' must be before 'Date To'.", ['date_from', 'date_to'])]
    
    def create(self, cr, uid, values, context=None):
        if not 'name' in values or values['name'] == '':
            name = self.pool.get('ir.sequence').get(cr, uid, 'emppay.payslip')
            values['name'] = name
        #default deduct all of the employee's borrow money residual
        if not values.get('money_borrow_deduction') and values.get('employee_id'):
            money_borrow_deduction = self.pool.get('hr.employee').read(cr, uid, values['employee_id'], ['money_residual'], context=context)['money_residual']
            #default to deduct the borrow money fully
            values['money_borrow_deduction'] = money_borrow_deduction
                        
        return super(hr_emppay,self).create(cr, uid, values, context=context)
        
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'company_id': self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
            'name': self.pool.get('ir.sequence').get(cr, uid, 'emppay.payslip'),
            'emppay_sheet_id': False,
        })
        
        return super(hr_emppay, self).copy(cr, uid, id, default, context=context)

    def action_verify(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'verified'}, context=context)
   
    def action_approve(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'approved'}, context=context)
    
    def action_pay(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'paid'}, context=context)

    def action_draft(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'draft'}, context=context)

    def unlink(self, cr, uid, ids, context=None):
        for payslip in self.browse(cr, uid, ids, context=context):
            if payslip.state not in  ['draft']:
                raise osv.except_osv(_('Warning!'),_('You cannot delete a payslip which is not draft!'))
        return super(hr_emppay, self).unlink(cr, uid, ids, context)
    
    def print_slip(self, cr, uid, ids, context=None):
        if context is None: 
            context = {}
        form_data = self.read(cr, uid, ids, context=context)
        datas = {
                 'model': 'hr.emppay',
                 'ids': ids,
                 'form': form_data,
        }
        return {'type': 'ir.actions.report.xml', 'report_name': 'hr.emppay.slip', 'datas': datas, 'nodestroy': True} 

    def print_slip_dimission(self, cr, uid, ids, context=None):
        if context is None: 
            context = {}
        form_data = self.read(cr, uid, ids, context=context)
        datas = {
                 'model': 'hr.emppay',
                 'ids': ids,
                 'form': form_data,
        }
        return {'type': 'ir.actions.report.xml', 'report_name': 'hr.emppay.slip.dimission', 'datas': datas, 'nodestroy': True} 
        
    def print_slip_india(self, cr, uid, ids, context=None):
        if context is None: 
            context = {}
        form_data = self.read(cr, uid, ids, context=context)
        datas = {
                 'model': 'hr.emppay',
                 'ids': ids,
                 'form': form_data,
        }
        return {'type': 'ir.actions.report.xml', 'report_name': 'hr.emppay.slip.india', 'datas': datas, 'nodestroy': True}     
    
    def recompute(self, cr, uid, ids, context=None):
        for slip in self.browse(cr, uid, ids, context=context):            
            #emppay_sheet_id updating will trigger the wage recalucation function
            self.write(cr, uid, slip.id, {'emppay_sheet_id':slip.emppay_sheet_id.id}, context=context)
        return True
            
    def emp_take(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'emp_took':True}, context=context)
            
hr_emppay()

from openerp.report import report_sxw
from openerp.addons.metro.rml import rml_parser_ext
class hr_emppay_slip_print(rml_parser_ext):
    def __init__(self, cr, uid, name, context):
        super(hr_emppay_slip_print, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'list_alw':self.list_alw,
            'list_ded':self.list_ded,
        })
    def list_alw(self,slip):
        ret = ''
        alws = slip.alw_ids
        for alw in alws:
            if alw.amount !=0:
                ret += '%s: %s; '%(alw.name,alw.amount)
        return ret
    def list_ded(self,slip):
        ret = ''
        for item in slip.ded_ids:
            if item.amount !=0:
                ret += '%s: %s; '%(item.name,item.amount)                                    
        return ret
    
report_sxw.report_sxw('report.hr.emppay.slip', 'hr.emppay', 'addons/metro_hr/emppay/hr_emppay_slip.rml', parser=hr_emppay_slip_print, header='internal landscape')
report_sxw.report_sxw('report.hr.emppay.slip.dimission', 'hr.emppay', 'addons/metro_hr/emppay/hr_emppay_slip_dimission.rml', parser=hr_emppay_slip_print, header='internal landscape')
report_sxw.report_sxw('report.hr.emppay.slip.sign', 'hr.emppay.sheet', 'addons/metro_hr/emppay/hr_emppay_slip_sign.rml', parser=hr_emppay_slip_print, header='internal landscape')
report_sxw.report_sxw('report.hr.emppay.slip.india', 'hr.emppay', 'addons/metro_hr/emppay/hr_emppay_india_slip.rml', parser=hr_emppay_slip_print, header='internal landscape')
report_sxw.report_sxw('report.hr.emppay.slip.sign.india', 'hr.emppay.sheet', 'addons/metro_hr/emppay/hr_emppay_india_slip_sign.rml', parser=hr_emppay_slip_print, header='internal landscape')

class hr_employee(osv.osv):
    '''
    Employee
    '''
    _inherit = 'hr.employee'
    _columns = {
        'emppay_ids':fields.one2many('hr.emppay', 'employee_id', 'Payslips', required=False, readonly=True)
    }

hr_employee()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
