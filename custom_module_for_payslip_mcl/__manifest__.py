{
    'name': 'Document Model',
    'version': '12.0.1.1',
    'category': 'Tools',
    'summary': "This module consists, the customized Templates",
    'depends': ['base','account_tax_python','account','l10n_in','customer_vendor_product_assets_number','hr','addon_fields_for_mcl'],
    'website': 'http://www.prixgen.com',
    'data': [
             'views/report_payslip_document_inherit.xml',
             'views/amt_words.xml',
             ],
    'auto_install': False,
    'application': True,
}
