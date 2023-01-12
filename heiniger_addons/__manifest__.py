# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Heiniger Addons',
    'version': '1.0',
    'category': 'Customizations',
    'sequence': 6,
    'summary': 'Custom changes for heiniger ',
    'description': """

This module added for additional fields & custom developments.

""",
    'depends': ['sale','sale_crm'],
    'data': [
        'views/res_partner_view.xml',
        'views/sale_order_view.xml',
        'views/crm_lead_view.xml',
        ],
    'installable': True,
    # 'assets': {
    #     'point_of_sale.assets': [
    #         'pos_discount/static/src/js/**/*',
    #         'pos_discount/static/src/xml/**/*',
    #     ],
    # },
    'license': 'LGPL-3',
}
