#!/usr/bin/python
import sys, getopt
import xmlrpclib

host = 'localhost'
port = '9069'
dbname = 'metro_0514'
username = 'erpadmin'
pwd = 'develop'
    
#host = '10.1.4.14'
#port = '9069'
#dbname = 'metro_po141'
#username = 'erpadmin'
#pwd = 'erp123'

#host = '10.0.1.119'
#port = '9069'
##dbname = 'metro_production'
#dbname = 'metro_uat'
#username = 'erpadmin'
#pwd = 'erp123-test'
        
#if dbname == 'metro_production':
#    print('Can not perform operation on this database')
#    sys.exit(0)
            
try:
    sock_common = xmlrpclib.ServerProxy ('http://%s:%s/xmlrpc/common'%(host,port))
    uid = sock_common.login(dbname, username, pwd)
    if not uid:
        print('User login failed, please try again')
        sys.exit(0)
#    sock = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/object'%(host,port), verbose=True, allow_none=True, verbose=True)
    sock = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/object'%(host,port))
except Exception as e:
    print("Invalid Username or Password ...", e)
    sys.exit(0)     
    
def main():
    sock.execute(dbname, uid, pwd, 'order.informer', 'inform', 'purchase.order')
    # for the email template testing begin
#    tmpl_ids = sock.execute(dbname, uid, pwd, 'email.template', 'search', [('name','=','Purchase Order - Waitting Approval')])
#    vals = sock.execute(dbname, uid, pwd, 'email.template', 'generate_email',tmpl_ids[0],107)
    # for the email template testing end
                    
    print 'finished'

if __name__ == "__main__":
   main()
   
#select ean13 from product_product where ean13 is not null
#select ean13 from product_product where ean13 is null
#update product_product set ean13 = null where ean13 is not null   
