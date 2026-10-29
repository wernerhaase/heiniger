from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestAdvanceSummary(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.order = cls.env['sale.order'].sudo().create({
            'partner_id': cls.partner_a.id,
            'order_line': [Command.create({
                'product_id': cls.product_a.id,
                'product_uom_qty': 1.0,
                'price_unit': 1000.0,
                'tax_ids': [Command.clear()],
            })],
        })
        cls.order.action_confirm()
        cls.advance_sale_line = cls.env['sale.order.line'].sudo().create({
            'order_id': cls.order.id,
            'name': 'Down payment',
            'product_id': cls.product_a.id,
            'product_uom_id': cls.product_a.uom_id.id,
            'product_uom_qty': 0.0,
            'price_unit': 300.0,
            'tax_ids': [Command.clear()],
            'is_downpayment': True,
        })

    @classmethod
    def _create_advance_move(cls, move_type, amount):
        move = cls.env['account.move'].sudo().create({
            'move_type': move_type,
            'partner_id': cls.partner_a.id,
            'invoice_date': '2026-10-29',
            'invoice_line_ids': [Command.create({
                'name': 'Down payment',
                'product_id': cls.product_a.id,
                'quantity': 1.0,
                'price_unit': amount,
                'tax_ids': [Command.clear()],
                'sale_line_ids': [Command.set(cls.advance_sale_line.ids)],
                'is_downpayment': True,
            })],
        })
        move.action_post()
        return move

    def test_posted_advance_and_refund_update_summary(self):
        advance = self._create_advance_move('out_invoice', 300.0)
        self.assertTrue(self.order.hgr_has_advance_invoices)
        self.assertEqual(self.order.hgr_advance_invoiced_total, 300.0)
        self.assertEqual(self.order.hgr_remaining_after_advance, 700.0)

        self.assertTrue(advance.hgr_has_advance_summary)
        self.assertEqual(advance.hgr_sale_order_untaxed, 1000.0)
        self.assertEqual(advance.hgr_sale_order_total, 1000.0)
        self.assertEqual(advance.hgr_advance_invoiced_total, 300.0)
        self.assertEqual(advance.hgr_remaining_after_advance, 700.0)

        self._create_advance_move('out_refund', 50.0)
        self.assertEqual(self.order.hgr_advance_invoiced_total, 250.0)
        self.assertEqual(self.order.hgr_remaining_after_advance, 750.0)

    def test_draft_advance_is_not_summarized(self):
        draft = self.env['account.move'].sudo().create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2026-10-29',
            'invoice_line_ids': [Command.create({
                'name': 'Draft down payment',
                'product_id': self.product_a.id,
                'price_unit': 300.0,
                'tax_ids': [Command.clear()],
                'sale_line_ids': [Command.set(self.advance_sale_line.ids)],
                'is_downpayment': True,
            })],
        })
        self.assertEqual(draft.state, 'draft')
        self.assertFalse(self.order.hgr_has_advance_invoices)
        self.assertEqual(self.order.hgr_advance_invoiced_total, 0.0)
        self.assertEqual(self.order.hgr_remaining_after_advance, 1000.0)

    def test_sale_and_invoice_reports_include_advance_summary(self):
        advance = self._create_advance_move('out_invoice', 300.0)
        report_model = self.env['ir.actions.report'].sudo()
        sale_html, _ = report_model._render_qweb_html(
            'sale.action_report_saleorder', self.order.ids,
        )
        invoice_html, _ = report_model._render_qweb_html(
            'account.account_invoices', advance.ids,
        )
        portal_totals_html = self.env['ir.ui.view']._render_template(
            'sale.sale_order_portal_content_totals_table',
            {'sale_order': self.order},
        )
        self.assertIn(b'Invoiced advances', sale_html)
        self.assertIn(b'Auftragswert exkl. MwSt.', sale_html)
        self.assertIn(b'Remaining order amount', sale_html)
        self.assertIn(b'Invoiced advances', portal_totals_html)
        self.assertIn(b'Auftragswert exkl. MwSt.', portal_totals_html)
        self.assertIn(b'Remaining order amount', portal_totals_html)
        self.assertIn(b'hgr_advance_summary_label', portal_totals_html)
        self.assertIn(b'hgr_advance_summary_value', portal_totals_html)
        self.assertIn(b'Auftragswert exkl. MwSt.', invoice_html)
        self.assertIn(b'Order total incl. tax', invoice_html)
        self.assertIn(b'Invoiced advances', invoice_html)
        self.assertIn(b'hgr_advance_summary_label', invoice_html)
        self.assertIn(b'hgr_advance_summary_value', invoice_html)
        self.assertIn(b'hgr_invoice_totals', invoice_html)
        self.assertIn(b'hgr_invoice_terms', invoice_html)
        self.assertLess(
            invoice_html.index(b'hgr_invoice_totals'),
            invoice_html.index(b'hgr_invoice_terms'),
        )
