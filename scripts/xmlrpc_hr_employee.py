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
host = 'localhost'
port = '9069'
dbname = 'metro_develop'
username = 'erpadmin'
pwd = 'develop'

#host = '10.1.1.141'
#port = '80'
#dbname = 'metro_production'
#username = 'erpadmin'
#pwd = 'erp123'

sock_common = xmlrpclib.ServerProxy ('http://%s:%s/xmlrpc/common'%(host,port))
uid = sock_common.login(dbname, username, pwd)
sock = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/object'%(host,port))
ids = sock.execute(dbname, uid, pwd, 'hr.employee', 'search', [])
for id in ids:
    sock.execute(dbname, uid, pwd, 'hr.employee', 'write', [id],{'emp_code':'%03d'%id})
    print 'Updated emp:%s'%id

print 'done...'