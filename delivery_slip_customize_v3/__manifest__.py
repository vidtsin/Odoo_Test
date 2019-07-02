{
    'name': 'sale Delivery Slip customized',
    'summary': 'quotation',
    'category': 'product',
    'version': '3.0(Delivery Date)',
    'description': """Print and Send your Sales Order by Post""",
    'depends': ['base', 'stock','sale_management','report_custom_fields'],
    'website': 'http://www.prixgen.com',
    'data': ['report/delivery.xml',
    'views/stock_view.xml'],
    'auto_install': False,
    'application': True,
}