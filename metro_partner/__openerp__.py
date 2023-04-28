{
    'name': 'Metro Partner',
    'version': '1.0',
    'category': 'Metro',
    'description': """
    
        
        """,
        
        
    'author': 'PY Solutions',
    'maintainer': 'PY Solutions',
    'website': 'http://www.pysolutions.com',
    'depends': ["metro", "base", "mail", "sale", "purchase"],
    'init_xml': [],
    'update_xml': [
	'security/ir.model.access.csv',
	'partner_view.xml',
    ],
    'demo_xml': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
