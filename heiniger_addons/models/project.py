
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class HgrProfitabilityManualCost(models.Model):
    _name = 'hgr.profitability.manual.cost'
    _description = 'Manual Profitability Material Cost'
    _order = 'date desc, id desc'

    project_id = fields.Many2one('project.project', required=True, ondelete='cascade', index=True)
    date = fields.Date(required=True, index=True)
    description = fields.Char(required=True)
    amount = fields.Monetary(required=True, currency_field='currency_id')
    company_id = fields.Many2one(related='project_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True)
    validated_by_id = fields.Many2one('res.users', required=True, readonly=True)


class Task(models.Model):
	_inherit = 'project.task'

	employee_ids = fields.Many2many('hr.employee', relation='project_task_employee_rel', column1='task_id', column2='employee_id', string='Employees', context={'active_test': False}, tracking=True)


class Project(models.Model):
    _inherit = 'project.project'

    def _hgr_check_profitability_access(self):
        if not (
            self.env.user.has_group('account.group_account_invoice')
            or self.env.user.has_group('account.group_account_readonly')
            or self.env.user.has_group('project.group_project_manager')
        ):
            raise AccessError(_('You are not allowed to view project profitability.'))

    @api.model
    def _hgr_analytic_share(self, distribution, analytic_account):
        """Return the share assigned to one account in an analytic JSON value."""
        account_id = str(analytic_account.id)
        return sum(
            percentage
            for account_keys, percentage in (distribution or {}).items()
            if account_id in str(account_keys).split(',')
        ) / 100.0

    def _hgr_profitability_sale_orders(self):
        self.ensure_one()
        orders = self.sale_order_id | self.reinvoiced_sale_order_id
        orders |= self.env['sale.order'].search([
            ('project_id', '=', self.id),
            ('state', '!=', 'cancel'),
        ])
        return orders.filtered(lambda order: order.state != 'cancel')

    def _hgr_profitability_service_lines(self):
        self.ensure_one()
        return self.sudo()._hgr_profitability_sale_orders().order_line.filtered(
            lambda line: not line.display_type and line.product_id.type == 'service'
        )

    @api.model
    def get_hgr_profitability_manual_options(self, project_id):
        self._hgr_check_profitability_access()
        project = self.browse(project_id).exists()
        if not project:
            return {'services': []}
        project.check_access('read')
        return {
            'services': [
                {'id': line.id, 'name': line.display_name}
                for line in project._hgr_profitability_service_lines()
            ],
        }

    @api.model
    def _hgr_normalize_manual_entry(self, payload):
        if not isinstance(payload, dict):
            raise ValidationError(_('Invalid manual profitability data.'))
        entry_type = payload.get('entry_type')
        if entry_type not in ('labour', 'material'):
            raise ValidationError(_('Select Labour or Material Cost.'))
        try:
            project_id = int(payload.get('project_id') or 0)
            employee_id = int(payload.get('employee_id') or 0)
            sale_line_id = int(payload.get('sale_line_id') or 0)
            hours = float(payload.get('hours') or 0)
            amount = float(payload.get('amount') or 0)
            date = fields.Date.to_date(payload.get('date'))
        except (TypeError, ValueError):
            raise ValidationError(_('The manual entry contains an invalid number.'))
        description = (payload.get('description') or '').strip()
        manual_service_name = (payload.get('manual_service_name') or '').strip()
        return {
            'entry_type': entry_type,
            'project_id': project_id,
            'employee_id': employee_id,
            'sale_line_id': sale_line_id,
            'manual_service_name': manual_service_name,
            'date': fields.Date.to_string(date) if date else False,
            'hours': round(hours, 4),
            'amount': round(amount, 2),
            'description': description,
        }

    @api.model
    def _hgr_validate_manual_entry(self, payload):
        values = self._hgr_normalize_manual_entry(payload)
        project = self.browse(values['project_id']).exists()
        if not project or not project.account_id or not values['date'] or not values['description']:
            raise ValidationError(_('Project, date, and description are required.'))
        project.check_access('read')
        if project.company_id and project.company_id != self.env.company:
            raise ValidationError(_('The project must belong to the active company.'))

        AnalyticLine = self.env['account.analytic.line'].sudo()
        if values['entry_type'] == 'labour':
            employee = self.env['hr.employee'].sudo().browse(values['employee_id']).exists()
            sale_line = self.env['sale.order.line'].sudo().browse(values['sale_line_id']).exists()
            if not employee or (not sale_line and not values['manual_service_name']) or values['hours'] <= 0:
                raise ValidationError(_('Employee, service, and positive hours are required.'))
            if values['hours'] > 24:
                raise ValidationError(_('Hours cannot exceed 24 for one employee.'))
            if sale_line and sale_line not in project._hgr_profitability_service_lines():
                raise ValidationError(_('The service must come from a sales order linked to this project.'))
            if sale_line:
                values['manual_service_name'] = ''
            if project.company_id and employee.company_id != project.company_id:
                raise ValidationError(_('The employee and project must belong to the same company.'))
            duplicate_domain = [
                ('project_id', '=', project.id),
                ('date', '=', values['date']),
                ('employee_id', '=', employee.id),
            ]
            if sale_line:
                duplicate_domain.append(('so_line', '=', sale_line.id))
            else:
                duplicate_domain.extend([
                    ('so_line', '=', False),
                    ('hgr_manual_service_name', '=ilike', values['manual_service_name']),
                ])
            duplicate = AnalyticLine.search_count(duplicate_domain)
        else:
            if values['amount'] <= 0:
                raise ValidationError(_('Enter a positive material cost.'))
            duplicate = self.env['hgr.profitability.manual.cost'].sudo().search_count([
                ('project_id', '=', project.id),
                ('date', '=', values['date']),
                ('amount', '=', values['amount']),
                ('description', '=', values['description']),
            ])
        if duplicate:
            raise ValidationError(_(
                'A matching entry already exists. Review the Timesheets or Material tab before entering it again.'
            ))
        return values, project

    @api.model
    def _hgr_manual_entry_token(self, values):
        database_uuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid', '')
        serialized = json.dumps(values, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(
            f'{database_uuid}:{self.env.user.id}:{serialized}'.encode()
        ).hexdigest()

    @api.model
    def check_hgr_manual_profitability_entry(self, payload):
        self._hgr_check_profitability_access()
        values, _project = self._hgr_validate_manual_entry(payload)
        return {'validation_token': self._hgr_manual_entry_token(values)}

    @api.model
    def create_hgr_manual_profitability_entry(self, payload, validation_token):
        self._hgr_check_profitability_access()
        values, project = self._hgr_validate_manual_entry(payload)
        if validation_token != self._hgr_manual_entry_token(values):
            raise ValidationError(_('The entry changed after validation. Validate it again before saving.'))
        if values['entry_type'] == 'labour':
            line = self.env['account.analytic.line'].sudo().create({
                'date': values['date'],
                'project_id': project.id,
                'account_id': project.account_id.id,
                'name': values['description'],
                'hgr_profitability_manual_type': 'labour',
                'hgr_profitability_manual_user_id': self.env.user.id,
                'employee_id': values['employee_id'],
                'so_line': values['sale_line_id'] or False,
                'is_so_line_edited': bool(values['sale_line_id']),
                'hgr_manual_service_name': values['manual_service_name'],
                'unit_amount': values['hours'],
            })
        else:
            line = self.env['hgr.profitability.manual.cost'].sudo().create({
                'project_id': project.id,
                'date': values['date'],
                'description': values['description'],
                'amount': values['amount'],
                'validated_by_id': self.env.user.id,
            })
        return {'id': line.id}

    @api.model
    def _hgr_uom_root(self, uom):
        """Return the reference root used by Odoo 19 to group related UoMs."""
        while uom.relative_uom_id:
            uom = uom.relative_uom_id
        return uom

    def _hgr_profitability_summary(self, date_from=False, date_to=False, sale_order=False):
        self.ensure_one()
        account = self.account_id
        company = self.company_id or self.env.company
        currency = company.currency_id
        date_domain = []
        if date_from:
            date_domain.append(('date', '>=', date_from))
        if date_to:
            date_domain.append(('date', '<=', date_to))

        timesheets = self.env['account.analytic.line'].search([
            ('project_id', '=', self.id),
            ('employee_id', '!=', False),
            *date_domain,
        ], order='date desc, id desc')
        hour_uom = self.env.ref('uom.product_uom_hour')
        actual_hours = sum(
            (line.product_uom_id or company.project_time_mode_id)._compute_quantity(
                line.unit_amount, hour_uom
            )
            for line in timesheets
        )
        labor_cost = -sum(timesheets.mapped('amount'))

        invoice_line_domain = [
            ('move_id.move_type', 'in', ('in_invoice', 'in_refund', 'in_receipt')),
            ('parent_state', 'in', ('draft', 'posted')),
            ('display_type', '=', 'product'),
            ('analytic_distribution', 'in', account.ids),
            *date_domain,
        ]
        vendor_lines = self.env['account.move.line'].search(
            invoice_line_domain, order='date desc, id desc'
        ) if account else self.env['account.move.line']
        vendor_cost_posted = 0.0
        vendor_cost_draft = 0.0
        vendor_details = []
        for line in vendor_lines:
            share = self._hgr_analytic_share(line.analytic_distribution, account)
            allocated_amount = line.balance * share
            if line.parent_state == 'posted':
                vendor_cost_posted += allocated_amount
            else:
                vendor_cost_draft += allocated_amount
            vendor_details.append({
                'id': line.id,
                'move_id': line.move_id.id,
                'invoice': line.move_id.name or line.move_id.ref or _('Draft'),
                'date': fields.Date.to_string(line.date),
                'vendor': line.partner_id.display_name or '',
                'description': line.name or '',
                'product': line.product_id.display_name or '',
                'allocation_percent': share * 100.0,
                'allocated_amount': currency.round(allocated_amount),
                'state': line.parent_state,
                'source': 'vendor_bill',
            })

        manual_material_lines = self.env['hgr.profitability.manual.cost'].sudo().search([
            ('project_id', '=', self.id),
            *date_domain,
        ], order='date desc, id desc')
        manual_material_cost = sum(manual_material_lines.mapped('amount'))
        manual_material_details = [{
            'id': line.id,
            'date': fields.Date.to_string(line.date),
            'description': line.description or '',
            'allocated_amount': currency.round(line.amount),
            'entered_by': line.validated_by_id.name or '',
            'source': 'manual',
        } for line in manual_material_lines]

        orders = sale_order or self._hgr_profitability_sale_orders()
        linked_revenue_lines = orders.order_line.invoice_lines.filtered_domain([
            ('move_id.move_type', 'in', ('out_invoice', 'out_refund')),
            ('parent_state', 'in', ('draft', 'posted')),
            ('display_type', '=', 'product'),
            *date_domain,
        ])
        revenue_domain = [
            ('move_id.move_type', 'in', ('out_invoice', 'out_refund')),
            ('parent_state', 'in', ('draft', 'posted')),
            ('display_type', '=', 'product'),
            ('analytic_distribution', 'in', account.ids),
            ('id', 'not in', linked_revenue_lines.ids),
            *date_domain,
        ]
        analytic_revenue_lines = self.env['account.move.line'].search(revenue_domain) if account else self.env['account.move.line']
        revenue_lines = linked_revenue_lines | analytic_revenue_lines
        revenue_posted = revenue_draft = 0.0
        for line in revenue_lines:
            share = (
                1.0
                if line in linked_revenue_lines
                else self._hgr_analytic_share(line.analytic_distribution, account)
            )
            amount = -line.balance * share
            if line.parent_state == 'posted':
                revenue_posted += amount
            else:
                revenue_draft += amount

        quoted_amount = sum(
            order.currency_id._convert(
                order.amount_untaxed,
                currency,
                company,
                order.date_order or fields.Date.context_today(self),
            )
            for order in orders
        )
        quoted_hours = 0.0
        for line in orders.order_line.filtered(lambda item: not item.display_type and item.product_uom_id):
            if self._hgr_uom_root(line.product_uom_id) == self._hgr_uom_root(hour_uom):
                quoted_hours += line.product_uom_id._compute_quantity(
                    line.product_uom_qty, hour_uom
                )

        total_cost = labor_cost + vendor_cost_posted + manual_material_cost
        margin = revenue_posted - total_cost
        margin_percent = revenue_posted and margin / revenue_posted * 100.0 or 0.0
        timesheet_details = [{
            'id': line.id,
            'date': fields.Date.to_string(line.date),
            'employee': line.employee_id.name or '',
            'service': line.hgr_manual_service_name or line.so_line.display_name or '',
            'task': line.task_id.display_name or '',
            'description': line.name or '',
            'hours': (line.product_uom_id or company.project_time_mode_id)._compute_quantity(
                line.unit_amount, hour_uom
            ),
            'cost': currency.round(-line.amount),
        } for line in timesheets]

        return {
            'id': self.id,
            'name': self.display_name,
            'customer': self.partner_id.display_name or '',
            'analytic_account': account.display_name or '',
            'currency_id': currency.id,
            'quoted_amount': currency.round(quoted_amount),
            'quoted_hours': quoted_hours,
            'actual_hours': actual_hours,
            'hours_variance': quoted_hours - actual_hours,
            'labor_cost': currency.round(labor_cost),
            'vendor_cost_posted': currency.round(vendor_cost_posted),
            'vendor_cost_draft': currency.round(vendor_cost_draft),
            'manual_material_cost': currency.round(manual_material_cost),
            'total_cost': currency.round(total_cost),
            'revenue_posted': currency.round(revenue_posted),
            'revenue_draft': currency.round(revenue_draft),
            'margin': currency.round(margin),
            'margin_percent': margin_percent,
            'vendor_bill_count': len(vendor_lines.move_id),
            'timesheet_count': len(timesheets),
            'invoice_count': len(revenue_lines.move_id),
            'vendor_details': vendor_details,
            'manual_material_details': manual_material_details,
            'timesheet_details': timesheet_details,
        }

    @api.model
    def get_hgr_profitability_report(
        self, project_id=False, date_from=False, date_to=False, sale_order_id=False
    ):
        self._hgr_check_profitability_access()
        project = self.browse(project_id).exists() if project_id else self
        if project and not project.account_id:
            project = self
        projects = project or self.search([
            ('active', '=', True),
            ('account_id', '!=', False),
            '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id),
        ], order='name', limit=200)
        sale_order = self.env['sale.order'].browse(sale_order_id).exists() if sale_order_id else False
        summaries = [
            record._hgr_profitability_summary(
                date_from=date_from,
                date_to=date_to,
                sale_order=(
                    sale_order
                    if sale_order and record in (sale_order.project_id | sale_order.project_ids)
                    else False
                ),
            )
            for record in projects
        ]
        currency = (projects[:1].company_id or self.env.company).currency_id
        total_keys = (
            'quoted_amount', 'quoted_hours', 'actual_hours', 'hours_variance',
            'labor_cost', 'vendor_cost_posted', 'vendor_cost_draft', 'total_cost',
            'manual_material_cost',
            'revenue_posted', 'revenue_draft', 'margin',
        )
        totals = {key: sum(item[key] for item in summaries) for key in total_keys}
        totals['margin_percent'] = (
            totals['revenue_posted']
            and totals['margin'] / totals['revenue_posted'] * 100.0
            or 0.0
        )
        return {
            'currency_id': currency.id,
            'projects': summaries,
            'totals': totals,
            'selected_project_id': projects.id if len(projects) == 1 else False,
            'date_from': date_from or False,
            'date_to': date_to or False,
        }

    @api.depends('name', 'sale_order_id.name', 'reinvoiced_sale_order_id.name')
    @api.depends_context('hgr_show_quote_no')
    def _compute_display_name(self):
        super()._compute_display_name()
        if not self.env.context.get('hgr_show_quote_no'):
            return

        # Quotations created from a CRM opportunity can point directly to the
        # project without being the project's default sales order line.
        direct_orders = self.env['sale.order'].sudo().search(
            [('project_id', 'in', self.ids)], order='id desc'
        )
        direct_order_by_project = {}
        for order in direct_orders:
            direct_order_by_project.setdefault(order.project_id.id, order)

        for project in self:
            project_sudo = project.sudo()
            order = (
                project_sudo.sale_order_id
                or direct_order_by_project.get(project.id)
                or project_sudo.reinvoiced_sale_order_id
            )
            if order:
                project.display_name = f'{project.display_name} — {order.name}'
