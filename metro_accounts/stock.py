# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP SA (<http://openerp.com>).
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
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp import netsvc
from openerp import tools
from openerp.tools import float_compare, DEFAULT_SERVER_DATETIME_FORMAT

  
class stock_picking(osv.osv):
    _inherit = "stock.picking"
    def action_done(self, cr, uid, ids, context=None):
        resu = super(stock_picking,self).action_done(cr, uid, ids, context=context)
        actmv_obj = self.pool.get('account.move')
        inv_model={'out':'stock.picking.out', 'in':'stock.picking.in', 'internal':'stock.picking', 'mr':'material.request', 'mrr':'material.request'}
        for pick_id in ids:
            #merge stock valuation account moves
            self.merge_pick_moves(cr, uid, pick_id, context)
        #since by above merging, the pick.account_move_ids were changed, so need another loop to ge the new data
        for pick in self.browse(cr, uid, ids, context=context):
            #update account move's source_id
            if pick.account_move_ids:
                actmv_ids = [mv.id for mv in pick.account_move_ids]
                source_id = '%s,%s'%(inv_model.get(pick.type),pick.id)
                actmv_obj.write(cr, uid, actmv_ids, {'source_id':source_id})
                            
        return resu
    
    #merge the account moves of one picking,since the account move are generated one by one per stock move
    def merge_pick_moves(self, cr, uid, picking_id, context):
        '''
        Merge the generated stocking journal account moves by stock move ,
        generated on stock_move.action_done()-->_create_product_valuation_moves()
        
        Rule:
        *State: draft
        *Same data: with same ref,period_id,journal_id,company_id
        *journal_id.type: stock
        Result:
        --same: ref,period_id,journal_id,company_id
        //--date: the max of the moves
        //--narration: combine all of the move's narration together
        --merge:line_id        
        '''

        '''
        stock_journal_id = self.pool.get('ir_property').get(cr, uid, 'property_stock_journal', 'product.category',context=context)
        
        property_stock_valuation_account_id,product.category
        
        property_stock_account_output, product.template
        property_stock_account_input, product.template
        
        property_stock_account_output_categ, product.category
        property_stock_account_input_categ, product.category
        '''
        if isinstance(picking_id, (int, long)):
            pick = self.browse(cr, uid, picking_id,context=context)
        else:
            pick = picking_id
        #only do the merging when there more than one stocking moves to this picking
        if not pick.account_move_ids or len(pick.account_move_ids) <= 1:
            '''
            #remove the auto post, johnw, 10/11/2014
            move_ids = [move.id for move in pick.account_move_ids]
            if move_ids:
                self.pool.get('account.move').post(cr, uid, move_ids, context=context)
            '''
            return        
        # pick one product to get the account configuration
        product_id = pick.move_lines[0].product_id.id
        accounts = self.pool.get('product.product').get_product_accounts(cr, uid, product_id, context)
        '''
                return {
            'stock_account_input': stock_input_acc,
            'stock_account_output': stock_output_acc,
            'stock_journal': journal_id,
            'property_stock_valuation_account_id': account_valuation
        }
        '''
        new_moves = {}
        unlink_move_ids = []
        for move in pick.account_move_ids:
            #only the draft's stock move can be merge
            if move.state != 'draft' or move.journal_id.id != accounts['stock_journal']:
                continue
            #get the account move values
            move_key = '%s-%s-%s-%s'%(move.ref,move.period_id.id,move.journal_id.id,move.company_id.id)
            move_vals = {}
            if move_key not in new_moves:
                move_vals = {'picking_id':pick.id,
                             'ref':move.ref,
                             'period_id':move.period_id.id,
                             'journal_id':move.journal_id.id,
                             'company_id':move.company_id.id,
                             'line_id':[],
                             'valuation_line_id':[],}
                new_moves.update({move_key:move_vals})
            else:
                move_vals = new_moves.get(move_key)
                #get the move lines
                
            for move_line in move.line_id:
                if move_line.quantity == 0.0:
                    continue
                if move_line.account_id.id == accounts['property_stock_valuation_account_id']:
                    '''
                    #merge the stock valuation values to one line
                    stock_valuation_line = {}
                    if 'stock_valuation_line' not in move_vals:
                        stock_valuation_line = {
                            'name': pick.name, 
                            'ref': pick.name,
                            'date': time.strftime('%Y-%m-%d'),
                            'partner_id': move_line.partner_id.id,
                            'credit': 0,
                            'debit': 0,
                            'account_id': move_line.account_id.id,
                            }
                        move_vals.update({'stock_valuation_line':stock_valuation_line});
                    else:
                        stock_valuation_line = move_vals.get('stock_valuation_line')
                    stock_valuation_line['credit'] += move_line.credit
                    stock_valuation_line['debit'] += move_line.debit
                    '''
                    #add valuation move lines
                    new_move_line = {
                        'name': move_line.name,
                        'product_id': move_line.product_id.id,
                        'quantity': move_line.quantity,
                        'product_uom_id': move_line.product_uom_id.id, 
                        'ref': move_line.ref,
                        'date': time.strftime('%Y-%m-%d'),
                        'partner_id': move_line.partner_id.id,
                        'credit': move_line.credit,
                        'debit': move_line.debit,
                        'account_id': move_line.account_id.id,
                        'analytic_account_id': move_line.analytic_account_id.id,
                        }
                    
                    move_vals.get('valuation_line_id').append((0, 0, new_move_line))                    
                else:
                    #add other move lines for the stock in/out account
                    new_move_line = {
                        'name': move_line.name,
                        'product_id': move_line.product_id.id,
                        'quantity': move_line.quantity,
                        'product_uom_id': move_line.product_uom_id.id, 
                        'ref': move_line.ref,
                        'date': time.strftime('%Y-%m-%d'),
                        'partner_id': move_line.partner_id.id,
                        'credit': move_line.credit,
                        'debit': move_line.debit,
                        'account_id': move_line.account_id.id,
                        'analytic_account_id': move_line.analytic_account_id.id,
                        }
                    
                    move_vals.get('line_id').append((0, 0, new_move_line))
            if len(move_vals.get('line_id')) > 0:
                unlink_move_ids.append(move.id)
        #if move count did not change then return directly
        if len(new_moves) == len(unlink_move_ids):
            return
        move_obj = self.pool.get('account.move')
        #create the new moves
        new_move_ids = []
        for new_move_vals in new_moves.values():
            if len(move_vals.get('line_id')) <= 0:
                continue
            #new_move_vals.get('line_id').append((0,0,new_move_vals['stock_valuation_line']))
            line_ids = []
            if pick.type in (u'out',u'mr'):
                line_ids =  new_move_vals['valuation_line_id'] + new_move_vals.get('line_id') 
            else:
                line_ids =  new_move_vals.get('line_id') + new_move_vals['valuation_line_id']
            if not line_ids:
                continue
            new_move_vals['line_id'] = line_ids
            new_move_id = move_obj.create(cr, uid, new_move_vals, context=context)
            new_move_ids.append(new_move_id)
        #deleted the merged moves
        if unlink_move_ids:
            move_obj.unlink(cr, uid, unlink_move_ids, context=context)
        '''    
        #remove the auto post, johnw, 10/11/2014
        #post new move
        if new_move_ids:
            move_obj.post(cr, uid, new_move_ids, context=context)
        '''

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
