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
#dbname = 'metro_1125'
#username = 'erpadmin'
#pwd = 'develop'

#host = '10.1.1.141'
#port = '80'
#dbname = 'metro_test'
#username = 'erpadmin'
#pwd = 'erp123-test'
#
host = '10.1.1.140'
port = '80'
dbname = 'metro_production'
username = 'erpadmin'
pwd = 'erp123'

sock_common = xmlrpclib.ServerProxy ('http://%s:%s/xmlrpc/common'%(host,port))
uid = sock_common.login(dbname, username, pwd)
sock = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/object'%(host,port))
print 'begin...'
#get the product inventory quantity
prod_ids = sock.execute(dbname, uid, pwd, 'product.product', 'search', [])
cnt = 0
dealed_ids = []
for prod_id in prod_ids:
    images = sock.execute(dbname, uid, pwd, 'product.product', 'read', [prod_id], ['image','image_medium','image_small'])
    cnt += 1
    dealed_ids.append(prod_id)
    print 'done: %s'%(cnt,)
#    if cnt >= 500:
#        break
    
print dealed_ids    
print 'done...'