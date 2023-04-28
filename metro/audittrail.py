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

from openerp import SUPERUSER_ID
from openerp.addons.audittrail.audittrail import audittrail_objects_proxy
from metro import utils

from datetime import datetime
'''
fix the bug of the exception raising when get name if the method is unlink, since data is not existing after unlink, johnw, 10/14/2014
'''
class audittrail_objects_proxy_patch(audittrail_objects_proxy):
    
    def prepare_audittrail_log_line(self, cr, uid, pool, model, resource_id, method, old_values, new_values, field_list=None):
        """
        This function compares the old data (i.e before the method was executed) and the new data
        (after the method was executed) and returns a structure with all the needed information to
        log those differences.

        :param cr: the current row, from the database cursor,
        :param uid: the current user’s ID. This parameter is currently not used as every
            operation to get data is made as super admin. Though, it could be usefull later.
        :param pool: current db's pooler object.
        :param model: model object which values are being changed
        :param resource_id: ID of record to which values are being changed
        :param method: method to log: create, read, unlink, write, actions, workflow actions
        :param old_values: dict of values read before execution of the method
        :param new_values: dict of values read after execution of the method
        :param field_list: optional argument containing the list of fields to log. Currently only
            used when performing a read, it could be usefull later on if we want to log the write
            on specific fields only.

        :return: dictionary with
            * keys: tuples build as ID of model object to log and ID of resource to log
            * values: list of all the changes in field values for this couple (model, resource)
              return {
                (model.id, resource_id): []
              }

        The reason why the structure returned is build as above is because when modifying an existing
        record, we may have to log a change done in a x2many field of that object
        """
        if field_list is None:
            field_list = []
        key = (model.id, resource_id)
        lines = {
            key: []
        }
        # loop on all the fields
        for field_name, field_definition in pool.get(model.model)._all_columns.items():
            if field_name in ('__last_update', 'id'):
                continue
            #if the field_list param is given, skip all the fields not in that list
            if field_list and field_name not in field_list:
                continue
            field_obj = field_definition.column
            if field_obj._type in ('one2many','many2many'):
                # checking if an audittrail rule apply in super admin mode
                if self.check_rules(cr, SUPERUSER_ID, field_obj._obj, method):
                    # checking if the model associated to a *2m field exists, in super admin mode
                    x2m_model_ids = pool.get('ir.model').search(cr, SUPERUSER_ID, [('model', '=', field_obj._obj)])
                    x2m_model_id = x2m_model_ids and x2m_model_ids[0] or False
                    assert x2m_model_id, _("'%s' Model does not exist..." %(field_obj._obj))
                    x2m_model = pool.get('ir.model').browse(cr, SUPERUSER_ID, x2m_model_id)
                    # the resource_ids that need to be checked are the sum of both old and previous values (because we
                    # need to log also creation or deletion in those lists).
                    x2m_old_values_ids = old_values.get(key, {'value': {}})['value'].get(field_name, [])
                    x2m_new_values_ids = new_values.get(key, {'value': {}})['value'].get(field_name, [])
                    # We use list(set(...)) to remove duplicates.
                    res_ids = list(set(x2m_old_values_ids + x2m_new_values_ids))
                    if model.model == x2m_model.model:
                        # we need to remove current resource_id from the many2many to prevent an infinit loop
                        if resource_id in res_ids:
                            res_ids.remove(resource_id)
                    for res_id in res_ids:
                        lines.update(self.prepare_audittrail_log_line(cr, SUPERUSER_ID, pool, x2m_model, res_id, method, old_values, new_values, field_list))
            # if the value value is different than the old value: record the change
            if key not in old_values or key not in new_values or old_values[key]['value'][field_name] != new_values[key]['value'][field_name]:
                #johnw, 01/14/2015, use the user's local time as the datetime value to store into log
                if field_obj._type == 'datetime':
                    new_value_text = key in new_values and new_values[key]['text'].get(field_name)
                    old_value_text = key in old_values and old_values[key]['text'].get(field_name)
                    if new_value_text: 
                        new_value_text = utils.dtstr_utc2local(cr, uid, new_value_text)
                    if old_value_text:
                        old_value_text = utils.dtstr_utc2local(cr, uid, old_value_text)
                    data = {
                          'name': field_name,
                          'new_value': new_value_text,
                          'old_value': old_value_text,
                          'new_value_text': new_value_text,
                          'old_value_text': old_value_text
                    }                                        
                else:
                    data = {
                          'name': field_name,
                          'new_value': key in new_values and new_values[key]['value'].get(field_name),
                          'old_value': key in old_values and old_values[key]['value'].get(field_name),
                          'new_value_text': key in new_values and new_values[key]['text'].get(field_name),
                          'old_value_text': key in old_values and old_values[key]['text'].get(field_name)
                    }
                lines[key].append(data)
        return lines
        
    def process_data(self, cr, uid, pool, res_ids, model, method, old_values=None, new_values=None, field_list=None):
        """
        This function processes and iterates recursively to log the difference between the old
        data (i.e before the method was executed) and the new data and creates audittrail log
        accordingly.

        :param cr: the current row, from the database cursor,
        :param uid: the current user’s ID,
        :param pool: current db's pooler object.
        :param res_ids: Id's of resource to be logged/compared.
        :param model: model object which values are being changed
        :param method: method to log: create, read, unlink, write, actions, workflow actions
        :param old_values: dict of values read before execution of the method
        :param new_values: dict of values read after execution of the method
        :param field_list: optional argument containing the list of fields to log. Currently only
            used when performing a read, it could be usefull later on if we want to log the write
            on specific fields only.
        :return: True
        """
        if field_list is None:
            field_list = []
        # loop on all the given ids
        for res_id in res_ids:
            # compare old and new values and get audittrail log lines accordingly
            lines = self.prepare_audittrail_log_line(cr, uid, pool, model, res_id, method, old_values, new_values, field_list)

            # if at least one modification has been found
            for model_id, resource_id in lines:
                '''
                fix the bug of the exception raising when get name if the method is unlink, since data is not existing after unlink, johnw, 10/14/2014
                '''
                #name = pool.get(model.model).name_get(cr, uid, [resource_id])[0][1]
                #fix begin
                name = ''
                if (model_id, resource_id) in new_values:
                    # the resource is existing then we can get the data
                    name = pool.get(model.model).name_get(cr, uid, [resource_id])[0][1]
                else:
                    #get name from old data
                    #rec_name_column = self._all_columns[self._rec_name].columnv
                    if lines[(model_id, resource_id)]:
                        rec_column_name = pool.get(model.model)._rec_name
                        for line in lines[(model_id, resource_id)]:
                            if line['name'] == rec_column_name:
                                name = line['old_value_text']
                                break
                #fix end
                vals = {
                    'method': method,
                    'object_id': model_id,
                    'user_id': uid,
                    'res_id': resource_id,
                    'name': name,
                }
                if (model_id, resource_id) not in old_values and method not in ('copy', 'read'):
                    # the resource was not existing so we are forcing the method to 'create'
                    # (because it could also come with the value 'write' if we are creating
                    #  new record through a one2many field)
                    vals.update({'method': 'create'})
                if (model_id, resource_id) not in new_values and method not in ('copy', 'read'):
                    # the resource is not existing anymore so we are forcing the method to 'unlink'
                    # (because it could also come with the value 'write' if we are deleting the
                    #  record through a one2many field)
                    vals.update({'method': 'unlink'})
                # create the audittrail log in super admin mode, only if a change has been detected
                if lines[(model_id, resource_id)]:
                    #johnw, 01/14/2014, use UTC now as the log's timestamp, the _defaults in audittrail.py have issues when servre's TZ is not UTC
                    vals['timestamp'] = datetime.utcnow()
                    log_id = pool.get('audittrail.log').create(cr, SUPERUSER_ID, vals)
                    model = pool.get('ir.model').browse(cr, uid, model_id)
                    self.create_log_line(cr, SUPERUSER_ID, log_id, model, lines[(model_id, resource_id)])
        return True
audittrail_objects_proxy_patch()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

