# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import _, fields, models
from odoo.exceptions import UserError


class MultiProductWizardInv(models.TransientModel):
    _name = "multi.product.wizard.inv"
    _description = "Invoice Multi Product Selection"

    product_ids = fields.Many2many("product.product", string="Products")

    def sh_multi_product_apply(self):

        if self and self.product_ids and self.env.context.get('sh_active_inv', False):
            active_inv = self.env['account.move'].search(
                [('id', '=', self.env.context.get('sh_active_inv'))], limit=1)
            if active_inv:
                for product in self.product_ids:
                    accounts = product.product_tmpl_id.get_product_accounts(
                        active_inv.fiscal_position_id)
                    account = False
                    if active_inv.move_type in ('out_invoice', 'out_refund'):
                        account = accounts['income']
                    else:
                        account = accounts['expense']
                    if not account:
                        raise UserError(
                            _("No account defined for this product: " + product.name))

                    inv_line_obj = self.env['account.move.line']
                    created_inv_line = inv_line_obj.with_context(check_move_validity=False).create({'product_id': product.id,
                                                                                                    'move_id': active_inv.id,
                                                                                                    'account_id': account.id})
                    if created_inv_line:
                        created_inv_line._compute_name()
                        created_inv_line._compute_product_uom_id()
                        created_inv_line._compute_price_unit()
                        created_inv_line._compute_tax_ids()
                        created_inv_line._compute_totals()

                active_inv.with_context(
                    check_move_validity=False)._onchange_partner_id()
                active_inv._onchange_quick_edit_line_ids()
