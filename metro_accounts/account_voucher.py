# -*- coding: utf-8 -*-
import time
from openerp.report import report_sxw
from openerp.osv import fields, osv
from openerp.addons.metro import utils
    
class account_voucher(osv.osv):
    _inherit = "account.voucher"
    _columns={
              'receipt_number': fields.char('Receipt Number', size=64, help="The reference of this invoice as provided by the partner."),
              #make the memo editable at any state        
              #'name':fields.char('Memo', size=256, readonly=True, states={'draft':[('readonly',False)]}),
              'name':fields.char('Memo', size=256, readonly=False),
              'pay_attach_name': fields.char('Payment Attachment Name', size=64),
              'pay_attach': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file, string="Payment Attachment", type="binary", multi="_get_file",),              
    }
    def action_move_line_create(self, cr, uid, ids, context=None):
        resu = super(account_voucher,self).action_move_line_create(cr, uid, ids, context=context)
        '''
        #remove the auto post, johnw, 10/11/2014
        move_pool = self.pool.get('account.move')
        for voucher in self.browse(cr, uid, ids, context=context):
            if voucher.move_id and voucher.move_id.state == 'draft':
                move_pool.post(cr, uid, [voucher.move_id.id], context={})
        '''
        return resu
    
    def unlink(self, cr, uid, ids, context=None):
        #delete the attachments
        for id in ids:
            utils.field_set_file(self, cr, uid, id, 'pay_attach', None, {'unlink':True}, context=None)
        resu = super(account_voucher, self).unlink(cr, uid, ids, context=context)
        return resu
        
r=account_voucher()
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: