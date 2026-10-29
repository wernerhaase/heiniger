from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestBankStatementQuickTax(AccountTestInvoicingCommon):

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
