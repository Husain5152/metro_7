# -*- coding: utf-8 -*-
import time
from openerp.report import report_sxw
from openerp.osv import fields, osv
    
class account_invoice(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(account_invoice, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'serials': self.serials,
        })
    
    def serials(self,inv_line):
        serial_ids = []
        for so_ln in inv_line.sale_lines:
            serial_ids += so_ln.serial_ids
        if not serial_ids:
            return False
        else:
            val =  ', '.join(map(lambda x: x.serial, serial_ids))
            return val
        
report_sxw.report_sxw(
    'report.account.invoice.metro',
    'account.invoice',
    'metro_accounts/account_invoice_metro.rml',
    parser=account_invoice
)

    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: