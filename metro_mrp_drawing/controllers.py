# -*- coding: utf-8 -*-
import openerp.addons.web.http as http
from werkzeug.wrappers import Response
import urllib
import urllib2
def content_disposition(filename, req):
    filename = filename.encode('utf8')
    escaped = urllib2.quote(filename)
    browser = req.httprequest.user_agent.browser
    version = int((req.httprequest.user_agent.version or '0').split('.')[0])
    if browser == 'msie' and version < 9:
        return "attachment; filename=%s" % escaped
    elif browser == 'safari':
        return "attachment; filename=%s" % filename
    else:
        return "attachment; filename*=UTF-8''%s" % escaped
class Drawing_Order_Print_PDF(http.Controller):
    _cp_path = '/web/export/drawing_order_print_pdf'
    @http.httprequest
    def index(self, request, file_name, file_data):
        #pdf_data = open(file_data,'rb').read()
        #response = Response(pdf_data)
        #response = Response(pdf_data)
        pdf_file = open(file_data,'rb')
        #dump_stream = openerp.service.db.dump_db(backup_db, None, backup_format)
        #response = werkzeug.wrappers.Response(dump_stream, headers=headers, direct_passthrough=True)

        response = Response(pdf_file, direct_passthrough=True)
        response.headers['Content-Type'] = 'application/pdf'
        #response.headers['Content-Disposition'] = 'attachment; filename="%s.pdf"'%file_name
        response.headers['Content-Disposition'] = content_disposition(file_name, request)
        return response
