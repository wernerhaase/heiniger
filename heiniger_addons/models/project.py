
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
    product_id = fields.Many2one('product.product', string='Product', ondelete='restrict', index=True)
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
            work_category_id = int(payload.get('work_category_id') or 0)
            product_id = int(payload.get('product_id') or 0)
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
            'work_category_id': work_category_id,
            'product_id': product_id,
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
            work_category = self.env['hgr.work.category'].browse(
                values['work_category_id']
            ).exists()
            if (
                not employee
                or (not sale_line and not values['manual_service_name'])
                or not work_category
                or values['hours'] <= 0
            ):
                raise ValidationError(_(
                    'Employee, service, work category, and positive hours are required.'
                ))
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
            product = self.env['product.product'].browse(values['product_id']).exists()
            values['product_id'] = product.id or False
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
                'hgr_work_category_id': values['work_category_id'],
                'unit_amount': values['hours'],
            })
        else:
            line = self.env['hgr.profitability.manual.cost'].sudo().create({
                'project_id': project.id,
                'date': values['date'],
                'description': values['description'],
                'product_id': values['product_id'] or False,
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

        analytic_lines = self.env['account.analytic.line']
        if account:
            analytic_selectors = [
                ('project_id', '=', self.id),
                ('account_id', '=', account.id),
            ]
            plan_account_field = account.plan_id._column_name()
            if plan_account_field != 'account_id':
                analytic_selectors.append((plan_account_field, '=', account.id))
            analytic_lines = analytic_lines.search([
                *(['|'] * (len(analytic_selectors) - 1)),
                *analytic_selectors,
                *date_domain,
            ], order='date desc, id desc')
        timesheets = analytic_lines.filtered(lambda line: line.employee_id)
        material_lines = (analytic_lines - timesheets).filtered(
            lambda line: line.analytic_profitability == 'loss'
        )
        timesheets = timesheets.filtered_domain([
            ('employee_id', '!=', False),
        ])
        hour_uom = self.env.ref('uom.product_uom_hour')
        actual_hours = sum(
            (line.product_uom_id or company.project_time_mode_id)._compute_quantity(
                line.unit_amount, hour_uom
            )
            for line in timesheets
        )
        labor_cost = -sum(timesheets.mapped('amount'))

        draft_invoice_line_domain = [
            ('move_id.move_type', 'in', ('in_invoice', 'in_refund', 'in_receipt')),
            ('parent_state', '=', 'draft'),
            ('display_type', '=', 'product'),
            ('analytic_distribution', 'in', account.ids),
            *date_domain,
        ]
        draft_vendor_lines = self.env['account.move.line'].search(
            draft_invoice_line_domain, order='date desc, id desc'
        ) if account else self.env['account.move.line']
        vendor_cost_posted = -sum(material_lines.mapped('amount'))
        vendor_cost_draft = 0.0
        vendor_details = [{
            'id': line.id,
            'detail_key': f'analytic-{line.id}',
            'move_id': line.move_line_id.move_id.id or False,
            'invoice': (
                line.move_line_id.move_id.name
                or line.move_line_id.move_id.ref
                or line.ref
                or _('Analytic Entry')
            ),
            'date': fields.Date.to_string(line.date),
            'vendor': line.partner_id.display_name or '',
            'description': line.name or '',
            'product': line.product_id.display_name or '',
            'product_id': line.product_id.id or False,
            'quantity': line.unit_amount or 0.0,
            'allocation_percent': 100.0,
            'allocated_amount': currency.round(-line.amount),
            'state': 'posted',
            'source': line.category or 'analytic',
        } for line in material_lines]
        for line in draft_vendor_lines:
            share = self._hgr_analytic_share(line.analytic_distribution, account)
            allocated_amount = line.balance * share
            vendor_cost_draft += allocated_amount
            vendor_details.append({
                'id': line.id,
                'detail_key': f'draft-vendor-{line.id}',
                'move_id': line.move_id.id,
                'invoice': line.move_id.name or line.move_id.ref or _('Draft'),
                'date': fields.Date.to_string(line.date),
                'vendor': line.partner_id.display_name or '',
                'description': line.name or '',
                'product': line.product_id.display_name or '',
                'product_id': line.product_id.id or False,
                'quantity': (line.quantity or 0.0) * share,
                'allocation_percent': share * 100.0,
                'allocated_amount': currency.round(allocated_amount),
                'state': 'draft',
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
            'product': line.product_id.display_name or '',
            'product_id': line.product_id.id or False,
            'quantity': 0.0,
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
        quoted_lines = orders.order_line.filtered(
            lambda item: not item.display_type and item.product_uom_id
        )
        for line in quoted_lines:
            if self._hgr_uom_root(line.product_uom_id) == self._hgr_uom_root(hour_uom):
                quoted_hours += line.product_uom_id._compute_quantity(
                    line.product_uom_qty, hour_uom
                )

        labour_groups = {}

        def labour_group(key, category):
            return labour_groups.setdefault(key, {
                'key': key,
                'category': category,
                'quoted_hours': 0.0,
                'actual_hours': 0.0,
                'balance_hours': 0.0,
                'cost': 0.0,
                'entries': 0,
            })

        for line in quoted_lines:
            if self._hgr_uom_root(line.product_uom_id) != self._hgr_uom_root(hour_uom):
                continue
            category = line.hgr_work_category_id
            key = f'category-{category.id}' if category else f'service-{line.id}'
            label = category.display_name if category else line.display_name
            labour_group(key, label)['quoted_hours'] += line.product_uom_id._compute_quantity(
                line.product_uom_qty, hour_uom
            )

        for line in timesheets:
            category = line.hgr_work_category_id or line.so_line.hgr_work_category_id
            if category:
                key = f'category-{category.id}'
                label = category.display_name
            elif line.so_line:
                key = f'service-{line.so_line.id}'
                label = line.so_line.display_name
            else:
                label = line.hgr_manual_service_name or _('Uncategorised Labour')
                key = f'manual-{label}'
            group = labour_group(key, label)
            group['actual_hours'] += (
                line.product_uom_id or company.project_time_mode_id
            )._compute_quantity(line.unit_amount, hour_uom)
            group['cost'] += -line.amount
            group['entries'] += 1

        labour_comparison = []
        for group in labour_groups.values():
            group['quoted_hours'] = round(group['quoted_hours'], 4)
            group['actual_hours'] = round(group['actual_hours'], 4)
            group['balance_hours'] = round(
                group['quoted_hours'] - group['actual_hours'], 4
            )
            group['cost'] = currency.round(group['cost'])
            labour_comparison.append(group)
        labour_comparison.sort(key=lambda item: item['category'])

        material_groups = {}

        def material_group(key, product):
            return material_groups.setdefault(key, {
                'key': key,
                'product': product,
                'quoted_quantity': 0.0,
                'actual_quantity': 0.0,
                'quoted_amount': 0.0,
                'actual_amount': 0.0,
                'balance_amount': 0.0,
                'entries': 0,
            })

        for line in quoted_lines.filtered(lambda item: item.product_id.type != 'service'):
            product = line.product_id
            group = material_group(f'product-{product.id}', product.display_name)
            group['quoted_quantity'] += line.product_uom_qty
            group['quoted_amount'] += line.order_id.currency_id._convert(
                line.price_subtotal,
                currency,
                company,
                line.order_id.date_order or fields.Date.context_today(self),
            )

        for line in material_lines:
            product = line.product_id
            key = f'product-{product.id}' if product else 'unmatched-material'
            label = product.display_name if product else _('Unmatched Material')
            group = material_group(key, label)
            group['actual_quantity'] += line.unit_amount or 0.0
            group['actual_amount'] += -line.amount
            group['entries'] += 1

        for line in manual_material_lines:
            product = line.product_id
            key = f'product-{product.id}' if product else 'unmatched-material'
            label = product.display_name if product else _('Unmatched Material')
            group = material_group(key, label)
            group['actual_amount'] += line.amount
            group['entries'] += 1

        material_comparison = []
        for group in material_groups.values():
            group['quoted_quantity'] = round(group['quoted_quantity'], 4)
            group['actual_quantity'] = round(group['actual_quantity'], 4)
            group['quoted_amount'] = currency.round(group['quoted_amount'])
            group['actual_amount'] = currency.round(group['actual_amount'])
            group['balance_amount'] = currency.round(
                group['quoted_amount'] - group['actual_amount']
            )
            material_comparison.append(group)
        material_comparison.sort(key=lambda item: item['product'])
        quoted_material_amount = currency.round(sum(
            item['quoted_amount'] for item in material_comparison
        ))
        actual_material_amount = currency.round(sum(
            item['actual_amount'] for item in material_comparison
        ))

        total_cost = labor_cost + vendor_cost_posted + manual_material_cost
        margin = revenue_posted - total_cost
        margin_percent = revenue_posted and margin / revenue_posted * 100.0 or 0.0
        timesheet_details = [{
            'id': line.id,
            'date': fields.Date.to_string(line.date),
            'employee': line.employee_id.name or '',
            'service': line.hgr_manual_service_name or line.so_line.display_name or '',
            'work_category': (
                line.hgr_work_category_id.display_name
                or line.so_line.hgr_work_category_id.display_name
                or ''
            ),
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
            'quoted_material_amount': quoted_material_amount,
            'actual_material_amount': actual_material_amount,
            'material_balance': currency.round(
                quoted_material_amount - actual_material_amount
            ),
            'total_cost': currency.round(total_cost),
            'revenue_posted': currency.round(revenue_posted),
            'revenue_draft': currency.round(revenue_draft),
            'margin': currency.round(margin),
            'margin_percent': margin_percent,
            'vendor_bill_count': len({
                line.move_line_id.move_id.id
                for line in material_lines
                if line.move_line_id.move_id.move_type in ('in_invoice', 'in_refund', 'in_receipt')
            } | set(draft_vendor_lines.move_id.ids)),
            'timesheet_count': len(timesheets),
            'invoice_count': len(revenue_lines.move_id),
            'vendor_details': vendor_details,
            'manual_material_details': manual_material_details,
            'timesheet_details': timesheet_details,
            'labour_comparison': labour_comparison,
            'material_comparison': material_comparison,
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
            'manual_material_cost', 'quoted_material_amount',
            'actual_material_amount', 'material_balance',
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
