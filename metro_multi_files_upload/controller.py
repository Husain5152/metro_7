# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012-today OpenERP SA (<http://www.openerp.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################
import logging

import openerp
import base64
import xmlrpclib
import simplejson
from openerp.addons.multi_image.controllers.main import Binary_multi
_logger = logging.getLogger(__name__)

class BinaryMulti(Binary_multi):
    @openerp.addons.web.http.httprequest
    def upload_attachment_multi(self, req, callback, model, id, ufiles):
        Model = req.session.model('ir.attachment')
        out = """<script language="javascript" type="text/javascript">
                    var win = window.top.window;
                    win.jQuery(win).trigger(%s, %s);
                </script>"""
        args = {}
        try:
            for ufile in ufiles:
                attachment_id = Model.create({
                    'name': ufile.filename,
                    'datas': base64.encodestring(ufile.read()),
                    'datas_fname': ufile.filename,
                    'res_model': model,
                    'res_id': int(id)
                }, req.context)
                args[ufile.filename] = attachment_id
        except xmlrpclib.Fault, e:
            args = {'error':e.faultCode }
        return out % (simplejson.dumps(callback), simplejson.dumps(args))

# vim:expandtab:tabstop=4:softtabstop=4:shiftwidth=4:
