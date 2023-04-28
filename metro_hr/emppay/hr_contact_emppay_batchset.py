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

from openerp.osv import osv,fields
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp


class hr_set_alwded(osv.osv_memory):
    _name = 'hr.set.alwded'
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
        'set_id': fields.many2one('hr.contract.emppay.batchset', required=True, select=True, ondelete='cascade'),
        'alwded_id': fields.many2one('hr.emppay.alwded', 'Allowance/Deduction', required=True, ondelete='cascade'),
        'sequence': fields.related('alwded_id', 'sequence', type='integer', string='#', store=True, readonly=True),
        'type': fields.related('alwded_id', 'type', type='selection', selection=[('alw','Allowance'),('ded','Deduction'),('alw_inwage','Allowance In Wage')],
                                    string='Type', store=True, readonly=True),
        'type_calc':fields.related('alwded_id', 'type_calc', type='selection', selection=[('fixed','Fixed'),('by_attend','By Attendance')], 
                                    string='Calculation Type', store=True, readonly=True),
        #default is alwded_id.amount, user can change it
        'amount': fields.float('Amount', digits_compute=dp.get_precision('Payroll'), required=True),
        #fields related to hr_rpt_attend_month_line
        "attend_field" : fields.selection(_alwded_field_get, "Attend Field", size=32, help="Associated field in the attendance report."),
        'currency_id':fields.many2one('res.currency','Currency'),
    }
    
    _defaults={
               'type_calc':'fixed',
               }
    def onchange_alwded_id(self, cr, uid, ids, alwded_id, context=None):
        alwded = self.pool.get('hr.emppay.alwded').browse(cr, uid, alwded_id, context=context)
        vals = {'sequence':alwded.sequence, 'type':alwded.type, 'type_calc':alwded.type_calc, 'amount':alwded.amount, 'attend_field':alwded.attend_field}
        return {'value':vals}
    

