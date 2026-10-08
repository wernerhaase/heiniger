# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Heiniger Addons',
    'version': '19.0.1.4.3',
    'category': 'Customizations',
    'sequence': 6,
    'summary': 'Custom changes for heiniger ',
    'description': """

This module added for additional fields & custom developments.

""",
    'depends': [
        'sale',
        'sale_timesheet',
        'sale_crm',
        'sale_project',
        'project',
        'hr_timesheet',
        'account',
        'l10n_din5008',
        'l10n_din5008_sale',
        'documents',
        'documents_project',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_view.xml',
        'views/sale_order_view.xml',
        'views/sale_line_units.xml',
        'views/print_attachments.xml',
        'views/portal_view_fix.xml',
        'views/portal_pdf_preview.xml',
        'views/crm_lead_view.xml',
        'views/project_view.xml',
        'report/timesheet_report.xml',
        'report/document_language.xml',
        'report/sender_address.xml',
        'report/legacy_reports.xml',
        ],
    'installable': True,
    'assets': {
        'web.assets_backend': [
            'heiniger_addons/static/src/js/quotation_attachment_order.js',
        ],
        'web.report_assets_common': [
            'heiniger_addons/static/src/css/report_pdf.css',
        ],
    },
    'license': 'LGPL-3',
}
