# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP S.A. <http://www.openerp.com>
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
import logging
import time

from openerp.osv import fields, osv
from openerp.tools.translate import _
from datetime import datetime
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.addons.base.ir.ir_cron import _intervalTypes
import traceback
from openerp import netsvc
import sys

def str2tuple(s):
    return eval('tuple(%s)' % (s or ''))

_logger = logging.getLogger(__name__)

class ir_cron(osv.osv):
    _name = "ir.cron"
    _inherit = ['ir.cron', 'mail.thread']
    def manual_run(self, cr, uid, ids, context):
#        cron_id = ids[0]
#        cron_data = self.browse(cr, uid, cron_id, context=context)
#        args = str2tuple(cron_data.args)
#        model = self.pool.get(cron_data.model)
#        if model and hasattr(model, cron_data.function):
#            method = getattr(model, cron_data.function)
#            method(cr, uid, *args)
        cron = self.read(cr, uid, ids[0], context=context)
        cron['user_id'] = cron['user_id'][0]
        self._process_job( cr, cron, cr, force_run = True)
        return True
    '''
    1.datetime.utcnow() 
    2.Log the cron running message and exception message
    3.Add 'force_run' parameter for manual running
    '''
    def _process_job(self, job_cr, job, cron_cr, force_run=False):
        """ Run a given job taking care of the repetition.

        :param job_cr: cursor to use to execute the job, safe to commit/rollback
        :param job: job to be run (as a dictionary).
        :param cron_cr: cursor holding lock on the cron job row, to use to update the next exec date,
            must not be committed/rolled back!
        """
        try:
            #change to utcnow, johnw, 11/15/2014
            #now = datetime.now()
            now = datetime.utcnow() 
            nextcall = datetime.strptime(job['nextcall'], DEFAULT_SERVER_DATETIME_FORMAT)
            numbercall = job['numbercall']

            ok = False
            while force_run or (nextcall < now and numbercall):
                if numbercall > 0:
                    numbercall -= 1
                if not ok or job['doall']:
                    try:
                        call_log = self._callback(job_cr, job['user_id'], job['model'], job['function'], job['args'], job['id'])
                        self.message_post(cron_cr, job['user_id'], job['id'], 
                                          type='comment', subtype='mail.mt_comment', 
                                          subject='Runned at %s'%(datetime.now()),
                                          content_subtype="plaintext",
                                          body=call_log)
                    except Exception,e:
                        formatted_info = "".join(traceback.format_exception(*(sys.exc_info())))
                        self.message_post(cron_cr, job['user_id'], job['id'], 
                                          type='comment', subtype='mail.mt_comment', 
                                          subject='Runned with exception at %s'%(datetime.now()),
                                          content_subtype="plaintext",
                                          body=formatted_info)
                        
                if numbercall:
                    nextcall += _intervalTypes[job['interval_type']](job['interval_number'])
                ok = True
                if force_run:
                    #force_run can only run one time
                    force_run = False
            addsql = ''
            if not numbercall:
                addsql = ', active=False'
            cron_cr.execute("UPDATE ir_cron SET nextcall=%s, numbercall=%s"+addsql+" WHERE id=%s",
                       (nextcall.strftime(DEFAULT_SERVER_DATETIME_FORMAT), numbercall, job['id']))

        finally:
            job_cr.commit()
            cron_cr.commit()
    '''
    1.return the cron running log
    2.raise the original exception
    '''
    def _callback(self, cr, uid, model_name, method_name, args, job_id):
        """ Run the method associated to a given job

        It takes care of logging and exception handling.

        :param model_name: model name on which the job method is located.
        :param method_name: name of the method to call when this job is processed.
        :param args: arguments of the method (without the usual self, cr, uid).
        :param job_id: job id.
        """
        args = str2tuple(args)
        model = self.pool.get(model_name)
        call_log = ''
        if model and hasattr(model, method_name):
            method = getattr(model, method_name)
            try:
                log_depth = (None if _logger.isEnabledFor(logging.DEBUG) else 1)
                netsvc.log(_logger, logging.DEBUG, 'cron.object.execute', (cr.dbname,uid,'*',model_name,method_name)+tuple(args), depth=log_depth)
                start_time = time.time()
                call_resu = method(cr, uid, *args)
                if call_resu:
                    call_log += "return result:\n" + str(call_resu) + "\n"
                end_time = time.time()    
                msg = '%.3fs (%s, %s)' % (end_time - start_time, model_name, method_name)         
                call_log += msg + "\n"       
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug(msg)                    
                return call_log
            except Exception, e:
                self._handle_callback_exception(cr, uid, model_name, method_name, args, job_id, e)
                #raise the original exception, 11/15/2015, johnw   
                raise
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
