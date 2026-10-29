from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestBankStatementQuickTax(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tax_purchase_26 = cls.tax_purchase_a.copy({
            'name': 'Purchase VAT 2.6% (gross)',
            'amount_type': 'percent',
            'amount': 2.6,
        })
        cls.tax_purchase_81 = cls.tax_purchase_a.copy({
            'name': 'Purchase VAT 8.1% (gross)',
            'amount_type': 'percent',
            'amount': 8.1,
        })

    def test_quick_created_transaction_applies_selected_tax(self):
        statement_line = self.env['account.bank.statement.line'].create({
            'journal_id': self.company_data['default_journal_bank'].id,
            'date': '2026-10-29',
            'payment_ref': 'Quick transaction with tax',
            'amount': -108.10,
            'hgr_tax_id': self.tax_purchase_a.id,
        })
        _liquidity_lines, suspense_lines, _other_lines = statement_line._seek_for_lines()

        self.assertEqual(statement_line.hgr_tax_id, self.tax_purchase_a)
        self.assertFalse(statement_line.line_ids.tax_ids)

        statement_line.set_account_bank_statement_line(
            suspense_lines.id,
            self.company_data['default_account_expense'].id,
        )

        base_line = statement_line.line_ids.filtered('tax_ids')
        tax_line = statement_line.line_ids.filtered('tax_line_id')

        self.assertEqual(base_line.account_id, self.company_data['default_account_expense'])
        self.assertEqual(base_line.tax_ids, self.tax_purchase_a)
        self.assertEqual(tax_line.tax_line_id, self.tax_purchase_a)

    def test_multiple_quick_taxes_create_separate_allocated_lines(self):
        statement_line = self.env['account.bank.statement.line'].create({
            'journal_id': self.company_data['default_journal_bank'].id,
            'date': '2026-10-29',
            'payment_ref': 'Receipt with two VAT rates',
            'amount': -75.05,
            'hgr_tax_ids': [Command.set((self.tax_purchase_26 + self.tax_purchase_81).ids)],
            'hgr_tax_allocation_ids': [
                Command.create({'tax_id': self.tax_purchase_26.id, 'amount': 68.45}),
                Command.create({'tax_id': self.tax_purchase_81.id, 'amount': 6.60}),
            ],
        })
        _liquidity_lines, suspense_lines, _other_lines = statement_line._seek_for_lines()

        statement_line.set_account_bank_statement_line(
            suspense_lines.id,
            self.company_data['default_account_expense'].id,
        )

        base_26 = statement_line.line_ids.filtered(
            lambda line: self.tax_purchase_26 in line.tax_ids
        )
        base_81 = statement_line.line_ids.filtered(
            lambda line: self.tax_purchase_81 in line.tax_ids
        )
        tax_26 = statement_line.line_ids.filtered(
            lambda line: line.tax_line_id == self.tax_purchase_26
        )
        tax_81 = statement_line.line_ids.filtered(
            lambda line: line.tax_line_id == self.tax_purchase_81
        )
        _liquidity_lines, suspense_lines, _other_lines = statement_line._seek_for_lines()

        self.assertEqual(len(base_26), 1)
        self.assertEqual(len(base_81), 1)
        self.assertEqual(len(tax_26), 1)
        self.assertEqual(len(tax_81), 1)
        self.assertAlmostEqual(base_26.amount_currency, 66.72, places=2)
        self.assertAlmostEqual(tax_26.amount_currency, 1.73, places=2)
        self.assertAlmostEqual(base_81.amount_currency, 6.11, places=2)
        self.assertAlmostEqual(tax_81.amount_currency, 0.49, places=2)
        self.assertFalse(suspense_lines)
        self.assertTrue(statement_line.is_reconciled)

    def test_tax_onchange_keeps_one_allocation_row_per_selected_tax(self):
        statement_line = self.env['account.bank.statement.line'].new({
            'journal_id': self.company_data['default_journal_bank'].id,
            'date': '2026-10-29',
            'payment_ref': 'Sequential tax selection',
            'amount': -55.05,
        })

        statement_line.hgr_tax_ids = self.tax_purchase_26
        statement_line._onchange_hgr_tax_ids()
        statement_line.hgr_tax_ids = self.tax_purchase_26 + self.tax_purchase_81
        statement_line._onchange_hgr_tax_ids()

        self.assertEqual(len(statement_line.hgr_tax_allocation_ids), 2)
        self.assertEqual(
            statement_line.hgr_tax_allocation_ids.tax_id,
            self.tax_purchase_26 + self.tax_purchase_81,
        )

    def test_multiple_quick_taxes_require_exact_gross_total(self):
        with self.assertRaisesRegex(ValidationError, 'must total'):
            self.env['account.bank.statement.line'].create({
                'journal_id': self.company_data['default_journal_bank'].id,
                'date': '2026-10-29',
                'payment_ref': 'Invalid VAT allocation',
                'amount': -75.05,
                'hgr_tax_ids': [
                    Command.set((self.tax_purchase_26 + self.tax_purchase_81).ids)
                ],
                'hgr_tax_allocation_ids': [
                    Command.create({'tax_id': self.tax_purchase_26.id, 'amount': 68.45}),
                    Command.create({'tax_id': self.tax_purchase_81.id, 'amount': 6.00}),
                ],
            })
