# -*- coding: utf-8 -*-
"""Free unit-of-measure selection on quotation and invoice lines.

Odoo 19 restricts the unit on sale/invoice lines to the product's own unit
plus its packaging units (``product.uom_id | product.uom_ids``). Heiniger
needs to pick any unit per line (kg, m2, Stk., Psch., ...) depending on the
offer, without changing the product master data.
"""

from odoo import api, models


class UomUom(models.Model):
    _inherit = 'uom.uom'

    def _hgr_has_common_reference(self, other):
        if not self or not other or len(self) != 1 or len(other) != 1:
            return True
        if not self.parent_path or not other.parent_path:
            return True
        return self._has_common_reference(other)

    def _compute_price(self, price, to_unit):
        # Units without a common reference (e.g. Stk. -> kg, Stk. -> m2) have
        # no meaningful conversion factor. Standard Odoo would blindly apply
        # the absolute factors (Stk. 1 -> kg 1000), turning 50.- into 50'000.-
        # Keep the price unchanged instead.
        if to_unit and not self._hgr_has_common_reference(to_unit):
            return price
        return super()._compute_price(price, to_unit)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_id', 'product_id.uom_id', 'product_id.uom_ids')
    def _compute_allowed_uom_ids(self):
        all_uoms = self.env['uom.uom'].search([])
        for line in self:
            line.allowed_uom_ids = all_uoms

    def _get_gross_price_unit(self):
        # Standard converts the price into the product unit using absolute
        # factors. Skip it for unrelated units (see UomUom._compute_price).
        self.ensure_one()
        if (
            self.product_uom_id
            and self.product_id.uom_id
            and not self.product_uom_id._hgr_has_common_reference(self.product_id.uom_id)
        ):
            price_unit = self.price_unit
            if self.discount:
                price_unit = price_unit * (1 - self.discount / 100)
            if self.tax_ids:
                qty = self.product_uom_qty or 1
                price_unit = self.tax_ids.compute_all(
                    price_unit,
                    currency=self.order_id.currency_id,
                    quantity=qty,
                    rounding_method='round_globally',
                )['total_void']
                price_unit = price_unit / qty
            return price_unit
        return super()._get_gross_price_unit()

    @api.depends('price_unit', 'discount', 'qty_invoiced_at_date', 'qty_delivered_at_date')
    @api.depends_context('accrual_entry_date')
    def _compute_amount_to_invoice_at_date(self):
        unrelated = self.filtered(
            lambda l: l.product_uom_id and l.product_id.uom_id
            and not l.product_uom_id._hgr_has_common_reference(l.product_id.uom_id)
        )
        for line in unrelated:
            qty_to_invoice = line.qty_delivered_at_date - line.qty_invoiced_at_date
            line.amount_to_invoice_at_date = qty_to_invoice * line._get_gross_price_unit()
        return super(SaleOrderLine, self - unrelated)._compute_amount_to_invoice_at_date()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.depends('product_id', 'product_id.uom_id', 'product_id.uom_ids')
    def _compute_allowed_uom_ids(self):
        all_uoms = self.env['uom.uom'].search([])
        for line in self:
            line.allowed_uom_ids = all_uoms
