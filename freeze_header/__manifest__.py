# -*- coding: utf-8 -*-
# Powered by Kanak Infosystems LLP.
# © 2020 Kanak Infosystems LLP. (<https://www.kanakinfosystems.com>).

{
    'name': 'Freeze Header',
    'version': '16.0.1.0',
    'summary': 'Freeze header in list view | sticky header | sticky header in list view | fixed header | sticky header in one2many, many2many list view',
    'description': """
        Freeze header in list
    """,
    'category': 'Extra Tools',
    'license': 'OPL-1',
    'author': 'Kanak Infosystems LLP.',
    'website': 'https://www.kanakinfosystems.com',
    'depends': ['web', 'sale'],
    'data': [
        'views/freeze_tmp.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'freeze_header/static/src/scss/freeze.scss',
        ],
    },
    'images': ['static/description/banner.jpg'],
    'application': True,
    'price': 20,
    'currency': 'EUR',
}
