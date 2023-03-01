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
    'depends': ['sale','sale_crm','sale_project','project','hr_timesheet'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_view.xml',
        'views/sale_order_view.xml',
        'views/crm_lead_view.xml',
        'views/project_view.xml',
        'report/timesheet_report.xml',
        ],
    'installable': True,
    # 'assets': {
    #     'web.report_assets_common': [
    #         'heiniger_addons/static/src/**/*',
    #     ],
    # },
    'license': 'LGPL-3',
}
