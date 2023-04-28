# -*- coding: utf-8 -*-

{
    'name': 'Metro Help',
    'version': '1.0',
    'category': 'Metro',
    "sequence": 14,
    'complexity': "easy",
    'description': """
    
        Online help.
    
    """,
    'author': 'Metro Tower Trucks',
    'website': 'http://www.metrotowtrucks.com',
    'depends': ['base','knowledge'],
    'init_xml': [],
    'data' : [
       "help.xml",
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    #web
    "js": ["static/src/js/help.js"],
#    'qweb' : ["static/src/xml/help.xml"],
    'css' : ["static/src/css/help.css",],    
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
