# -*- coding: utf-8 -*-
import time
from openerp.osv import fields, osv
from openerp.osv.orm import browse_record, browse_null
from openerp.tools.translate import _
import datetime
import openerp.tools as tools
from openerp.addons.metro import utils

class hr_contract_change_si(osv.osv_memory):
    _name = 'hr.contract.change.si'
    _description = 'HR Contract Change SI'
    _columns = {
        'house_rent_fund': fields.float('Individual Housing Fund'),
        'company_house_rent_fund': fields.float('Company Housing Fund'),
        'si_value_ids': fields.one2many('hr.contract.change.si.values','wizard_id',string='SI Values'),
        'contract_ids': fields.many2many('hr.contract', 'rel_contract_change_si_wizard','wz_id','contract_id',string='Contracts'),
    }

    def do_update(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids, context)[0]
        contract_si_obj = self.pool.get('hr.contract.si')
        contract_obj = self.pool.get('hr.contract')
        contract_ids = []
        for contract in wizard.contract_ids:
            contract_ids.append(contract.id)
            for si in contract.si_ids:
                for new_si_value in wizard.si_value_ids:
                    if si.si_id.id ==  new_si_value.si_id.id:
                        contract_si_obj.write(cr, uid, [si.id], {
                            'amount_base': new_si_value.amount_base,
                        })
        contract_obj.write(cr, uid, contract_ids , {
            'house_rent_fund': wizard.house_rent_fund,
            'company_house_rent_fund': wizard.company_house_rent_fund,
        })
        return True
hr_contract_change_si()

class hr_contract_change_si_values(osv.osv_memory):
    _name = 'hr.contract.change.si.values'
    _description = 'HR Contract Change Si Values'
    _columns = {
        'wizard_id': fields.many2one('hr.contract.change.si'),
        'si_id': fields.many2one('hr.emppay.si', string='Social Insurrance'),
        'amount_base': fields.float('Amount'),
    }
hr_contract_change_si_values()