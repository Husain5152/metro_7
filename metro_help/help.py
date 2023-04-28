#-*- ecoding: utf-8 -*-
# __author__ = johnw

from osv import fields, osv

class help(osv.osv):
    '''
    Add help on each module
    '''
    _inherit= 'ir.module.module'
    def open_help(self, cr, uid, ids, context=None):
        return True;
#        return {
#            'type':'ir.actions.act_url',
#            'url':'help.php?page='+self.browse(cr, uid, ids, context)[0].name or '',
#            'target':'new',
#        }
help()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

