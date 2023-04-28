# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
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
import logging

from openerp.osv import osv

class cron_job(osv.osv_memory):  
    _name="cron.job"
    def po_state_update(self,cr,uid,context=None):
        _logger = logging.getLogger(__name__)
        _logger.info('#########po_state_update  begin##########')
        po_obj = self.pool.get('purchase.order')
        '''
                设置收货完毕状态
                对于所有没有shipped的单据，直接调用picking_done()
        '''
        po_ids = po_obj.search(cr, uid, ['&',('shipped', '!=', True),('state','=','approved')])
        po_obj.picking_done(cr, uid, po_ids, context=context)
        _logger.info('#########po_state_update  request to ship pos:%s##########'%po_ids)
            
        '''
                设置完成状态
                是否收货完毕:shipped
                是否付款完毕:paid_done
                是否已开凭据:invoiced
                是否凭证付款完毕
                    因为有预付款的存在，可能出现已经付款完毕，但是凭证没有验证和预付款核销完毕的情况。
                    1）检查相关po_line.invoice_qty,和采购数量相等
                    2）所有关联的凭证只能处于“cancel”和“paid”
                如果满足上述条件，直接调用po.wkf_done()进入发票等待状态或者完成状态
        '''
        po_ids = po_obj.search(cr, uid, ['&',('shipped', '=', True),('state','=','approved')])
        done_ids = []
        for po in po_obj.browse(cr, uid, po_ids, context=context):
            need_done = False
            #only the po have invoices and full paid then need to check the invoice detail
            if po.invoiced and po.paid_done:
                need_check = True
                for po_line in po.order_line:
                    if po_line.product_qty > po_line.invoice_qty:
                        #no invoice quantity completely, then can not be done
                        need_check = False
                        break
                if need_check:
                    for inv in po.invoice_ids:
                        if inv.state not in('cancel', 'paid'):
                            #if there are invoices with other states, then that invoices need to process to cancel or paid, then the purchase order can be done
                            need_check = False
                            break
                #po can be done
                if need_check:
                    po_obj.wkf_done(cr, uid, [po.id], context=context)
                    done_ids.append(po.id)
        _logger.info('#########po_state_update  done pos:%s##########'%done_ids)
        _logger.info('#########po_state_update  end##########')
                    
cron_job()  