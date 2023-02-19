{
    'name': "Sale Order Line Html Description",
    'version': "15.0.1",
    'category': "Sales",
    'summary': """Sale Order Line Html Description | Sale Order Line Colour Description
        | product description colour | product description html | html product description
        | sale order line wysiwyg description | product wysiwyg description
        | sale report colour | sale report product description colour | sale report description in colour
        | sale order line description styles | sale report styles | sale report wysiwyg
        | product description styles
    """,
    'author': "Javier Fernández",
    'website': "https://asdelmarketing.com",
    'license': 'OPL-1',
    'price': 9.99,
    'currency': 'EUR',
    'images': ['static/description/thumbnail.gif'],
    'data': [
        'views/sale_order_views.xml',
        'views/product_template_views.xml',
        'report/sale_order_report.xml',
    ],
    'license': 'AGPL-3',
    'depends': [
        'web',
        'sale'
    ],
    'installable': True,
}