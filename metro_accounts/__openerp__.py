# -*- coding: utf-8 -*-

{
    'name': 'Metro Accounts',
    'version': '1.0',
    'category': 'Metro',
    'sequence': 14,
    'summary': '',
    'description': """""",
    'author': 'PY Solutions',
    'website': 'PY Solutions',
    'images': [],
    'depends': [
        'metro','account','purchase','account_voucher','account_analytic_plans','metro_purchase','metro_sale'
    ],
    'data':[
        'security/ir.model.access.csv',
       "account_invoice_metro.xml",
       "account_voucher_view.xml",
       "account_invoice_view.xml",
       "invoice_payment_view.xml",
       "invoice_payment_workflow.xml",
       "account_move_view.xml",
       "account_move_source_view.xml",
       "wizard/account_move_batch.xml",
       
       "wizard/rpt_account_cn_gl_view.xml",
       "wizard/rpt_account_cn_detail_view.xml",
       "wizard/rpt_account_cn_detail_predefine_view.xml",
       "wizard/rpt_account_cn_detail_money_view.xml",
       "wizard/rpt_inventory_view.xml",
       "wizard/rpt_account_cn_menu.xml",
       "wizard/rpt_account_partner_view.xml",
       "account_financial_report_view.xml",
       "wizard/account_financial_report_wizard_view.xml",
       
       "account_report.xml",
       "account_analytic_view.xml",
       "metro_account_view.xml",
       "cash_bank_trans_view.xml",
       "emp_borrow_view.xml",
       "emp_reimburse_view.xml",
       
#       "res_config_view.xml",
       "res_company_view.xml",
       "hr_view.xml",
       "res_partner_view.xml",
       "account_move_report.xml",
       
        ],
    'demo': [],
    'test': [],
    "update_xml" : [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtabmartindent:tabstop=4ofttabstop=4hiftwidth=4:
