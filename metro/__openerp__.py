# -*- coding: utf-8 -*-

{
    'name': 'Metro',
    'version': '1.0',
    'category': 'Metro',
    "sequence": 14,
    'complexity': "easy",
    'description': """
    
        This module contains the common configurations needed by group of 
        Metro Modules.
    
    """,
    'author': 'Metro Tower Trucks',
    'website': 'http://www.metrotowtrucks.com',
    'depends': ['base','email_template','metro_web'],
    'init_xml': [],
    'data' : [
       "ir_actions_view.xml",
       "metro_menu.xml",
	   "security/metro.xml",
       "order_informer.xml",
       "cron_job_data.xml",
       "ir_cron_view.xml",
       "workflow_view.xml",
       "wizard/confirm_message_view.xml",       
        'wizard/file_down_view.xml',
        'rpt_base_view.xml',
        'ir_translation_view.xml',
        "warning_view.xml",
        'res_users_view.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    #web
    "js": ["static/src/js/metro.js"],
    'qweb' : ["static/src/xml/lang_switch.xml",
              "static/src/xml/base.xml",
              ],
    'css' : ["static/src/css/lang_switch.css",
             "static/src/css/metro.css",],    
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
