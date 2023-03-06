# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import _, fields, models
from odoo.exceptions import UserError


class InvCreateWizardProTmpl(models.TransientModel):
    _name = "inv.create.wizard.protmpl"
    _description = "Invoice Create Wizard Product Template"

    invoice_type = fields.Selection([('inv', 'Customer Invoice'),
                                     ('bill', 'Vendor Bill'),
                                     ('ccn', 'Customer Credit Note'),
                                     ('vcn', 'Vendor Credit Note')],
                                    default="inv",
                                    string="Invoicing Type",
                                    required=True)
    partner_id = fields.Many2one(
        "res.partner", string="Customer/Vendor", required=True)

    def sh_create_inv(self):
        account_move = self.env['account.move']
        account_move_line = self.env['account.move.line']
        if self and self.invoice_type and self.partner_id and self.env.context.get('active_ids', False):
            inv_vals = {}
            product_variant_list = []
            search_pro_tmpls = self.env['product.template'].search(
                [('id', 'in', self.env.context.get('active_ids'))])
            if search_pro_tmpls:
                for pro_tmpl in search_pro_tmpls:
                    if pro_tmpl.product_variant_id:
                        product_variant_list.append(
                            pro_tmpl.product_variant_id.id)
            search_products = self.env["product.product"].search(
                [('id', 'in', product_variant_list)])
            inv_vals.update({'partner_id': self.partner_id.id})

            if self.invoice_type == 'inv':
                inv_vals.update({"move_type": "out_invoice"})
                default_type = 'out_invoice'

            elif self.invoice_type == 'bill':
                inv_vals.update({"move_type": "in_invoice"})
                default_type = 'in_invoice'

            elif self.invoice_type == 'ccn':
                inv_vals.update({"move_type": "out_refund"})
                default_type = 'out_refund'
            elif self.invoice_type == 'vcn':
                inv_vals.update({"move_type": "in_refund"})
                default_type = 'in_refund'

            created_inv = account_move.with_context(
                default_type=default_type, check_move_validity=False).create(inv_vals)

            if search_products and created_inv:
                for product_tmpl in search_products:
                    vals = {}
                    vals.update({'product_id': product_tmpl.id})
                    accounts = product_tmpl.product_tmpl_id.get_product_accounts(
                        created_inv.fiscal_position_id)
                    account = False
                    if created_inv.move_type in ('out_invoice', 'out_refund'):
                        account = accounts['income']
                    else:
                        account = accounts['expense']

                    if account:
                        vals.update({'account_id': account.id})
                    else:
                        raise UserError(
                            _("No account defined for this product: " + product_tmpl.name))

                    vals.update({'move_id': created_inv.id})

                    created_inv_line = account_move_line.with_context(
                        check_move_validity=False).create(vals)
                    if created_inv_line:
                        created_inv_line._compute_name()
                        created_inv_line._compute_product_uom_id()
                        created_inv_line._compute_price_unit()
                        created_inv_line._compute_tax_ids()
                        created_inv_line._compute_totals()

                created_inv.with_context(
                    check_move_validity=False)._onchange_partner_id()
                created_inv._onchange_quick_edit_line_ids()
                view = self.env.ref('account.view_move_form')
                return {"type": "ir.actions.act_window",
                        "res_model": "account.move",
                        'views': [(view.id, 'form')],
                        'view_id': view.id,
                        "res_id": created_inv.id,
                        "target": "new"}
