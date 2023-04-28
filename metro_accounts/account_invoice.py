# -*- coding: utf-8 -*-
import time
from openerp.report import report_sxw
from openerp.osv import fields, osv

class account_invoice(osv.osv):
    _inherit = "account.invoice"
    
    #set the internal_number to empty, then user can delete the invoice after user set invoice to draft from cancel state
    def action_cancel(self, cr, uid, ids, context=None):
        resu = super(account_invoice,self).action_cancel(cr, uid, ids, context)
        self.write(cr, uid, ids, {'internal_number':False})
        return resu
    
    def unlink(self, cr, uid, ids, context=None):   
        #get the picking ids first
        pick_ids = self.pool.get('stock.picking').search(cr,uid,[('invoice_id','in',ids),('invoice_state','=','invoiced')],context=context)
        #do deletion
        resu = super(account_invoice,self).unlink(cr, uid, ids, context=context)
        #update the related picking invoice state
        self.pool.get('stock.picking').write(cr, uid, pick_ids, {'invoice_state':'2binvoiced'},context=context)
        return resu
    def action_move_create(self, cr, uid, ids, context=None):
        resu = super(account_invoice,self).action_move_create(cr, uid, ids, context=context)
        #get the move ids, and unpost them
        move_obj = self.pool.get('account.move')
        invs = self.browse(cr, uid, ids, context=context)
        move_ids = [inv.move_id.id for inv in invs if inv.move_id.state == 'posted']
        if move_ids:
            move_obj.button_cancel(cr, uid, move_ids, context)
        return resu
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

class account_invoice_line(osv.osv):
    _inherit = "account.invoice.line"
    _columns = {
        'sale_lines': fields.many2many('sale.order.line', 'sale_order_line_invoice_rel', 'invoice_id', 'order_line_id', 'Sale Order Lines', readonly=True),}