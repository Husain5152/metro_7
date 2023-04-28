# -*- coding: utf-8 -*-

{
    'name': 'Metro Multi Files upload',
    'version': '1.0',
    'category': 'Metro',
    "sequence": 14,
    'complexity': "easy",
    'description': """
    
    """,
    'author': 'Metro Tower Trucks',
    'website': 'http://www.metrotowtrucks.com',
    'depends': ['base'],
    'init_xml': [],
    'data' : [],
    'installable': True,
    'auto_install': False,
    'application': True,
    #web
    "js": ["static/src/js/metro_multi_files_upload.js"],
    'qweb' : ["static/src/xml/file_multi.xml"],
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
