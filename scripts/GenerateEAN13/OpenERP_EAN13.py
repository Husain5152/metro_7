#!/usr/bin/python
import sys, getopt
import xmlrpclib
        
def usage():
    print '''-H hostname
-P port
-D database_name
-U username
-p password
-h print this help'''   

#deal the command arguments
opts, args = getopt.getopt(sys.argv[1:], 'H:P:D:U:p:h')
for op, value in opts:
    if op == "-H":
        host = value
    if op == "-P":
        port = value
    if op == "-D":
        dbname = value
    if op == "-U":
        username = value
    if op == "-p":
        pwd = value
    if op == "-h":
        pwd = value
        usage()
        sys.exit()     
     
if not host:
    host = raw_input('Enter Host name : ')
if not port:
    port = raw_input('Enter Port name : ')
if not dbname:
    dbname = raw_input('Enter Database name : ')
if not username:
    username = raw_input('Enter User name : ')
if not pwd:
    pwd = raw_input('Enter Password : ')
    
if dbname == 'metro_production':
    print('Can not perform operation on this database')
    sys.exit(0)
            
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
    product_model = sock.execute(dbname, uid, pwd, 'ir.model', 'search', [('model', '=', 'product.product')])
    if product_model:
        product_ids = sock.execute(dbname, uid, pwd, 'product.product', 'search', [])
        sock.execute(dbname, uid, pwd, 'product.product', 'generate_ean13', product_ids)
#        for id in product_ids:
#            sock.execute(dbname, uid, pwd, 'product.product', 'generate_ean13', [id])
#            print "generated, product_id:%s"%id
    print '%s products were updated with ean13'%len(product_ids)

if __name__ == "__main__":
   main()
   
#select ean13 from product_product where ean13 is not null
#select ean13 from product_product where ean13 is null
#update product_product set ean13 = null where ean13 is not null   
