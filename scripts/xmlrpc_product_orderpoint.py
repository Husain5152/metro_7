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
#dbname = 'metro_develop'
#username = 'erpadmin'
#pwd = 'develop'

host = '10.1.1.141'
port = '80'
dbname = 'metro_0716'
username = 'erpadmin'
pwd = 'develop'
#
#host = '10.1.1.140'
#port = '80'
#dbname = 'metro_production'
#username = 'erpadmin'
#pwd = 'erp123'

sock_common = xmlrpclib.ServerProxy ('http://%s:%s/xmlrpc/common'%(host,port))
uid = sock_common.login(dbname, username, pwd)
sock = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/object'%(host,port))
print 'begin...'
#get the product inventory quantity
prod_ids = sock.execute(dbname, uid, pwd, 'product.product', 'search', [])
qtys = sock.execute(dbname, uid, pwd, 'product.product', 'read', prod_ids, ['uom_id','safe_qty'])
for qty in qtys:
    if not qty.get('safe_qty') or qty['safe_qty'] <= 0:
        continue 
    vals = {'product_id':qty['id'],
                            'product_uom':qty['uom_id'][0],
                            'product_min_qty':qty['safe_qty'], 
                            'product_max_qty':0,
                            'warehouse_id':2,
                            'location_id': 14,
                            }
    qtys = sock.execute(dbname, uid, pwd, 'stock.warehouse.orderpoint', 'create', vals)
    print "created for product:%s"%(qty['id'],)
    
print 'done...'