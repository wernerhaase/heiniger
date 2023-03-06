# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

{
    "name": "Invoice Multi Product Selection",
    "author": "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "license": "OPL-1",
    "category": "Accounting",
    "summary": """Invoice Multi Product Selection,add invoice more products app,
                add credit note products odoo, provide bills mass product,
                multi product select, invoice product odoo""",
    "description": """This module very useful and time saver if you want to add
                    multiple products on a single click. You can add multiple
                    products in Invoice/bill and you can also do from
                    multi-selection in product list view.Invoice Multi Product Selection,
                    add invoice more products app, add credit note products odoo,
                    provide bills mass product, multi product select module""",
    "version": "16.0.1",
    "depends": ["account"],
    "application": True,
    "data": ["security/ir.model.access.csv",
             "views/account_move_views.xml",
             "wizard/multi_product_inv_wizard_views.xml",
             "wizard/inv_create_pro_wizard_views.xml",
             "wizard/inv_create_protmpl_wizard_views.xml"],
    "images": ["static/description/background.png", ],
    "auto_install": False,
    "installable": True,
    "price": 15,
    "currency": "EUR"
}
