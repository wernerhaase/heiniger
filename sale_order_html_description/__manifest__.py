# -*- coding: utf-8 -*-


{
    'name': "Sale order Line Html Description",
    'summary': """
        Sale Order Line Html Description""",
    'description': """
              Sale Order Line Html Description""",

    'author': 'Ashish Thomas',
    'maintainer': 'Ashish Thomas',
    'category': 'Sales',
    'version': "19.0.1.0.0",
    'license': 'AGPL-3',
    'depends': [
        'sale','sale_project','account','html_editor'
    ],
    'data': [

        'views/sale_order.xml',
        'views/account_move.xml',
        'data/accounting_cleanup_server_actions.xml',

    ],
    'assets': {
        'web.assets_backend': [
            'sale_order_html_description/static/src/js/sale_order_line_html_text.js',
            'sale_order_html_description/static/src/xml/sale_order_line_html_text.xml',
            'sale_order_html_description/static/src/scss/sale_order_line_html_text.scss',
        ],
    },


}
