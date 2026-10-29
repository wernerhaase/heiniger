from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHgrProfitability(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_manager = cls.env.user
        cls.project_manager.group_ids += cls.env.ref('project.group_project_manager')
        cls.plan = cls.env['account.analytic.plan'].create({'name': 'Project Profitability Plan'})
        cls.account = cls.env['account.analytic.account'].create({
            'name': 'Profitability Analytic Account',
            'plan_id': cls.plan.id,
            'company_id': cls.env.company.id,
        })
        cls.customer = cls.env['res.partner'].create({'name': 'Profitability Customer'})
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Profitability Vendor',
            'supplier_rank': 1,
        })
        cls.project = cls.env['project.project'].create({
            'name': 'Profitability Project',
            'partner_id': cls.customer.id,
            'account_id': cls.account.id,
            'allow_timesheets': True,
        })
        cls.expense_account = cls.env['account.account'].search([
            ('company_ids', 'in', cls.env.company.id),
            ('account_type', '=', 'expense'),
        ], limit=1)
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Manual Profitability Worker',
            'company_id': cls.env.company.id,
        })
        cls.work_category = cls.env['hgr.work.category'].create({
            'name': 'Installation Work',
        })
        cls.service = cls.env['product.product'].create({
            'name': 'Manual Profitability Service',
            'type': 'service',
            'list_price': 200.0,
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.customer.id,
            'project_id': cls.project.id,
            'order_line': [Command.create({
                'product_id': cls.service.id,
                'product_uom_qty': 10.0,
                'hgr_work_category_id': cls.work_category.id,
            })],
        })
        cls.service_line = cls.order.order_line

    def test_vendor_bill_distribution_is_prorated(self):
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor.id,
            'invoice_line_ids': [Command.create({
                'name': 'Allocated material',
                'account_id': self.expense_account.id,
                'quantity': 1,
                'price_unit': 1000,
                'analytic_distribution': {str(self.account.id): 40.0},
            })],
        })
        summary = self.project._hgr_profitability_summary()

        self.assertEqual(summary['vendor_cost_draft'], 400.0)
        self.assertEqual(summary['vendor_details'][0]['allocation_percent'], 40.0)
        self.assertEqual(summary['vendor_details'][0]['move_id'], bill.id)

    def test_posted_vendor_bill_is_reported_as_material(self):
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor.id,
            'invoice_date': '2026-10-28',
            'invoice_line_ids': [Command.create({
                'name': 'Posted allocated material',
                'account_id': self.expense_account.id,
                'quantity': 1,
                'price_unit': 301.67,
                'analytic_distribution': {str(self.account.id): 100.0},
            })],
        })
        bill.action_post()

        summary = self.project._hgr_profitability_summary()

        self.assertEqual(summary['vendor_cost_posted'], 301.67)
        self.assertEqual(summary['total_cost'], 301.67)
        self.assertEqual(summary['vendor_details'][0]['move_id'], bill.id)
        self.assertEqual(summary['vendor_details'][0]['allocated_amount'], 301.67)

    def test_non_timesheet_analytic_cost_is_reported_as_material(self):
        material = self.env['account.analytic.line'].create({
            'name': 'Warehouse material allocation',
            'date': '2026-10-28',
            'account_id': self.account.id,
            'amount': -125.0,
        })

        summary = self.project._hgr_profitability_summary()

        self.assertEqual(summary['vendor_cost_posted'], 125.0)
        self.assertEqual(summary['vendor_details'][0]['id'], material.id)
        self.assertEqual(summary['vendor_details'][0]['allocated_amount'], 125.0)

    def test_sale_order_button_opens_filtered_profitability(self):
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'project_id': self.project.id,
        })
        action = order.action_open_hgr_profitability()

        self.assertEqual(action['tag'], 'hgr_project_profitability')
        self.assertEqual(action['context']['default_project_id'], self.project.id)
        self.assertEqual(action['context']['default_sale_order_id'], order.id)

    def test_quoted_time_uom_is_converted_to_hours(self):
        day_uom = self.env.ref('uom.product_uom_day')
        service = self.env['product.product'].create({
            'name': 'Profitability Consulting Day',
            'type': 'service',
            'uom_id': day_uom.id,
            'list_price': 1000.0,
        })
        self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'project_id': self.project.id,
            'order_line': [Command.create({
                'product_id': service.id,
                'product_uom_qty': 2.0,
                'product_uom_id': day_uom.id,
            })],
        })

        summary = self.project._hgr_profitability_summary()

        self.assertEqual(summary['quoted_hours'], 16.0)

    def test_labour_comparison_groups_quote_and_actual_by_work_category(self):
        hour_uom = self.env.ref('uom.product_uom_hour')
        service = self.env['product.product'].create({
            'name': 'Tagged Installation Hours',
            'type': 'service',
            'uom_id': hour_uom.id,
            'list_price': 100.0,
        })
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'project_id': self.project.id,
            'order_line': [Command.create({
                'product_id': service.id,
                'product_uom_qty': 12.0,
                'product_uom_id': hour_uom.id,
                'hgr_work_category_id': self.work_category.id,
            })],
        })
        self.env['account.analytic.line'].create({
            'date': '2026-10-28',
            'project_id': self.project.id,
            'account_id': self.account.id,
            'employee_id': self.employee.id,
            'so_line': order.order_line.id,
            'hgr_work_category_id': self.work_category.id,
            'unit_amount': 7.5,
            'name': 'Tagged installation',
        })

        summary = self.project._hgr_profitability_summary()
        row = next(
            item for item in summary['labour_comparison']
            if item['category'] == self.work_category.name
        )

        self.assertEqual(row['quoted_hours'], 12.0)
        self.assertEqual(row['actual_hours'], 7.5)
        self.assertEqual(row['balance_hours'], 4.5)

    def test_quoted_lines_are_split_by_time_uom_not_product_type(self):
        hour_uom = self.env.ref('uom.product_uom_hour')
        unit_uom = self.env.ref('uom.product_uom_unit')
        hourly_service = self.env['product.product'].create({
            'name': 'Hourly Service Classification',
            'type': 'service',
            'uom_id': hour_uom.id,
            'list_price': 95.0,
        })
        fixed_service = self.env['product.product'].create({
            'name': 'Fixed Service Classification',
            'type': 'service',
            'uom_id': unit_uom.id,
            'list_price': 250.0,
        })
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'project_id': self.project.id,
            'order_line': [
                Command.create({
                    'product_id': hourly_service.id,
                    'product_uom_qty': 3.0,
                    'product_uom_id': hour_uom.id,
                }),
                Command.create({
                    'product_id': fixed_service.id,
                    'product_uom_qty': 2.0,
                    'product_uom_id': unit_uom.id,
                }),
            ],
        })

        summary = self.project._hgr_profitability_summary()
        labour_keys = {item['key'] for item in summary['labour_comparison']}
        material_keys = {item['key'] for item in summary['material_comparison']}
        hourly_line = order.order_line.filtered(
            lambda line: line.product_id == hourly_service
        )
        fixed_line = order.order_line.filtered(
            lambda line: line.product_id == fixed_service
        )

        self.assertIn(f'service-{hourly_line.id}', labour_keys)
        self.assertNotIn(f'product-{hourly_service.id}', material_keys)
        self.assertIn(f'product-{fixed_service.id}', material_keys)
        self.assertNotIn(f'service-{fixed_line.id}', labour_keys)

    def test_detached_std_unit_is_classified_as_labour(self):
        std_uom = self.env['uom.uom'].create({
            'name': 'Std.',
            'relative_factor': 1.0,
        })
        service = self.env['product.product'].create({
            'name': 'Detached Std Labour',
            'type': 'service',
            'uom_id': std_uom.id,
            'list_price': 95.0,
        })
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'project_id': self.project.id,
            'order_line': [Command.create({
                'product_id': service.id,
                'product_uom_qty': 4.0,
                'product_uom_id': std_uom.id,
            })],
        })

        summary = self.project._hgr_profitability_summary()
        labour_keys = {item['key'] for item in summary['labour_comparison']}
        material_keys = {item['key'] for item in summary['material_comparison']}

        self.assertIn(f'service-{order.order_line.id}', labour_keys)
        self.assertNotIn(f'product-{service.id}', material_keys)
        self.assertEqual(summary['quoted_hours'], 4.0)

    def test_material_comparison_matches_quoted_and_actual_product(self):
        material = self.env['product.product'].create({
            'name': 'Quoted Paint Material',
            'type': 'consu',
            'list_price': 500.0,
        })
        self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'project_id': self.project.id,
            'order_line': [Command.create({
                'product_id': material.id,
                'product_uom_qty': 2.0,
                'price_unit': 500.0,
            })],
        })
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor.id,
            'invoice_date': '2026-10-28',
            'invoice_line_ids': [Command.create({
                'name': 'Actual paint material',
                'product_id': material.id,
                'account_id': self.expense_account.id,
                'quantity': 2.0,
                'price_unit': 350.0,
                'analytic_distribution': {str(self.account.id): 100.0},
            })],
        })
        bill.action_post()

        summary = self.project._hgr_profitability_summary()
        row = next(
            item for item in summary['material_comparison']
            if item['product'] == material.display_name
        )

        self.assertEqual(row['quoted_amount'], 1000.0)
        self.assertEqual(row['actual_amount'], 700.0)
        self.assertEqual(row['balance_amount'], 300.0)

    def test_double_validated_manual_material_cost_is_reported(self):
        payload = {
            'entry_type': 'material',
            'project_id': self.project.id,
            'date': '2026-10-28',
            'amount': 250.0,
            'description': 'Warehouse material issue 4711',
        }
        validation = self.env['project.project'].check_hgr_manual_profitability_entry(
            payload
        )

        self.env['project.project'].create_hgr_manual_profitability_entry(
            payload, validation['validation_token']
        )
        summary = self.project._hgr_profitability_summary()

        self.assertEqual(summary['manual_material_cost'], 250.0)
        self.assertEqual(summary['total_cost'], 250.0)
        self.assertEqual(summary['manual_material_details'][0]['description'], payload['description'])

    def test_manual_material_uses_product_as_missing_description(self):
        material = self.env['product.product'].create({
            'name': 'Manual Cost Product',
            'type': 'consu',
        })
        payload = {
            'entry_type': 'material',
            'project_id': self.project.id,
            'product_id': material.id,
            'date': '2026-10-29',
            'amount': 20.0,
            'description': '',
        }

        validation = self.env['project.project'].check_hgr_manual_profitability_entry(
            payload
        )
        result = self.env['project.project'].create_hgr_manual_profitability_entry(
            payload, validation['validation_token']
        )
        manual_cost = self.env['hgr.profitability.manual.cost'].browse(result['id'])

        self.assertEqual(manual_cost.description, material.display_name)

    def test_manual_entry_must_be_unchanged_after_validation(self):
        payload = {
            'entry_type': 'material',
            'project_id': self.project.id,
            'date': '2026-10-28',
            'amount': 100.0,
            'description': 'Validated warehouse cost',
        }
        validation = self.env['project.project'].check_hgr_manual_profitability_entry(
            payload
        )
        payload['amount'] = 200.0

        with self.assertRaises(ValidationError):
            self.env['project.project'].create_hgr_manual_profitability_entry(
                payload, validation['validation_token']
            )

    def test_manual_labour_rejects_matching_timesheet(self):
        description = 'Already entered installation work'
        self.env['account.analytic.line'].create({
            'date': '2026-10-28',
            'project_id': self.project.id,
            'employee_id': self.employee.id,
            'so_line': self.service_line.id,
            'is_so_line_edited': True,
            'unit_amount': 4.0,
            'name': description,
        })
        payload = {
            'entry_type': 'labour',
            'project_id': self.project.id,
            'employee_id': self.employee.id,
            'sale_line_id': self.service_line.id,
            'date': '2026-10-28',
            'hours': 4.0,
            'description': description,
            'work_category_id': self.work_category.id,
        }

        with self.assertRaises(ValidationError):
            self.env['project.project'].check_hgr_manual_profitability_entry(payload)

    def test_double_validated_manual_labour_creates_standard_timesheet(self):
        payload = {
            'entry_type': 'labour',
            'project_id': self.project.id,
            'employee_id': self.employee.id,
            'sale_line_id': self.service_line.id,
            'date': '2026-10-28',
            'hours': 3.5,
            'description': 'Manual emergency installation',
            'work_category_id': self.work_category.id,
        }
        validation = self.env['project.project'].check_hgr_manual_profitability_entry(
            payload
        )

        result = self.env['project.project'].create_hgr_manual_profitability_entry(
            payload, validation['validation_token']
        )
        timesheet = self.env['account.analytic.line'].browse(result['id'])

        self.assertEqual(timesheet.project_id, self.project)
        self.assertEqual(timesheet.employee_id, self.employee)
        self.assertEqual(timesheet.so_line, self.service_line)
        self.assertEqual(timesheet.unit_amount, 3.5)
        self.assertEqual(timesheet.hgr_profitability_manual_type, 'labour')
        self.assertEqual(timesheet.hgr_work_category_id, self.work_category)

    def test_double_validated_manual_labour_accepts_manual_service(self):
        payload = {
            'entry_type': 'labour',
            'project_id': self.project.id,
            'employee_id': self.employee.id,
            'sale_line_id': False,
            'manual_service_name': 'Emergency call-out',
            'date': '2026-10-29',
            'hours': 2.25,
            'description': 'Unplanned emergency service',
            'work_category_id': self.work_category.id,
        }
        validation = self.env['project.project'].check_hgr_manual_profitability_entry(
            payload
        )

        result = self.env['project.project'].create_hgr_manual_profitability_entry(
            payload, validation['validation_token']
        )
        timesheet = self.env['account.analytic.line'].browse(result['id'])
        summary = self.project._hgr_profitability_summary()

        self.assertFalse(timesheet.so_line)
        self.assertEqual(timesheet.hgr_manual_service_name, 'Emergency call-out')
        self.assertEqual(summary['timesheet_details'][0]['service'], 'Emergency call-out')

    def test_manual_labour_uses_service_as_missing_description(self):
        payload = {
            'entry_type': 'labour',
            'project_id': self.project.id,
            'employee_id': self.employee.id,
            'sale_line_id': self.service_line.id,
            'date': '2026-10-29',
            'hours': 1.5,
            'description': '',
            'work_category_id': self.work_category.id,
        }

        validation = self.env['project.project'].check_hgr_manual_profitability_entry(
            payload
        )
        result = self.env['project.project'].create_hgr_manual_profitability_entry(
            payload, validation['validation_token']
        )
        timesheet = self.env['account.analytic.line'].browse(result['id'])

        self.assertEqual(timesheet.name, self.service_line.display_name)

    def test_manual_labour_requires_sale_line_or_manual_service(self):
        payload = {
            'entry_type': 'labour',
            'project_id': self.project.id,
            'employee_id': self.employee.id,
            'sale_line_id': False,
            'manual_service_name': '',
            'date': '2026-10-29',
            'hours': 1.0,
            'description': 'Missing service',
            'work_category_id': self.work_category.id,
        }

        with self.assertRaises(ValidationError):
            self.env['project.project'].check_hgr_manual_profitability_entry(payload)
