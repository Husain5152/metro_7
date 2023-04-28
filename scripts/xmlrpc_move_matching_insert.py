#!/usr/bin/python
import sys, getopt
import xmlrpclib
'''
host = raw_input('Enter openerp host name : ')
port = raw_input('Enter openerp host port : ')
dbname = raw_input('Enter database name : ')

if dbname == 'metro_production':
    print('Can not perform operation on this database')
    sys.exit(0)

username = raw_input('Enter user name : ')
pwd = raw_input('Enter password : ')
'''
#host = 'localhost'
#port = '9069'
#dbname = 'metro_dev_prod_0328'
#username = 'erpadmin'
#pwd = 'develop'

#host = '10.1.1.141'
#port = '80'
#dbname = 'metro_prod_0328'
#username = 'erpadmin'
#pwd = 'develop'

host = '10.1.1.140'
port = '80'
dbname = 'metro_production'
username = 'erpadmin'
pwd = 'erp123'

sock_common = xmlrpclib.ServerProxy ('http://%s:%s/xmlrpc/common'%(host,port))
uid = sock_common.login(dbname, username, pwd)
sock = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/object'%(host,port))
'''
FIFO module will report error when there no stock in quantity(move in with stock_move.qty_remaining)
This script is to update the stock_move.qty_remaining for the FIFO module having move to match when do stocking out.
My idea is to get the product's qty_available, and then allocate this quantity to the stock_move.qty_remaining of this product, 
the new stock_move will be allocate first, once the qty_available is finished allocated, then this product is finished.
And it will also update the stock_move.price_unit from product.standard_price if move price is empty
'''
ids = sock.execute(dbname, uid, pwd, 'product.product', 'search', [('active','=',True)])
#ids = [1023]
for id in ids:
    #get the product onhand quantity
    prod = sock.execute(dbname, uid, pwd, 'product.product', 'read', id, ['qty_available','standard_price'])
    qty_avail = prod['qty_available']
    prod_price = prod['standard_price']
    if qty_avail <= 0:
        #no hand then continue
        continue
    #get the this product's stock move with done state, all of the move target is stock location, and order by id desc
#    args = [('state','=','done'),('location_dest_id','=',14),('location_id','=',8),('product_id','=',id)]
    args = [('state','=','done'),('location_dest_id','=',14),('product_id','=',id)]
    move_ids = sock.execute(dbname, uid, pwd, 'stock.move', 'search', args , '', '', 'id desc')
    for move_id in move_ids:
        move_info = sock.execute(dbname, uid, pwd, 'stock.move', 'read', move_id, ['product_qty','price_unit'])
        move_qty = move_info['product_qty']
        move_price = move_info['price_unit']
        #get the quantity need to remain
        qty_remaining = (move_qty >= qty_avail) and qty_avail or move_qty
        #since the 'qty_remaining' is a function field with store=True, can not update it by code, use 'note' to update and then update qty_remaining by sql
        move_vals = {'note':qty_remaining}
        #if move price is zero then update it to the product standard price 
        if move_price <= 0:
            move_vals.update({'price_unit':prod_price})
        #update stock_move qty_remaining
        sock.execute(dbname, uid, pwd, 'stock.move', 'write', move_id, move_vals)
        #break once the there are not qty to remain
        qty_avail = qty_avail - qty_remaining
        if qty_avail <= 0:
            break
        
    print 'Updated product:%s'%id

print 'done...'