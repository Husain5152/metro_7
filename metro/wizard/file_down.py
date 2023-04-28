# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (c) 2004-2012 OpenERP S.A. <http://openerp.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import base64
import cStringIO

from openerp.osv import fields,osv
from openerp.tools.translate import _
import xlrd
from xlutils.copy import copy

import os
import logging
_logger = logging.getLogger(__name__)

class file_down(osv.osv_memory):
    _name = "file.down"
    _columns = {
            'filename': fields.char('File Name'),
            'filedata': fields.binary('File', required=True),
    }
    def download_data(self, cr, uid, filename, filedata, context=None):
        fdown_vals = {'filename':filename,'filedata':filedata}
        fid = self.create(cr, uid, fdown_vals, context=context)
        #find the view id
        ir_model_data_obj = self.pool.get('ir.model.data')
        ir_model_data_id = ir_model_data_obj.search(cr, uid, [['model', '=', 'ir.ui.view'], ['name', '=', 'wizard_file_down_view']], context=context)
        if ir_model_data_id:
            view_id = ir_model_data_obj.read(cr, uid, ir_model_data_id, fields=['res_id'])[0]['res_id']
        #goto download action
        return {
            'name': 'Download File',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [view_id],
            'res_model': self._name,
            'context': context,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'res_id': fid,
        } 
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