class hr_set_si(osv.osv_memory):
    _name = 'hr.set.si'
    _description = 'Contact''s Salary Social Insurance'
    def _amount_all(self, cr, uid, ids, field_names, args, context=None):
        res = dict((id,dict((field_name,None) for field_name in field_names)) for id in ids)
        for si in self.browse(cr, uid, ids, context=context):
            if 'amount_company' in field_names:
                res[si.id]['amount_company'] = si.amount_base * si.rate_company
            if 'amount_personal' in field_names:
                res[si.id]['amount_personal'] = si.amount_base * si.rate_personal
        return res    
    
    _order = 'sequence'
    
    _columns = {
        'set_id': fields.many2one('hr.contract.emppay.batchset', required=True, select=True, ondelete='cascade'),
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
        
class hr_contract_emppay_batchset(osv.osv_memory):
    _name = 'hr.contract.emppay.batchset'
    _description = 'Set Contract Payroll in batch'
    _OTPAY_SEL = [('wage', 'Wage'),('wage2', 'Basic Wage'),('fixed', 'Fixed Amount')]
    _columns = {
        'wage2_set':fields.boolean('Set Wage2'),
        'wage2':fields.float('Wage2', digits_compute=dp.get_precision('Payroll')),
        'pit_base_set':fields.boolean('Set PIT Start Point'),
        'pit_base':fields.float('PIT Start Point', digits_compute=dp.get_precision('Payroll')),
        'wage_currency_set':fields.boolean('Set Wage Currency'),
        'wage_currency_id': fields.many2one('res.currency', 'Wage Currency'),
        #####################
        'ot_pay_set':fields.boolean('Set OT Pay Options'),
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
        #####################
                        
        'alwded_ids_set':fields.boolean('Set Allowance&Deduction'),
        'alwded_ids': fields.one2many('hr.set.alwded', 'set_id', 'Allowance&Deduction'),
        'si_ids_set':fields.boolean('Set Social Insurance'),
        'si_ids': fields.one2many('hr.set.si', 'set_id', 'Social Insurance'),
        
        'contract_ids': fields.many2many('hr.contract', string='Contracts'),
    }
    def _get_currency(self, cr, uid, context=None):
        if context is None:
            context = {}
        cur = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id
        return cur and cur.id or False
        
    _defaults={
        'wage2_set':False, 
        'pit_base_set':False,
        'wage_currency_set':False, 
        'ot_pay_set':False,
        'alwded_ids_set':True, 
        'si_ids_set':True,
        'wage_currency_id': _get_currency,
        
        'ot_pay_normal': 'wage',
        'ot_pay_normal_multi': 1,
        'ot_pay_weekend': 'wage',
        'ot_pay_weekend_multi': 2,
        'ot_pay_holiday': 'wage',
        'ot_pay_holiday_multi': 3,
        
        'ot_pay_normal2': 'wage2',
        'ot_pay_normal2_multi': 1,
        'ot_pay_weekend2': 'wage2',
        'ot_pay_weekend2_multi': 2,
        'ot_pay_holiday2': 'wage2',
        'ot_pay_holiday2_multi': 3,               
        }
                        
    def default_get(self, cr, uid, fields, context=None):
        vals = super(hr_contract_emppay_batchset, self).default_get(cr, uid, fields, context=context)
        if not vals:
            vals = {}
        #employees
        if context.get('active_model','') == 'hr.employee' and context.get('active_ids'):
            emp_ids = context.get('active_ids')
            contract_obj = self.pool.get('hr.contract')
            date_now = time.strftime('%Y-%m-%d')
            contract_ids = []
            for emp_id in emp_ids:
                emp_contract_ids = contract_obj.get_emp_contract(cr, uid, emp_id, date_now, date_now, context=context)
                if emp_contract_ids:
                    contract_ids += [emp_contract_ids[0]]
            vals['contract_ids'] = contract_ids
                
        #contracts
        if context.get('active_model','') == 'hr.contract' and context.get('active_ids'):
            vals['contract_ids'] = context.get('active_ids')
                                
        return vals
    
    def clear_set_data(self, cr, uid, ids, context=None):
        self.set_data(cr, uid, ids, context, clear_data = True)
            
    
    def set_data(self, cr, uid, ids, context=None, clear_data = False):
        order = self.browse(cr, uid, ids[0], context=context)
        if order.contract_ids:
            #field names to read
            field_names = []
            if order.wage2_set:
                field_names.append('wage2') 
            if order.pit_base_set:
                field_names.append('pit_base')
            if order.wage_currency_set:
                field_names.append('wage_currency_id')
            if order.ot_pay_set:
                field_names.append('ot_pay_normal')
                field_names.append('ot_pay_normal_multi')
                field_names.append('ot_pay_weekend')
                field_names.append('ot_pay_weekend_multi')
                field_names.append('ot_pay_holiday')
                field_names.append('ot_pay_holiday_multi')
                field_names.append('ot_pay_normal2')
                field_names.append('ot_pay_normal2_multi')
                field_names.append('ot_pay_weekend2')
                field_names.append('ot_pay_weekend2_multi')
                field_names.append('ot_pay_holiday2')
                field_names.append('ot_pay_holiday2_multi')
                
            if order.alwded_ids_set:
                field_names.append('alwded_ids')
            if order.si_ids_set:
                field_names.append('si_ids')
            if field_names:
                data_write = {}
                for field_name in field_names:
                    if field_name == 'alwded_ids':
                        alwded_ids = [alwded_id.id for alwded_id in order.alwded_ids]
                        alwded_dicts = self.pool.get('hr.set.alwded').read(cr, uid, alwded_ids, context=context)
                        alwded_ids = []
                        for alwded in alwded_dicts:
                            alwded['alwded_id'] = alwded['alwded_id'][0]
                            alwded['currency_id'] = alwded['currency_id'] and alwded['currency_id'][0] or None
                            alwded_ids.append((0,0,alwded))
                        data_write['alwded_ids'] = alwded_ids
                    elif field_name == 'si_ids':
                        si_ids = [si_id.id for si_id in order.si_ids]
                        si_dicts = self.pool.get('hr.set.si').read(cr, uid, si_ids, context=context)
                        si_ids = []
                        for si in si_dicts:
                            si['si_id'] = si['si_id'][0]
                            si_ids.append((0,0,si))
                        data_write['si_ids'] = si_ids
                    elif field_name == 'wage_currency_id':
                        if order[field_name]:
                            data_write[field_name] = order[field_name].id
                    else:
                        data_write[field_name] = order[field_name]
                        
                contract_ids = [contract.id for contract in order.contract_ids]
                
                #clear data
                if clear_data:
                    unlink_ids =  self.pool.get('hr.contract.alwded').search(cr, uid, [('contract_id', 'in', contract_ids)], context=context)
                    self.pool.get('hr.contract.alwded').unlink(cr, uid, unlink_ids, context=context)
                    unlink_ids =  self.pool.get('hr.contract.si').search(cr, uid, [('contract_id', 'in', contract_ids)], context=context)
                    self.pool.get('hr.contract.si').unlink(cr, uid, unlink_ids, context=context)
                #write data
                self.pool.get('hr.contract').write(cr, uid, contract_ids, data_write,context=context)
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
