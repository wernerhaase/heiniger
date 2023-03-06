# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models


class AccountInvoice(models.Model):
    _inherit = "account.move"

    def sh_action_select_product(self):
        if self:
            view = self.env.ref(
                'sh_invoice_multi_product.sh_multi_product_wizard_inv')
            context = self.env.context
            return {'name': 'Select Products',
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'multi.product.wizard.inv',
                    'views': [(view.id, 'form')],
                    'view_id': view.id,
                    'target': 'new',
                    'context': context}
