# -*- coding: utf-8 -*-
"""Free unit-of-measure selection on quotation and invoice lines.

Odoo 19 restricts the unit on sale/invoice lines to the product's own unit
plus its packaging units (``product.uom_id | product.uom_ids``). Heiniger
needs to pick any unit per line (kg, m2, Stk., Psch., ...) depending on the
offer, without changing the product master data.
"""

from odoo import api, fields, models

# Imperial / unused standard units hidden from quotation lines by default.
HGR_HIDDEN_UOM_XMLIDS = [
    'uom.product_uom_lb', 'uom.product_uom_oz', 'uom.product_uom_inch',
    'uom.product_uom_foot', 'uom.product_uom_yard', 'uom.product_uom_mile',
    'uom.product_uom_square_foot', 'uom.product_uom_cubic_foot',
    'uom.product_uom_cubic_inch', 'uom.product_uom_floz', 'uom.product_uom_qt',
    'uom.product_uom_gal',
]


class UomUom(models.Model):
    _inherit = 'uom.uom'

    hgr_sale_selectable = fields.Boolean(
        string='Selectable on Quotes/Invoices',
        default=True,
        help='Offer this unit on every quotation and invoice line, whatever '
             'the product unit is. Untick duplicates or units nobody uses.',
    )

    @api.model
    def _hgr_selectable_uoms(self):
        return self.search([('hgr_sale_selectable', '=', True)])

    @api.model
    def _hgr_dedupe_selectable(self):
        """Keep one selectable unit per (normalised) name: the most used one.

        The v17 -> v19 migration left one copy of e.g. kg/Psch./Stk. per old
        UoM category. Offering all of them makes the unit dropdown unusable.
        """
        lang = 'de_CH' if self.env['res.lang']._lang_get('de_CH') else 'en_US'
        uoms = self.with_context(lang=lang, active_test=True).search([])
        usage = dict.fromkeys(uoms.ids, 0)
        for model, field in (
            ('sale.order.line', 'product_uom_id'),
            ('account.move.line', 'product_uom_id'),
            ('product.template', 'uom_id'),
        ):
            for uom, count in self.env[model].sudo()._read_group(
                [(field, 'in', uoms.ids)], [field], ['__count'],
            ):
                usage[uom.id] = usage.get(uom.id, 0) + count

        def norm(name):
            name = (name or '').strip().lower().rstrip('.')
            return name.replace('²', '2').replace('³', '3')

        groups = {}
        for uom in uoms:
            groups.setdefault(norm(uom.name), []).append(uom)
        hidden = self.browse()
        for members in groups.values():
            members.sort(key=lambda u: (-usage.get(u.id, 0), u.id))
            hidden |= self.browse([u.id for u in members[1:]])
        for xmlid in HGR_HIDDEN_UOM_XMLIDS:
            uom = self.env.ref(xmlid, raise_if_not_found=False)
            if uom and not usage.get(uom.id):
                hidden |= uom
        hidden.write({'hgr_sale_selectable': False})
        (uoms - hidden).write({'hgr_sale_selectable': True})
        return hidden

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

    @api.depends('product_id', 'product_id.uom_id', 'product_id.uom_ids', 'product_uom_id')
    def _compute_allowed_uom_ids(self):
        selectable = self.env['uom.uom']._hgr_selectable_uoms()
        for line in self:
            line.allowed_uom_ids = (
                selectable | line.product_id.uom_id | line.product_id.uom_ids
                | line.product_uom_id
            )

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

    @api.depends('product_id', 'product_id.uom_id', 'product_id.uom_ids', 'product_uom_id')
    def _compute_allowed_uom_ids(self):
        selectable = self.env['uom.uom']._hgr_selectable_uoms()
        for line in self:
            line.allowed_uom_ids = (
                selectable | line.product_id.uom_id | line.product_id.uom_ids
                | line.product_uom_id
            )
