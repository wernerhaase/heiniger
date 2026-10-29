from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSupervisorTimesheet(TransactionCase):
    def setUp(self):
        super().setUp()
        self.customer = self.env['res.partner'].create({
            'name': 'Supervisor Timesheet Customer',
            'customer_rank': 1,
        })
        self.project = self.env['project.project'].create({
            'name': 'Supervisor Timesheet Project',
            'partner_id': self.customer.id,
            'allow_timesheets': True,
        })
        self.supervisor = self.env['hr.employee'].create({
            'name': 'Test Supervisor',
            'company_id': self.env.company.id,
        })
        self.worker = self.env['hr.employee'].create({
            'name': 'Test Worker',
            'company_id': self.env.company.id,
        })
        self.work_category = self.env['hgr.work.category'].create({
            'name': 'Installation Work',
        })
        self.service = self.env['product.product'].create({
            'name': 'Installation Service',
            'type': 'service',
            'list_price': 150.0,
        })
        self.order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'project_id': self.project.id,
            'order_line': [Command.create({
                'product_id': self.service.id,
                'product_uom_qty': 10.0,
                'hgr_work_category_id': self.work_category.id,
            })],
        })
        self.service_line = self.order.order_line

    def payload(self):
        return {
            'partner_id': self.customer.id,
            'project_id': self.project.id,
            'supervisor_id': self.supervisor.id,
            'date': '2026-10-28',
            'description': 'General site work',
            'lines': [{
                'employee_id': self.worker.id,
                'sale_line_id': self.service_line.id,
                'work_category_id': self.work_category.id,
                'unit_amount': 7.5,
                'name': 'Installed and tested equipment',
            }],
        }

    def test_creates_batch_and_standard_timesheet(self):
        result = self.env['hgr.supervisor.timesheet'].create_from_ui(self.payload())
        sheet = self.env['hgr.supervisor.timesheet'].browse(result['id'])
        self.assertEqual(result['count'], 1)
        self.assertEqual(sheet.description, 'General site work')
        self.assertEqual(sheet.line_ids.employee_id, self.worker)
        self.assertEqual(sheet.line_ids.sale_line_id, self.service_line)
        self.assertEqual(sheet.line_ids.work_category_id, self.work_category)
        self.assertEqual(sheet.line_ids.unit_amount, 7.5)
        self.assertEqual(sheet.timesheet_ids, sheet.line_ids.timesheet_id)
        self.assertEqual(sheet.timesheet_ids.project_id, self.project)
        self.assertEqual(sheet.timesheet_ids.employee_id, self.worker)
        self.assertEqual(sheet.timesheet_ids.so_line, self.service_line)
        self.assertEqual(
            sheet.timesheet_ids.hgr_work_category_id,
            self.work_category,
        )
        self.assertTrue(sheet.timesheet_ids.is_so_line_edited)
        self.assertEqual(sheet.timesheet_ids.name, 'Installed and tested equipment')

    def test_lists_service_items_from_linked_sale_orders(self):
        goods = self.env['product.product'].create({
            'name': 'Physical Material',
            'type': 'consu',
        })
        self.order.order_line = [Command.create({
            'product_id': goods.id,
            'product_uom_qty': 1.0,
        })]

        options = self.env['hgr.supervisor.timesheet'].get_service_sale_lines(
            self.project.id
        )

        self.assertEqual([option['id'] for option in options], [self.service_line.id])
        self.assertEqual(options[0]['work_category_id'], self.work_category.id)

    def test_manual_service_creates_standard_timesheet(self):
        payload = self.payload()
        payload['lines'][0].update({
            'sale_line_id': False,
            'manual_service_name': 'Emergency cleaning',
        })

        result = self.env['hgr.supervisor.timesheet'].create_from_ui(payload)
        sheet = self.env['hgr.supervisor.timesheet'].browse(result['id'])

        self.assertFalse(sheet.line_ids.sale_line_id)
        self.assertEqual(sheet.line_ids.manual_service_name, 'Emergency cleaning')
        self.assertFalse(sheet.timesheet_ids.so_line)
        self.assertEqual(
            sheet.timesheet_ids.hgr_manual_service_name,
            'Emergency cleaning',
        )

    def test_manual_service_is_required_without_sale_line(self):
        payload = self.payload()
        payload['lines'][0]['sale_line_id'] = False

        with self.assertRaises(ValidationError):
            self.env['hgr.supervisor.timesheet'].create_from_ui(payload)

    def test_rejects_service_from_unrelated_sale_order(self):
        other_customer = self.env['res.partner'].create({
            'name': 'Other Service Customer',
            'customer_rank': 1,
        })
        other_order = self.env['sale.order'].create({
            'partner_id': other_customer.id,
            'order_line': [Command.create({
                'product_id': self.service.id,
                'product_uom_qty': 1.0,
            })],
        })
        payload = self.payload()
        payload['lines'][0]['sale_line_id'] = other_order.order_line.id

        with self.assertRaises(ValidationError):
            self.env['hgr.supervisor.timesheet'].create_from_ui(payload)

    def test_project_selector_shows_quotation_number(self):
        quotation = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'project_id': self.project.id,
        })

        result = self.project.with_context(hgr_show_quote_no=True).name_search(
            name=self.project.name,
        )

        self.assertIn(
            (self.project.id, f'{self.project.name} — {quotation.name}'),
            result,
        )

    def test_sale_order_action_prefills_customer_and_project(self):
        quotation = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'project_id': self.project.id,
        })

        action = quotation.action_open_hgr_supervisor_timesheet()

        self.assertEqual(action['tag'], 'hgr_supervisor_timesheet')
        self.assertEqual(action['context']['default_partner_id'], self.customer.id)
        self.assertEqual(action['context']['default_project_id'], self.project.id)
        self.assertEqual(action['context']['default_company_id'], quotation.company_id.id)

    def test_rejects_project_from_another_customer(self):
        payload = self.payload()
        payload['partner_id'] = self.env['res.partner'].create({
            'name': 'Other Customer',
            'customer_rank': 1,
        }).id
        with self.assertRaises(ValidationError):
            self.env['hgr.supervisor.timesheet'].create_from_ui(payload)

    def test_rejects_incomplete_worker_line(self):
        payload = self.payload()
        payload['lines'][0]['unit_amount'] = 0
        with self.assertRaises(ValidationError):
            self.env['hgr.supervisor.timesheet'].create_from_ui(payload)

    def test_work_category_is_required(self):
        payload = self.payload()
        payload['lines'][0]['work_category_id'] = False

        with self.assertRaises(ValidationError):
            self.env['hgr.supervisor.timesheet'].create_from_ui(payload)
