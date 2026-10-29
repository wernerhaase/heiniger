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

    def test_analytic_distribution_can_be_searched_by_project_customer(self):
        customer = self.env['res.partner'].create({
            'name': 'Needle Analytic Customer',
            'customer_rank': 1,
        })
        analytic_account = self.env['account.analytic.account'].create({
            'name': 'Unrelated Project Account Name',
            'plan_id': self.plan.id,
        })
        self.env['project.project'].create({
            'name': 'Customer Search Project',
            'partner_id': customer.id,
            'account_id': analytic_account.id,
        })

        results = self.env['account.analytic.account'].name_search(
            name='Needle Analytic',
        )

        self.assertIn(analytic_account.id, dict(results))

    def test_analytic_distribution_can_be_searched_by_direct_sale_order(self):
        customer = self.env['res.partner'].create({
            'name': 'Sale Order Search Customer',
            'customer_rank': 1,
        })
        analytic_account = self.env['account.analytic.account'].create({
            'name': 'Direct Sale Order Project Account',
            'plan_id': self.plan.id,
        })
        project = self.env['project.project'].create({
            'name': 'Direct Sale Order Search Project',
            'partner_id': customer.id,
            'account_id': analytic_account.id,
            'allow_billable': True,
        })
        self.env['sale.order'].create({
            'name': '2026-AN-SEARCH-DIRECT',
            'partner_id': customer.id,
            'project_id': project.id,
        })

        results = self.env['account.analytic.account'].name_search(
            name='AN-SEARCH-DIRECT',
        )

        self.assertIn(analytic_account.id, dict(results))
        self.assertEqual(analytic_account.code, '2026-AN-SEARCH-DIRECT')

    def test_analytic_distribution_can_be_searched_by_project_sale_order(self):
        customer = self.env['res.partner'].create({
            'name': 'Project Sale Order Search Customer',
            'customer_rank': 1,
        })
        analytic_account = self.env['account.analytic.account'].create({
            'name': 'Project Sale Order Account',
            'plan_id': self.plan.id,
        })
        order = self.env['sale.order'].create({
            'name': '2026-AN-SEARCH-STANDARD',
            'partner_id': customer.id,
        })
        service = self.env['product.product'].create({
            'name': 'Sale Order Search Service',
            'type': 'service',
        })
        sale_line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': service.id,
            'product_uom_qty': 1,
            'price_unit': 100,
        })
        self.env['project.project'].create({
            'name': 'Standard Sale Order Search Project',
            'partner_id': customer.id,
            'account_id': analytic_account.id,
            'allow_billable': True,
            'sale_line_id': sale_line.id,
        })

        results = self.env['account.analytic.account'].name_search(
            name='AN-SEARCH-STANDARD',
        )

        self.assertIn(analytic_account.id, dict(results))
        self.assertEqual(analytic_account.code, '2026-AN-SEARCH-STANDARD')

    def test_primary_quotation_reference_tracks_latest_direct_order(self):
        customer = self.env['res.partner'].create({
            'name': 'Stable Quotation Customer',
            'customer_rank': 1,
        })
        analytic_account = self.env['account.analytic.account'].create({
            'name': 'Stable Quotation Project',
            'plan_id': self.plan.id,
        })
        project = self.env['project.project'].create({
            'name': 'Stable Quotation Project',
            'partner_id': customer.id,
            'account_id': analytic_account.id,
            'allow_billable': True,
        })
        for name in ('2026-AN9001', '2026-AN9002'):
            self.env['sale.order'].create({
                'name': name,
                'partner_id': customer.id,
                'project_id': project.id,
            })

        self.assertEqual(analytic_account.code, '2026-AN9002')

    def test_quotation_reference_is_not_duplicated_in_display_name(self):
        analytic_account = self.env['account.analytic.account'].create({
            'name': '2026-AN-DISPLAY',
            'code': '2026-AN-DISPLAY',
            'plan_id': self.plan.id,
        })

        self.assertEqual(analytic_account.display_name, '2026-AN-DISPLAY')
