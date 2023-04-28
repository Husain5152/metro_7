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
    
class hr_contract(osv.osv):
    _inherit = 'hr.contract'
    _columns = {        
        #Wage currency
        'wage_currency_id': fields.many2one('res.currency', 'Wage Currency'),
    }

    def _get_currency(self, cr, uid, context=None):
        if context is None:
            context = {}
        cur = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id
        return cur and cur.id or False
        
    _defaults={
        'wage_currency_id': _get_currency
        }
    
class hr_emppay(osv.osv):
    _inherit = 'hr.emppay'
    '''
    Override this method, to share code between parent and child's function fields
    '''
    def _wage_compute(self, cr, uid, ids, field_names, args, context=None):
        resu = super(hr_emppay, self)._wage_compute(cr, uid, ids, field_names, args, context=None)
        curr_obj = self.pool.get('res.currency')
        for slip in self.browse(cr, uid, ids, context=context):
            currency_rate = 1
            slip_currency_id = slip.currency_id or slip.contract_id.wage_currency_id
            if slip_currency_id and slip_currency_id.id != slip.company_id.currency_id.id:            
                curr_from_id = slip_currency_id.id
                curr_to_id = slip.company_id.currency_id.id
                wage_total_local = curr_obj.compute(cr, uid, curr_from_id, curr_to_id, resu[slip.id]['wage_total'], context=context)
                wage_pay_local = curr_obj.compute(cr, uid, curr_from_id, curr_to_id, resu[slip.id]['wage_pay'], context=context)
                wage_net_local = curr_obj.compute(cr, uid, curr_from_id, curr_to_id, resu[slip.id]['wage_net'], context=context)
                alw_total_local = curr_obj.compute(cr, uid, curr_from_id, curr_to_id, resu[slip.id]['alw_total'], context=context)
                ded_total_local = curr_obj.compute(cr, uid, curr_from_id, curr_to_id, resu[slip.id]['ded_total'], context=context)
                currency_rate = curr_obj._get_conversion_rate(cr, uid, slip.company_id.currency_id, slip_currency_id, context=context)
                resu[slip.id].update({'show_local':True, 
                                      'wage_total_local':wage_total_local, 'wage_pay_local':wage_pay_local, 'wage_net_local':wage_net_local,
                                      'alw_total_local':alw_total_local, 'ded_total_local':ded_total_local, 'currency_rate':currency_rate})
            else:
                resu[slip.id].update({'show_local':False, 'wage_total_local':0.0, 'wage_pay_local':0.0, 'wage_net_local':0.0, 'currency_rate':1})        
        return resu
    '''
    this method is also defined in hr_emppay.py, but the method in function's field can not be inherited by reuse, so redefine it and do not call super
    Both the _wage_all in hr_emppay.py and this py file, will call same method _wage_compute(), override that method
    '''    
    def _wage_all(self, cr, uid, ids, field_names, args, context=None):
        return self._wage_compute(cr, uid, ids, field_names, args, context=context)
                
    _columns = {
        'currency_id':fields.related('contract_id', 'wage_currency_id', string="Currency", type='many2one',relation='res.currency',store=True),
        'currency_rate':fields.function(_wage_all, string='Currency Rate', type='float', digits=(12,6),  store=True, multi="_wage_all"),
        'show_local':fields.function(_wage_all, string='Show Local', type='boolean',  store=True, multi="_wage_all"),
        'wage_total_local':fields.function(_wage_all, string='Total Wage Local', type='float',  store=True,
                                     digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'wage_pay_local':fields.function(_wage_all, string='Wage Should Pay Local', type='float',  store=True,
                                     digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
        'wage_net_local':fields.function(_wage_all, string='Net Wage Local', type='float',  store=True,
                                   digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),  
        'alw_total_local':fields.function(_wage_all, string='Allowance Local', type='float',  store=True,
                                   digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),  
        'ded_total_local':fields.function(_wage_all, string='Deduction Local', type='float',  store=True,
                                   digits_compute=dp.get_precision('Payroll'), multi="_wage_all"),
    }
    
    def recompute(self, cr, uid, ids, context=None):
        alwded_obj = self.pool.get('hr.emppay.ln.alwded')
        curr_obj = self.pool.get('res.currency')   
        for slip in self.browse(cr, uid, ids, context=context):
            if slip.currency_id and slip.currency_id.id != slip.company_id.currency_id.id:
                curr_slip_id = slip.currency_id.id
                curr_local_id = slip.company_id.currency_id.id                
                #recompute the allowance and deductions by the currency rate
                #allowance: from amount to amount local
                for alw in slip.alw_ids:
                    if alw.currency_id and alw.currency_id.id == curr_slip_id:
                        amount_local = curr_obj.compute(cr, uid, curr_slip_id, curr_local_id, alw.amount, context=context)
                        alwded_obj.write(cr, uid,alw.id,{'amount_local':amount_local})
                #deduction: from amount local to amount
                for ded in slip.ded_ids:
                    if ded.currency_id and ded.currency_id.id == curr_slip_id:
                        amount = curr_obj.compute(cr, uid, curr_local_id, curr_slip_id, ded.amount_local, context=context)
                        alwded_obj.write(cr, uid,ded.id,{'amount':amount})
        return super(hr_emppay, self).recompute(cr, uid, ids, context=context)   
                
hr_emppay()

class hr_contract_alwded(osv.osv):
    _inherit = 'hr.contract.alwded'
    _columns = {
        'currency_id':fields.many2one('res.currency','Currency'),
    }
    
    def create(self, cr, uid, values, context=None):
        new_id = super(hr_contract_alwded,self).create(cr, uid, values, context=context)
        #update the currency_id to contract's wage currency, if user do not supply the currency
        if ('currency_id' not in values or not values['currency_id']) and values['contract_id']:
            currency_id = self.pool.get('hr.contract').read(cr, uid, values['contract_id'], ['wage_currency_id'], context=context)['wage_currency_id']
            self.write(cr, uid, new_id, {'currency_id':currency_id[0]}, context=context)
        return new_id

class hr_emppay_ln_alwded(osv.osv):
    _inherit = 'hr.emppay.ln.alwded'
    _columns = {
        'currency_id':fields.many2one('res.currency','Currency'),
        'amount_local':fields.float('Amount Local', digits_compute=dp.get_precision('Payroll')),
    }
    def onchange_amount(self, cr, uid, ids, currency_id,  amount, context=None):
        resu = {'value':{}}
        if currency_id != context.get('default_currency_id'):
            return resu
        if context.get('currency_rate'):
            new_amt = amount / float(context.get('currency_rate'))
            new_amt = float('%.2f' %new_amt)            
            resu['value'].update({'amount_local':new_amt})
        return resu
    def onchange_amount_local(self, cr, uid, ids, currency_id, amount_local, context=None):
        resu = {'value':{}}
        if currency_id != context.get('default_currency_id'):
            return resu
        if context.get('currency_rate'):
            new_amt = amount_local * float(context.get('currency_rate'))
            new_amt = float('%.2f' %new_amt)
            resu['value'].update({'amount':new_amt})
        return resu     
    
class hr_emppay_sheet(osv.osv):
    _inherit = 'hr.emppay.sheet'
    _columns = {
        'currency_id':fields.many2one('res.currency','Currency'),
        'currency_rate':fields.float('Currency Rate', digits=(12,6)),    
    }
    
    def create(self, cr, uid, values, context=None):
        new_id = super(hr_emppay_sheet,self).create(cr, uid, values, context=context)
        #update currency data
        sheet = self.browse(cr, uid, new_id, context=context)
        local_currency = sheet.company_id.currency_id
        vals = {'currency_id':local_currency.id, 'currency_rate':1}
        for slip in sheet.emppay_ids:
            slip_currency = slip.currency_id or slip.contract_id.wage_currency_id
            if slip_currency.id !=  local_currency.id:
                currency_rate = self.pool.get('res.currency')._get_conversion_rate(cr, uid, local_currency, slip_currency, context=context)
                vals = {'currency_id':slip_currency.id, 'currency_rate':currency_rate}
                break
        self.write(cr, uid, [sheet.id], vals, context=context)        
        return new_id
    
    def write(self, cr, uid, ids, vals, context=None):
        resu = super(hr_emppay_sheet, self).write(cr, uid, ids, vals, context=context)
        #handle the currency_rate changing, update the slips        
        if 'currency_id' in vals or 'currency_rate' in vals:
            deal_currency_ids = []
            rate_obj = self.pool.get("res.currency.rate")
            #update res_currency_rate                            
            for sheet in self.browse(cr, uid, ids, context=context):
                if sheet.currency_id.id not in deal_currency_ids:
                    currency_local = sheet.company_id.currency_id
                    currency_rate = currency_local.rate * sheet.currency_rate                
                    rate_ids = rate_obj.search(cr, uid, [('name','=',time.strftime('%Y-%m-%d')), ('currency_id', '=', sheet.currency_id.id)], context=context)
                    if rate_ids:
                        rate_obj.write(cr, uid, rate_ids[0], {'rate':currency_rate}, context=context)
                    else:
                        rate_obj.create(cr, uid, {'name':time.strftime('%Y-%m-%d'), 'rate':currency_rate, 'currency_id':sheet.currency_id.id}, context=context)
                    deal_currency_ids.append(sheet.currency_id.id)
            #recompute related slips based on the new currency rate
            self.recompute(cr, uid, ids, context)
        return resu
    
    def onchange_currency(self, cr, uid, ids, currency_id, context=None):
        resu = {'value':{}}
        if not currency_id:
            return resu
        rate = self.pool.get('res.currency').read(cr, uid, currency_id, ['rate'], context=context)['rate']
        currency_local = None
        if not ids:
            currency_local = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id
        else:
            currency_local = self.browse(cr, uid, ids[0]).company_id.currency_id
        #convert to the rate to the local currency
        resu['value']['currency_rate'] = rate / currency_local.rate
        return resu
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
