# -*- coding: utf-8 -*-
"""Free unit-of-measure selection on quotation and invoice lines.

Odoo 19 restricts the unit on sale/invoice lines to the product's own unit
plus its packaging units (``product.uom_id | product.uom_ids``). Heiniger
needs to pick any unit per line (kg, m2, Stk., Psch., ...) depending on the
offer, without changing the product master data.
"""

import logging
import re

from psycopg2 import errors, sql

from odoo import api, fields, models
from odoo.tools import float_round

_logger = logging.getLogger(__name__)

# Different spellings of the same unit (keys are normalised names).
HGR_UOM_SYNONYMS = {
    'stk': 'stk', 'stück': 'stk', 'pieces': 'stk', 'units': 'stk',
    'psch': 'psch', 'lump sum': 'psch',
    'h': 'h', 'std': 'h', 'stunde': 'h', 'stunden': 'h', 'hours': 'h',
    'tag': 'tage', 'tage': 'tage', 'days': 'tage',
    'm2': 'm2', 'm3': 'm3',
    'l': 'l', 'ltr': 'l', 'liter': 'l',
    't': 't', 'tonne': 't',
    'roll': 'rolle', 'rolle': 'rolle',
}

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
    def _hgr_lang_uoms(self):
        lang = 'de_CH' if self.env['res.lang']._lang_get('de_CH') else 'en_US'
        return self.with_context(lang=lang, active_test=True).search([])

    @api.model
    def _hgr_uom_usage(self, uoms):
        usage = dict.fromkeys(uoms.ids, 0)
        for model, field in (
            ('sale.order.line', 'product_uom_id'),
            ('account.move.line', 'product_uom_id'),
            ('product.template', 'uom_id'),
        ):
            for uom, count in self.env[model].sudo().with_context(active_test=False)._read_group(
                [(field, 'in', uoms.ids)], [field], ['__count'],
            ):
                usage[uom.id] = usage.get(uom.id, 0) + count
        return usage

    @api.model
    def _hgr_uom_group_key(self, name):
        key = re.sub(r'\s+', ' ', (name or '').strip().lower()).rstrip('.')
        key = key.replace('²', '2').replace('³', '3')
        return HGR_UOM_SYNONYMS.get(key, key)

    @api.model
    def _hgr_uom_groups(self, uoms):
        groups = {}
        for uom in uoms:
            groups.setdefault(self._hgr_uom_group_key(uom.name), []).append(uom)
        return groups

    @api.model
    def _hgr_uom_fk_columns(self):
        self.env.cr.execute("""
            SELECT cl.relname, att.attname
              FROM pg_constraint con
              JOIN pg_class cl ON cl.oid = con.conrelid
              JOIN pg_attribute att ON att.attrelid = con.conrelid
                                   AND att.attnum = con.conkey[1]
             WHERE con.contype = 'f'
               AND con.confrelid = 'uom_uom'::regclass
               AND array_length(con.conkey, 1) = 1
               AND cl.relname != 'uom_uom'
        """)
        return self.env.cr.fetchall()

    @api.model
    def _hgr_repoint_uom(self, duplicates, target):
        """Point every reference to ``duplicates`` at ``target`` (SQL level)."""
        cr = self.env.cr
        dup_ids = tuple(duplicates.ids)
        for table, column in self._hgr_uom_fk_columns():
            cr.execute('SAVEPOINT hgr_uom_merge')
            query = sql.SQL('UPDATE {t} SET {c} = %s WHERE {c} IN %s').format(
                t=sql.Identifier(table), c=sql.Identifier(column))
            try:
                cr.execute(query, (target.id, dup_ids))
                cr.execute('RELEASE SAVEPOINT hgr_uom_merge')
            except errors.UniqueViolation:
                # Many2many relation tables: drop pairs that would collide.
                cr.execute('ROLLBACK TO SAVEPOINT hgr_uom_merge')
                cr.execute("""
                    SELECT array_agg(attname::text) FROM pg_attribute
                     WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped
                """, (table,))
                cols = cr.fetchone()[0]
                if len(cols) != 2:
                    raise
                other = sql.Identifier([c for c in cols if c != column][0])
                cr.execute(sql.SQL("""
                    DELETE FROM {t} d WHERE d.{c} IN %s AND (
                        d.{o} IN (SELECT {o} FROM {t} WHERE {c} = %s)
                        OR d.ctid <> (SELECT min(x.ctid) FROM {t} x
                                       WHERE x.{o} = d.{o} AND x.{c} IN %s))
                """).format(t=sql.Identifier(table), c=sql.Identifier(column), o=other),
                    (dup_ids, target.id, dup_ids))
                cr.execute(query, (target.id, dup_ids))
                cr.execute('RELEASE SAVEPOINT hgr_uom_merge')
        # Units defined relative to a duplicate (e.g. pallet -> m3).
        dependants = self.with_context(active_test=False).search([
            ('relative_uom_id', 'in', duplicates.ids), ('id', 'not in', duplicates.ids),
        ])
        for uom in dependants:
            if uom == target:
                uom.write({'relative_uom_id': False, 'relative_factor': 1.0})
            else:
                uom.write({'relative_uom_id': target.id})

    @api.model
    def _hgr_merge_duplicate_uoms(self):
        """Merge units that are the same unit under several records.

        The v17 -> v19 migration created one copy of kg, Psch., Stk., Std ...
        per former UoM category. Per (synonym-normalised) German name, keep
        the standard Odoo unit if there is one, else the most used record,
        give it the most used spelling, move every reference to it and
        archive the copies.
        """
        uoms = self._hgr_lang_uoms()
        usage = self._hgr_uom_usage(uoms)
        xmlids = {
            d.res_id for d in self.env['ir.model.data'].sudo().search([
                ('model', '=', 'uom.uom'), ('module', '=', 'uom'),
                ('res_id', 'in', uoms.ids),
            ])
        }
        merged = {}
        for members in self._hgr_uom_groups(uoms).values():
            if len(members) < 2:
                continue
            by_usage = sorted(members, key=lambda u: (-usage.get(u.id, 0), u.id))
            standard = [u for u in members if u.id in xmlids]
            target = standard[0] if standard else by_usage[0]
            duplicates = self.browse([u.id for u in members if u != target])
            name = by_usage[0].name
            self._hgr_repoint_uom(duplicates, target)
            duplicates.write({'active': False, 'hgr_sale_selectable': False})
            if target.name != name:
                target.with_context(lang=uoms.env.lang).write({'name': name})
            merged[target.id] = duplicates.ids
            _logger.info('Heiniger UoM merge: %s -> %s (%s)', duplicates.ids, target.id, name)
        self.env.invalidate_all()
        return merged

    @api.model
    def _hgr_dedupe_selectable(self):
        """Keep one selectable unit per (normalised) name: the most used one.

        The v17 -> v19 migration left one copy of e.g. kg/Psch./Stk. per old
        UoM category. Offering all of them makes the unit dropdown unusable.
        """
        uoms = self._hgr_lang_uoms()
        usage = self._hgr_uom_usage(uoms)
        groups = self._hgr_uom_groups(uoms)
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

    def _compute_quantity(self, qty, to_unit, round=True, rounding_method='UP',
                          raise_if_failure=True):
        # Unrelated units (e.g. Stk. -> Tage, Stk. -> t): keep the quantity
        # 1:1 instead of applying unrelated absolute factors.
        if qty and to_unit and not self._hgr_has_common_reference(to_unit):
            if round:
                return float_round(qty, precision_rounding=to_unit.rounding,
                                   rounding_method=rounding_method)
            return qty
        return super()._compute_quantity(
            qty, to_unit, round=round, rounding_method=rounding_method,
            raise_if_failure=raise_if_failure)

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
