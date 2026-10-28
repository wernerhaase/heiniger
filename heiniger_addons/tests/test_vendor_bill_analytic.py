from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVendorBillAnalyticDistribution(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Analytic Distribution Vendor',
            'supplier_rank': 1,
        })
        cls.plan = cls.env['account.analytic.plan'].create({
            'name': 'Vendor Bill Test Plan',
        })
        cls.analytic_account = cls.env['account.analytic.account'].create({
            'name': 'Vendor Bill Test Analytic Account',
            'plan_id': cls.plan.id,
        })
        cls.expense_account = cls.env['account.account'].search([
            ('company_ids', 'in', cls.env.company.id),
            ('account_type', '=', 'expense'),
        ], limit=1)
        if not cls.expense_account:
            cls.expense_account = cls.env['account.account'].create({
                'name': 'Vendor Bill Test Expense',
                'code': 'HGRTESTEXP',
                'account_type': 'expense',
                'company_ids': [Command.set(cls.env.company.ids)],
            })
        cls.income_account = cls.env['account.account'].search([
            ('company_ids', 'in', cls.env.company.id),
            ('account_type', '=', 'income'),
        ], limit=1)
        if not cls.income_account:
            cls.income_account = cls.env['account.account'].create({
                'name': 'Vendor Bill Test Income',
                'code': 'HGRTESTINC',
                'account_type': 'income',
                'company_ids': [Command.set(cls.env.company.ids)],
            })
        cls.distribution = {str(cls.analytic_account.id): 100.0}

    def _create_move(self, move_type='in_invoice', distribution=False):
        values = {
            'move_type': move_type,
            'partner_id': self.vendor.id,
            'invoice_line_ids': [Command.create({
                'name': 'Vendor service',
                'account_id': (
                    self.expense_account.id
                    if move_type.startswith('in_')
                    else self.income_account.id
                ),
                'quantity': 1,
                'price_unit': 100,
            })],
        }
        if distribution is not False:
            values['analytic_distribution'] = distribution
        return self.env['account.move'].create(values)

    def test_header_distribution_populates_bill_lines(self):
        bill = self._create_move(distribution=self.distribution)

        self.assertEqual(
            bill.invoice_line_ids.analytic_distribution,
            self.distribution,
        )

    def test_changing_and_clearing_header_updates_bill_lines(self):
        bill = self._create_move()

        bill.analytic_distribution = self.distribution
        self.assertEqual(
            bill.invoice_line_ids.analytic_distribution,
            self.distribution,
        )

        bill.analytic_distribution = False
        self.assertFalse(bill.invoice_line_ids.analytic_distribution)

    def test_customer_invoice_is_not_changed(self):
        invoice = self._create_move(move_type='out_invoice')
        invoice.analytic_distribution = self.distribution

        self.assertFalse(invoice.invoice_line_ids.analytic_distribution)
