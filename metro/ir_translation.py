# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import time
from lxml import etree
from operator import itemgetter

from openerp.osv import fields, osv
from openerp.tools.translate import _
'''
Report base class, the sub class need todo:
1.Add the default value for the 'type' field
2.Add the search fields that the report need
3.Defined the view xml based on the new class
4.define method run_%type% to report the report line data
5.define _pdf_data() method to return the report name in xml
'''
class ir_translation(osv.osv):
    _inherit = "ir.translation"
    '''
    Execute below SQL to do update manually at the first time deploy:
    update ir_translation set is_translated = true where src is not null and src != value
    '''
    def _is_translated(self, cr, uid, ids, fields, args, context):
        res = {}
        for trans in self.read(cr, uid, ids, ['src','value'], context=context):
            if not trans['value'] or trans['src'] == trans['value']:
                res[trans['id']] = False
            else:
                res[trans['id']]= True
        return res

    def _is_translated_search(self, cr, uid, obj, name, args, context=None):
        '''
        @param args: [(u'is_translated', u'=', False)] / [(u'is_translated', u'=', True)]  
        '''        
        if not args:
            return []
        if args[0][2]:
            where = 'value is not null and src != value'
        else:
            #the ids without translation
            where = 'value is null or src = value'
             
        cr.execute('SELECT id FROM ir_translation where ' + where)
        res = cr.fetchall()
        if not res:
            return [('id','=',0)]
        return [('id','in',map(itemgetter(0), res))]
        
    _columns = {
        'is_translated': fields.function(_is_translated,  fnct_search=_is_translated_search, string='Is Translated', type='boolean'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
