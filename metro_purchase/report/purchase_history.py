'''
Created on 18-01-2016

@author: Khai Hoang
'''
import time
from openerp.report import report_sxw
from openerp.osv import osv
from openerp import pooler

class purchase_history_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(purchase_history_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time})
        
report_sxw.report_sxw('report.purchase.history.new.product','purchase.history.new.product.group','addons/metro_purchase/report/purchase_history_new_product.rml',parser=purchase_history_report, header='internal')
report_sxw.report_sxw('report.purchase.history.supplier.change','purchase.history.supplier.change.group','addons/metro_purchase/report/purchase_history_supplier_change.rml',parser=purchase_history_report, header='internal')
report_sxw.report_sxw('report.purchase.history.price.change','purchase.history.price.change.group','addons/metro_purchase/report/purchase_history_price_change.rml',parser=purchase_history_report, header='internal')