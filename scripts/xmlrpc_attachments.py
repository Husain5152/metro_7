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
#dbname = 'metro_0428'
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
def migrate_attachment(att_id):
    # 1. get data
    att = sock.execute(dbname, uid, pwd, 'ir.attachment', 'read', att_id, ['datas'])
 
    data = att['datas']
 
    # Re-Write attachment
    a = sock.execute(dbname, uid, pwd, 'ir.attachment', 'write', [att_id], {'datas': data})
 
# SELECT attachments:
att_ids = sock.execute(dbname, uid, pwd, 'ir.attachment', 'search', [('store_fname','=',False)])
 
cnt = len(att_ids)
i = 0
for id in att_ids: 
    migrate_attachment(id)
    print 'Migrated ID %d (attachment %d of %d)' % (id,i,cnt)
    i = i + 1
 
print 'done...'