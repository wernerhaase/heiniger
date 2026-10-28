from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestTwoTierPaymentTerm(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other_currency = cls.setup_other_currency('EUR')
        cls.term = cls.env['account.payment.term'].create({
            'name': '3% 10 days, 2% 30 days, net 45 days',
            'company_id': cls.company_data['company'].id,
            'early_discount': True,
            'discount_percentage': 3.0,
            'discount_days': 10,
            'early_pay_discount_computation': 'included',
            'hgr_second_early_discount': True,
            'hgr_second_discount_percentage': 2.0,
            'hgr_second_discount_days': 30,
            'line_ids': [Command.create({
                'value': 'percent',
                'value_amount': 100,
                'nb_days': 45,
            })],
        })

    def _invoice(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2026-07-07',
            'date': '2026-07-07',
            'invoice_payment_term_id': self.term.id,
            'invoice_line_ids': [Command.create({
                'name': 'Two-tier discount test',
                'price_unit': 1000.0,
                'tax_ids': [],
            })],
        })
        invoice.action_post()
        return invoice

    def test_discount_options_and_deadlines(self):
        options = self.term._hgr_discount_options(
            fields.Date.from_string('2026-07-07'), 1000.0, 1000.0,
            self.company_data['currency'],
        )
        self.assertEqual([option['amount'] for option in options], [970.0, 980.0])
        self.assertEqual(
            [option['date'] for option in options],
            [fields.Date.from_string('2026-07-17'), fields.Date.from_string('2026-08-06')],
        )

    def test_list_discount_date_advances_to_next_available_deadline(self):
        invoice = self._invoice()
        self.assertEqual(
            invoice.with_context(
                hgr_payment_reference_date='2026-07-15',
            ).invoice_discount_date_due,
            fields.Date.from_string('2026-07-17'),
        )
        self.assertEqual(
            invoice.with_context(
                hgr_payment_reference_date='2026-07-27',
            ).invoice_discount_date_due,
            fields.Date.from_string('2026-08-06'),
        )
        self.assertEqual(
            invoice.with_context(
                hgr_payment_reference_date='2026-08-10',
            ).invoice_discount_date_due,
            fields.Date.from_string('2026-08-06'),
        )
        self.assertEqual(
            invoice.with_context(
                hgr_payment_reference_date='2026-09-10',
            ).invoice_discount_date_due,
            fields.Date.from_string('2026-08-06'),
        )

    def test_swiss_cash_rounding_matches_supplier_example(self):
        rounding = self.env['account.cash.rounding'].create({
            'name': 'CHF 0.05 test rounding',
            'rounding': 0.05,
            'rounding_method': 'HALF-UP',
            'strategy': 'add_invoice_line',
        })
        options = self.term._hgr_discount_options(
            fields.Date.from_string('2026-07-07'), 253.50, 234.50,
            self.company_data['currency'], rounding,
        )
        self.assertEqual([option['amount'] for option in options], [245.90, 248.45])

    def test_second_tier_is_suggested_and_reconciled(self):
        invoice = self._invoice()
        line = invoice.line_ids.filtered(lambda item: item.display_type == 'payment_term')
        installments = line._get_installments_data(
            payment_currency=invoice.currency_id,
            payment_date=fields.Date.from_string('2026-07-27'),
        )
        self.assertEqual(installments[0]['type'], 'early_payment_discount')
        self.assertEqual(installments[0]['hgr_discount_tier'], 'second')
        self.assertEqual(installments[0]['amount_residual_currency_unsigned'], 980.0)

        payment = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'payment_date': '2026-07-27'})._create_payments()
        self.assertTrue(payment.is_reconciled)
        self.assertEqual(
            payment.move_id.line_ids.sorted('balance').mapped('amount_currency'),
            [-1000.0, 20.0, 980.0],
        )

    def test_second_tier_with_tax_is_reconciled(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2026-07-07',
            'date': '2026-07-07',
            'invoice_payment_term_id': self.term.id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'price_unit': 1000.0,
                'tax_ids': [Command.set(self.product_a.taxes_id.ids)],
            })],
        })
        invoice.action_post()
        payment = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'payment_date': '2026-07-27'})._create_payments()
        self.assertTrue(payment.is_reconciled)
        self.assertEqual(invoice.payment_state, 'paid')

    def test_second_tier_adjusts_cash_basis_tax(self):
        company = self.company_data['company']
        company.tax_exigibility = True
        company.account_cash_basis_base_account_id = self.env['account.account'].create({
            'code': 'HGR.CABA.BASE',
            'name': 'HGR cash-basis base account',
            'account_type': 'income',
        })
        transition_account = self.env['account.account'].create({
            'code': 'HGR.CABA.TRANS',
            'name': 'HGR cash-basis transition account',
            'account_type': 'income',
            'reconcile': True,
        })
        tax = self.company_data['default_tax_sale'].copy({
            'name': 'Cash-basis VAT 8.1%',
            'amount': 8.1,
            'tax_exigibility': 'on_payment',
            'cash_basis_transition_account_id': transition_account.id,
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2026-07-07',
            'date': '2026-07-07',
            'invoice_payment_term_id': self.term.id,
            'invoice_line_ids': [Command.create({
                'name': 'Cash-basis two-tier discount',
                'price_unit': 1000.0,
                'tax_ids': [Command.set(tax.ids)],
            })],
        })
        invoice.action_post()
        payment = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'payment_date': '2026-07-27'})._create_payments()

        self.assertTrue(payment.is_reconciled)
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertEqual(payment.amount, 1059.38)
        cash_basis_tax_lines = invoice.tax_cash_basis_created_move_ids.line_ids.filtered(
            lambda line: line.tax_line_id == tax
        )
        self.assertTrue(
            cash_basis_tax_lines,
            invoice.tax_cash_basis_created_move_ids.line_ids.read([
                'name', 'balance', 'account_id', 'tax_line_id', 'tax_ids', 'tax_tag_ids',
            ]),
        )
        self.assertEqual(
            company.currency_id.round(abs(sum(cash_basis_tax_lines.mapped('balance')))),
            81.0,
        )
        discount_tax_lines = payment.move_id.line_ids.filtered(lambda line: line.tax_line_id == tax)
        self.assertTrue(
            discount_tax_lines,
            payment.move_id.line_ids.read([
                'name', 'balance', 'account_id', 'tax_line_id', 'tax_ids', 'tax_tag_ids',
            ]),
        )
        self.assertEqual(
            company.currency_id.round(abs(sum(discount_tax_lines.mapped('balance')))),
            1.62,
        )
        self.assertEqual(
            company.currency_id.round(
                abs(sum(cash_basis_tax_lines.mapped('balance')))
                - abs(sum(discount_tax_lines.mapped('balance')))
            ),
            79.38,
        )

    def test_second_tier_foreign_currency_is_reconciled(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'currency_id': self.other_currency.id,
            'invoice_date': '2026-07-07',
            'date': '2026-07-07',
            'invoice_payment_term_id': self.term.id,
            'invoice_line_ids': [Command.create({
                'name': 'Foreign-currency two-tier discount',
                'price_unit': 1000.0,
                'tax_ids': [],
            })],
        })
        invoice.action_post()
        payment = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'payment_date': '2026-07-27'})._create_payments()
        self.assertTrue(payment.is_reconciled)
        self.assertEqual(
            payment.move_id.line_ids.sorted('amount_currency').mapped('amount_currency'),
            [-1000.0, 20.0, 980.0],
        )

    def test_invoice_pdf_renders_two_tiers(self):
        invoice = self._invoice()
        invoice.partner_id.lang = 'de_CH'
        report = self.env['ir.actions.report']
        html, _report_type = report._render_qweb_html(
            'account.account_invoices', invoice.ids,
        )
        self.assertIn(b'text-danger', html)
        self.assertIn(b'Skonto', html)
        with self.allow_pdf_render():
            pdf, _report_type = report._render_qweb_pdf(
                'account.account_invoices', res_ids=invoice.id,
            )
        self.assertTrue(pdf)

    def test_first_tier_uses_standard_odoo_path(self):
        invoice = self._invoice()
        line = invoice.line_ids.filtered(lambda item: item.display_type == 'payment_term')
        installments = line._get_installments_data(
            payment_currency=invoice.currency_id,
            payment_date=fields.Date.from_string('2026-07-15'),
        )
        self.assertEqual(installments[0]['amount_residual_currency_unsigned'], 970.0)
        self.assertNotIn('hgr_discount_tier', installments[0])

    def test_invalid_second_tier_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.term.hgr_second_discount_percentage = 4.0
