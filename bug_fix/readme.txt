1.Fix: Invoicing an order as a fixed price or percentage deposit doesn’t work
bug page:
http://bazaar.launchpad.net/~openerp-dev/openobject-addons/trunk-bug-1098514-hip/revision/8495
fie list:
sale_make_invoice_advance.py
reason:
casued by the method parameter name , should be 'uom', it is 'uom_id' now

2.ir_cron.py
_process_job()中取现在时间应该改为utc时间,否则会造成下次运行时间不对

3.stock_partial_picking.py
增加'material.request'到line#115的模型类型检查,保证领料单正常运行

4.view_form.js
将one2many上面的表格改为可以排序的

5.Solve the from and login email user variance issue
enhance the mail sending logic, to handle the login and from address not mathcing issue
if from and login user is different, then to try to send using smtp_user again

6.mail_mail.py
line#304, add 'raise e' to thow the exception to user
