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
#dbname = 'metro_0514'
#username = 'erpadmin'
#pwd = 'develop'

host = '10.1.1.140'
port = '80'
dbname = 'metro_production'
username = 'erpadmin'
pwd = 'erp123'

#host = '10.1.1.141'
#port = '80'
#dbname = 'metro_0506'
#username = 'erpadmin'
#pwd = 'develop'

sock_common = xmlrpclib.ServerProxy ('http://%s:%s/xmlrpc/common'%(host,port))
uid = sock_common.login(dbname, username, pwd)
sock = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/object'%(host,port))
product_code = ['116019-1',
]
for code in product_code:
    new_uom_categ_id = sock.execute(dbname, uid, pwd, 'product.uom.categ', 'create', {'name':'MSP_%s'%code})
    #Meter
    uom_data = {
        'name':'Sheet',
        'category_id':new_uom_categ_id,
        'factor':1,
        'rounding': 0.0001,
#        'uom_type': 'reference',
#        'active': 1,
    }
    sock.execute(dbname, uid, pwd, 'product.uom', 'create', uom_data)
    #Tons
    uom_data = {
        'name':'Ton',
        'category_id':new_uom_categ_id,
        'factor':1,
        'rounding': 0.0001,
        'uom_type': 'bigger',
    }
    sock.execute(dbname, uid, pwd, 'product.uom', 'create', uom_data)    
    print 'Created UOM for %s'%code
print 'done...'