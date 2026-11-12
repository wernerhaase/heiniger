from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestFreeUom(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(su=True)
        cls.unit = cls.env.ref('uom.product_uom_unit')
        cls.kg = cls.env.ref('uom.product_uom_kgm')
        cls.m2 = cls.env.ref('uom.product_uom_square_meter')
        cls.paint = cls.env['product.product'].create({
            'name': 'Dispersionsfarbe',
            'type': 'consu',
            'uom_id': cls.unit.id,
            'list_price': 50.0,
        })

    def test_any_unit_is_allowed_on_quote_and_invoice_lines(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({'product_id': self.paint.id})],
        })
        line = order.order_line
        self.assertIn(self.kg, line.allowed_uom_ids)
        self.assertIn(self.m2, line.allowed_uom_ids)

        move = self.init_invoice('out_invoice', products=self.paint)
        self.assertIn(self.kg, move.invoice_line_ids.allowed_uom_ids)

    def test_unrelated_unit_keeps_price_and_flows_to_invoice(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({
                'product_id': self.paint.id,
                'product_uom_qty': 12.0,
                'tax_ids': [Command.clear()],
            })],
        })
        line = order.order_line
        line.product_uom_id = self.kg
        # No blind factor conversion (Stk. -> kg would give 50'000.-)
        self.assertEqual(line.price_unit, 50.0)
        self.assertEqual(line.price_subtotal, 600.0)

        order.action_confirm()
        line.qty_delivered = 12.0
        invoice = order._create_invoices()
        inv_line = invoice.invoice_line_ids
        self.assertEqual(inv_line.product_uom_id, self.kg)
        self.assertEqual(inv_line.quantity, 12.0)
        self.assertEqual(inv_line.price_unit, 50.0)
        self.assertEqual(line.qty_invoiced, 12.0)

    def test_related_units_still_convert(self):
        gram = self.env.ref('uom.product_uom_gram')
        self.assertAlmostEqual(self.kg._compute_price(10.0, gram), 0.01)

    def test_duplicate_units_are_hidden_but_current_unit_stays(self):
        Uom = self.env['uom.uom']
        dup_kg = Uom.create({'name': 'kg', 'relative_factor': 1.0})
        Uom._hgr_dedupe_selectable()
        # Exactly one "kg" stays selectable, never the fresh unused duplicate.
        kgs = Uom.with_context(lang='en_US').search([('name', '=', 'kg')])
        self.assertEqual(len(kgs.filtered('hgr_sale_selectable')), 1)
        self.assertFalse(dup_kg.hgr_sale_selectable)

        order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({'product_id': self.paint.id})],
        })
        line = order.order_line
        self.assertNotIn(dup_kg, line.allowed_uom_ids)
        line.product_uom_id = dup_kg
        self.assertIn(dup_kg, line.allowed_uom_ids)

    def test_merge_duplicate_units(self):
        Uom = self.env['uom.uom']
        dup_kg = Uom.create({'name': 'kg', 'relative_uom_id': self.unit.id, 'relative_factor': 1.0})
        dup_std = Uom.create({'name': 'Std', 'relative_uom_id': self.unit.id, 'relative_factor': 1.0})
        sack = Uom.create({'name': 'Hgr-Sack', 'relative_uom_id': dup_kg.id, 'relative_factor': 25.0})
        product = self.env['product.product'].create({
            'name': 'Paint in duplicate kg', 'type': 'consu', 'uom_id': dup_kg.id,
            'list_price': 10.0,
        })
        order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': 3})],
        })
        hour = self.env.ref('uom.product_uom_hour')

        Uom._hgr_merge_duplicate_uoms()

        self.assertFalse(dup_kg.active)
        self.assertFalse(dup_std.active)
        self.assertEqual(product.uom_id, self.kg)
        self.assertEqual(order.order_line.product_uom_id, self.kg)
        self.assertEqual(sack.relative_uom_id, self.kg)
        self.assertAlmostEqual(sack.factor, 25.0 * self.kg.factor)
        self.assertTrue(hour.active)
        kgs = Uom.with_context(lang='en_US').search([('name', '=', 'kg')])
        self.assertEqual(kgs, self.kg)

    def test_unrelated_units_keep_quantity(self):
        day = self.env.ref('uom.product_uom_day')
        self.assertEqual(day._compute_quantity(3.0, self.unit), 3.0)
        self.assertEqual(day._compute_quantity(1.0, self.env.ref('uom.product_uom_hour')), 8.0)
