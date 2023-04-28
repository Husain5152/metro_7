# -*- coding: utf-8 -*-

import ast
import base64
import csv
import glob
import itertools
import logging
import operator
import datetime
import hashlib
import os
import re
import simplejson
import time
import urllib
import urllib2
import urlparse
import xmlrpclib
import zlib
from xml.etree import ElementTree
from cStringIO import StringIO

import babel.messages.pofile
import werkzeug.utils
import werkzeug.wrappers
try:
    import xlwt
except ImportError:
    xlwt = None

import openerp
import openerp.modules.registry
from openerp.tools.translate import _

import openerp.addons.web.http as http
import datetime
import openerp.tools as tools
from datetime import timedelta
openerpweb = http
class View(openerpweb.Controller):
    _cp_path = "/web/view"

    @openerpweb.jsonrequest
    def add_custom(self, req, view_id, arch):
        CustomView = req.session.model('ir.ui.view.custom')
        CustomView.create({
            'user_id': req.session._uid,
            'ref_id': view_id,
            'arch': arch
        }, req.context)
        return {'result': True}

    @openerpweb.jsonrequest
    def undo_custom(self, req, view_id, reset=False):
        CustomView = req.session.model('ir.ui.view.custom')
        vcustom = CustomView.search([('user_id', '=', req.session._uid), ('ref_id' ,'=', view_id)],
                                    0, False, False, req.context)
        if vcustom:
            if reset:
                CustomView.unlink(vcustom, req.context)
            else:
                CustomView.unlink([vcustom[0]], req.context)
            return {'result': True}
        return {'result': False}
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
    
class Reports(View):
    _cp_path = "/web/report"
    POLLING_DELAY = 0.25
    TYPES_MAPPING = {
        'doc': 'application/vnd.ms-word',
        'html': 'text/html',
        'odt': 'application/vnd.oasis.opendocument.text',
        'pdf': 'application/pdf',
        'sxw': 'application/vnd.sun.xml.writer',
        'xls': 'application/vnd.ms-excel',
    }

    @openerpweb.httprequest
    def index(self, req, action, token):
        action = simplejson.loads(action)

        report_srv = req.session.proxy("report")
        context = dict(req.context)
        context.update(action["context"])

        report_data = {}
        report_ids = context["active_ids"]
        if 'report_type' in action:
            report_data['report_type'] = action['report_type']
        if 'datas' in action:
            if 'ids' in action['datas']:
                report_ids = action['datas'].pop('ids')
            report_data.update(action['datas'])

        report_id = report_srv.report(
            req.session._db, req.session._uid, req.session._password,
            action["report_name"], report_ids,
            report_data, context)

        report_struct = None
        while True:
            report_struct = report_srv.report_get(
                req.session._db, req.session._uid, req.session._password, report_id)
            if report_struct["state"]:
                break

            time.sleep(self.POLLING_DELAY)

        report = base64.b64decode(report_struct['result'])
        if report_struct.get('code') == 'zlib':
            report = zlib.decompress(report)
        report_mimetype = self.TYPES_MAPPING.get(
            report_struct['format'], 'octet-stream')
        file_name = action.get('name', 'report')
        if 'name' not in action:
            reports = req.session.model('ir.actions.report.xml')
            res_id = reports.search([('report_name', '=', action['report_name']),],
                                    0, False, False, context)
            if len(res_id) > 0:
                file_name = reports.read(res_id[0], ['name'], context)['name']
            else:
                file_name = action['report_name']
        ########################################################
        # PATCH TO CHANGE TASK LIST FILE NAME
        if context['active_model'] == 'task.print':
            model1 =req.session.model(context['active_model'])
            read=model1.read(context['active_id'],[],context)
            task_day = read['task_day']
            group_name = ''
            if action['report_name']  == 'task.group.by_team_full'\
                    or action['report_name']  == 'task.group.by_team_brief'\
                    or action['report_name']  == 'task.group.by_team_issue':
                group_name = 'Team'
            elif action['report_name'] == 'task.group.by_employee_full'\
                    or action['report_name'] == 'task.group.by_employee_brief'\
                    or action['report_name'] == 'task.group.by_employee_issue':
                group_name = 'Employee'
            elif action['report_name'] == 'task.group.by_assignee_full'\
                    or action['report_name'] == 'task.group.by_assignee_brief'\
                    or action['report_name'] == 'task.group.by_assignee_issue':
                group_name = 'Assignee'
            group_ids = context.get('group_ids',False)
            task_group_obj = req.session.model('task.group')
            task_group = task_group_obj.read(group_ids[0],[],context)
            if task_group:
                group_name = task_group['name']
            if task_day:
                date_start = task_day
                date_end = (datetime.datetime.strptime(task_day, tools.DEFAULT_SERVER_DATE_FORMAT) + timedelta(days = 7)).strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
            else:
                date_start = datetime.datetime.utcnow().strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
                date_end = (datetime.datetime.utcnow() + timedelta(days = 7)).strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
            if date_start and date_end:
                if action['report_name'] == 'task.group.by_team_full':
                    file_name = 'DailyReport_%s_%s-%s' % (group_name, date_start, date_end)
                elif action['report_name'] == 'task.group.by_employee_full':
                    file_name = 'DailyReport_%s_%s-%s' % (group_name, date_start, date_end)
                elif action['report_name'] == 'task.group.by_assignee_full':
                    file_name = 'DailyReport_%s_%s-%s' % (group_name, date_start, date_end)
                elif action['report_name'] == 'task.group.by_assignee_brief':
                    file_name = 'TaskList_%s_%s' % (group_name,date_start)
                elif action['report_name'] == 'task.group.by_employee_brief':
                    file_name = 'TaskList_%s_%s' % (group_name,date_start)
                elif action['report_name'] == 'task.group.by_team_brief':
                    file_name = 'TaskList_%s_%s' % (group_name,date_start)
                elif action['report_name'] in ['task.group.by_team_issue',
                                               'task.group.by_employee_issue',
                                               'task.group.by_assignee_issue']:
                    file_name = 'IssueDrawing_%s' % (group_name)
        # PATCH END
        #########################################################
        else:
            # HoangTK - 08/03/2016 - Fix use object name as report name
             action_context = context
             if action_context.has_key('active_model') and action_context.has_key('active_id'):
                 action_active_model = action_context.get('active_model', '')
                 action_active_ids = action_context.get('active_ids', [])
                 if action_active_model and action_active_ids:
                     # Use built-in ORM method to get data from DB
                     m = req.session.model(action_active_model)
                     r = m.read(action_active_ids, False, context)
                     # Parse result to create a better filename
                     for i, item in enumerate(r):
                         if item.has_key('name'):
                             if i == 0:
                                 file_name = ('%s-%s') % (file_name, item['name'])
                             else:
                                 file_name = ('%s-%s') % (file_name, item['name'])
            # HoangTK - 08/03/2016 - Fix use object name as report name
        file_name = '%s.%s' % (file_name, report_struct['format'])

        return req.make_response(report,
             headers=[
                 ('Content-Disposition', content_disposition(file_name, req)),
                 ('Content-Type', report_mimetype),
                 ('Content-Length', len(report))],
             cookies={'fileToken': int(token)})

# vim:expandtab:tabstop=4:softtabstop=4:shiftwidth=4:
