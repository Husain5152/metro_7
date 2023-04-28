# -*- coding: utf-8 -*-

{
    'name': 'Metro Serial',
    'version': '1.0',
    'category': 'Metro',
    "sequence": 14,
    'complexity': "easy",
    'description': """
    """,
    'author': 'Prakhar Bansal',
    'website': 'http://www.prakharbansal.com',
    'depends': ['metro','metro_attachment','metro_partner'],
    'init_xml': [],
	'demo': [],
    'update_xml': [
       "security/metro_security.xml",
       "security/ir.model.access.csv",
       "metro_serial_view.xml"
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
