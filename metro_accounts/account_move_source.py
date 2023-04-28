# -*- coding: utf-8 -*-
import time
from openerp.report import report_sxw
from openerp.osv import fields, osv

def get_model_selection(obj, cr, uid, context=None):
    #@return a list of tuples. tuples containing model name and name of the record
    model_pool = obj.pool.get('ir.model')
    ids = model_pool.search(cr, uid, [('name','not ilike','.')])
    res = model_pool.read(cr, uid, ids, ['model', 'name'])
    res.sort(lambda x, y: cmp(x['name'], y['name']))
    return [(r['model'], r['name']) for r in res] +  [('','')] 

class account_move(osv.osv):
    _inherit = "account.move"

    _columns = {
        'source_id': fields.reference('Source', selection=get_model_selection, size=128, select=1),
    }    
    
class account_move_line(osv.osv):
    _inherit = "account.move.line"
    
    def _get_move_lines(self, cr, uid, ids, context=None):
        result = []
        for move in self.pool.get('account.move').browse(cr, uid, ids, context=context):
            for line in move.line_id:
                result.append(line.id)
        return result    
    
    _columns = {
        'source_id': fields.related('move_id','source_id', type='reference', string='Source', selection=get_model_selection, size=128, select=1,  
                                store = {
                                    'account.move': (_get_move_lines, ['source_id'], 20)
                                }),
    }
'''
Entry move source:
采购预付款:purchase.order
采购预付款-自动核销:account.invoice
销售预收款:sale.order
销售预收款-自动核销:account.invoice
凭据:account.invoice: 是否需要链接凭据的相关单据?
付款单:account.voucher: 是否需要链接voucher的相关单据?
出纳-存取款,银行转账,其他收款,其他付款: cash.bank.trans
出纳-员工借款:emp.borrow
出纳-员工报销:emp.reimburse
出入库单,领料单
'''    
'''
采购预付款:purchase.order
Add source_id for purchase prepayment, inherited from:
metro_purchase/purchase_payment.py.purchase_order._prepare_payment_move()
'''
class purchase_order(osv.osv):  
    _inherit = "purchase.order"
    def _prepare_payment_move(self, cr, uid, move_name, order, journal,
                              period, date, description, context=None):
        res = super(purchase_order, self)._prepare_payment_move(cr, uid, move_name, order, journal, period, date, description, context=context)
        res['source_id'] = '%s,%s'%('purchase.order',order.id)
        return res
    
'''
销售预收款:sale.order
Add source_id for sale prepayment, inherited from:
metro_purchase/purchase_payment.py.purchase_order._prepare_payment_move()
'''
class sale_order(osv.osv):  
    _inherit = "sale.order"
    def _prepare_payment_move(self, cr, uid, move_name, sale, journal, period, date, description, context=None):
        res = super(sale_order,self)._prepare_payment_move(cr,uid,move_name,sale,journal,period,date,description,context)
        res['source_id'] = '%s,%s'%('sale.order',sale.id)
        return res

'''
采购预付款-自动核销:account.invoice/销售预收款-自动核销:account.invoice
参考metro_accounts.invoice_payment.py.account_invoice.add_inv_prepay_reconcile_move()
'''
        
'''
凭据
Add source_id for invoice validation
'''
class account_invoice(osv.osv):
    _inherit = "account.invoice"
    def action_move_create(self, cr, uid, ids, context=None):
        resu = super(account_invoice,self).action_move_create(cr, uid, ids, context=context)
        #get the move ids, and update resource_id
        move_obj = self.pool.get('account.move')
        for inv in self.browse(cr, uid, ids, context=context):
            move_obj.write(cr, uid, [inv.move_id.id], {'source_id':'%s,%s'%('account.invoice',inv.id)},context=context)
        return resu    
        
'''
付款单
Add source_id for account voucher
'''        
class account_voucher(osv.osv):
    _inherit = "account.voucher"
    def action_move_line_create(self, cr, uid, ids, context=None):
        resu = super(account_voucher,self).action_move_line_create(cr, uid, ids, context=context)
        move_obj = self.pool.get('account.move')
        for voucher in self.browse(cr, uid, ids, context=context):
            move_obj.write(cr, uid, [voucher.move_id.id], {'source_id':'%s,%s'%('account.voucher',voucher.id)},context=context)
        return resu         
    
'''
出纳-存取款,银行转账,其他收款,其他付款
Add source_id for bank/cash transaction
'''        
class cash_bank_trans(osv.osv):
    _inherit = 'cash.bank.trans'
    def _prepare_payment_move(self, cr, uid, move_name, order, journal,period, context=None):
        res = super(cash_bank_trans,self)._prepare_payment_move(cr, uid, move_name, order, journal,period, context=context)
        res['source_id'] = '%s,%s'%('cash.bank.trans',order.id)
        return res
    
''': cash.bank.trans
出纳-员工借款:emp.borrow
Add source_id for employee borrow
'''        
class emp_borrow(osv.osv):
    _inherit = 'emp.borrow'
    def _prepare_move(self, cr, uid, move_name, order, journal,period, context=None):
        res = super(emp_borrow,self)._prepare_move(cr, uid, move_name, order, journal,period, context=context)
        res['source_id'] = '%s,%s'%('emp.borrow',order.id)
        return res  
    
'''
出纳-员工报销:emp.reimburse
Add source_id for employee reimburse
'''        
class emp_reimburse(osv.osv):
    _inherit = 'emp.reimburse'    
    def _prepare_move(self, cr, uid, move_name, order, journal,period, context=None):
        res = super(emp_reimburse,self)._prepare_move(cr, uid, move_name, order, journal,period, context=context)
        res['source_id'] = '%s,%s'%('emp.reimburse',order.id)
        return res  
    
'''
出入库单,领料单
Add source_id for stock_picking/material_request
modify metro_accounts.stock.py.stock_picking
'''    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: