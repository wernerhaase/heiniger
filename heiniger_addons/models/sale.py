# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.tools import html2plaintext

class Saleorder(models.Model):
	_inherit = "sale.order"

	@api.model_create_multi
	def create(self, vals_list):
		orders = super().create(vals_list)
		orders.sudo().project_id._hgr_sync_analytic_quotation_codes()
		orders._hgr_sync_line_analytic_distributions()
		return orders

	def write(self, vals):
		projects = self.sudo().project_id
		result = super().write(vals)
		if {'name', 'project_id', 'state'} & vals.keys():
			projects |= self.sudo().project_id
			projects._hgr_sync_analytic_quotation_codes()
		if 'project_id' in vals:
			self._hgr_sync_line_analytic_distributions()
		return result

	def _hgr_project_analytic_account(self):
		"""Return the single project account that applies to this order."""
		self.ensure_one()
		projects = self.sudo().project_id | self.sudo().project_ids
		accounts = projects.mapped('account_id')
		return accounts if len(accounts) == 1 else self.env['account.analytic.account']

	def _hgr_sync_line_analytic_distributions(self):
		"""Keep every commercial order line allocated to its linked project."""
		updated_lines = self.env['sale.order.line']
		for order in self:
			account = order._hgr_project_analytic_account()
			if account:
				updated_lines |= order.order_line._hgr_apply_project_analytic_account(account)
		return updated_lines

	hgr_has_advance_invoices = fields.Boolean(
		string="Has invoiced advances",
		compute="_compute_hgr_advance_summary",
		export_string_translation=False,
	)
	hgr_advance_invoiced_total = fields.Monetary(
		string="Invoiced advances (-)",
		compute="_compute_hgr_advance_summary",
		currency_field="currency_id",
	)
	hgr_remaining_after_advance = fields.Monetary(
		string="Remaining order amount",
		compute="_compute_hgr_advance_summary",
		currency_field="currency_id",
	)

	hgr_object_id = fields.Many2one(related="opportunity_id.hgr_object_id",string="Object",store=True)
	hgr_subject = fields.Char(string="Subject")
	hgr_case_of_insurance = fields.Boolean(string="Insurance case",related="opportunity_id.hgr_case_of_insurance",store=True)

	hgr_insurance_id = fields.Many2one('res.partner',string="Insurance Company", ondelete='restrict', domain="[('hgr_is_insurance','=',True)]",help="Insurance Company")
	hgr_claim_person_id = fields.Many2one('res.partner',string="Claims Expert", ondelete='restrict', domain="[('parent_id','=',hgr_insurance_id)]", help="Claims contact person")
	hgr_insurance_policy_no = fields.Char(string="Policy No",)
	hgr_insurance_claim_no = fields.Char(string="Claim No",)
	hgr_insurance_record_date = fields.Date(string="Date")
	hgr_insurance_description = fields.Html(string="Insurance Notes",related="opportunity_id.hgr_insurance_description",store=True,readonly=False)
	l10n_din5008_document_subject = fields.Char(compute='_compute_l10n_din5008_document_subject')
	hgr_has_timesheet_project = fields.Boolean(
		compute='_compute_hgr_has_timesheet_project', export_string_translation=False,
	)

	@api.depends(
		'amount_total',
		'currency_id',
		'order_line.invoice_lines.move_id.state',
		'order_line.invoice_lines.move_id.move_type',
		'order_line.invoice_lines.move_id.amount_total',
		'order_line.invoice_lines.move_id.currency_id',
		'order_line.invoice_lines.move_id.invoice_date',
		'order_line.invoice_lines.is_downpayment',
	)
	def _compute_hgr_advance_summary(self):
		for order in self:
			advance_total = 0.0
			advance_invoices = order.invoice_ids.filtered(
				lambda invoice: invoice.state == 'posted' and invoice._is_downpayment()
			)
			for invoice in advance_invoices:
				invoice_amount = invoice.currency_id._convert(
					invoice.amount_total,
					order.currency_id,
					order.company_id,
					invoice.invoice_date or fields.Date.context_today(order),
				)
				advance_total += invoice_amount if invoice.move_type == 'out_invoice' else -invoice_amount

			advance_total = max(order.currency_id.round(advance_total), 0.0)
			order.hgr_has_advance_invoices = bool(advance_invoices) and not order.currency_id.is_zero(advance_total)
			order.hgr_advance_invoiced_total = advance_total
			order.hgr_remaining_after_advance = order.currency_id.round(order.amount_total - advance_total)

	@api.depends('project_id', 'project_ids')
	def _compute_hgr_has_timesheet_project(self):
		for order in self:
			order.hgr_has_timesheet_project = bool(
				order.project_id or order.sudo().project_ids
			)

	def action_open_hgr_supervisor_timesheet(self):
		self.ensure_one()
		project = self.project_id or self.sudo().project_ids[:1]
		action = self.env['ir.actions.actions']._for_xml_id(
			'heiniger_addons.action_hgr_supervisor_timesheet'
		)
		action['context'] = {
			'default_partner_id': self.partner_id.commercial_partner_id.id,
			'default_project_id': project.id or False,
			'default_company_id': (project.company_id or self.company_id).id,
		}
		return action

	def action_open_hgr_profitability(self):
		self.ensure_one()
		project = self.project_id or self.sudo().project_ids[:1]
		action = self.env['ir.actions.actions']._for_xml_id(
			'heiniger_addons.action_hgr_project_profitability'
		)
		action['context'] = {
			'default_project_id': project.id or False,
			'default_sale_order_id': self.id,
		}
		return action

	# @api.model
	# def create(self, vals):
	# 	for order in self:
	# 		if not order.oppurtunity_id.order_ids:
	# 			self.env['crm.lead.insurance'].create({
	#             'order_id': order.id,
	#             # 'hgr_insurance_id': order.hgr_insurance_id.id,
	#             # 'hgr_claim_person_id': order.hgr_claim_person_id.id,
	#             # 'hgr_insurance_policy_no': order.hgr_insurance_policy_no,
	#             # 'hgr_insurance_record_date': order.hgr_insurance_record_date,
	#             'lead_id': self.id,
	#         })
	# 	return super().create(vals)


	@api.depends('state')
	@api.depends_context('lang')
	def _compute_type_name(self):
		for record in self:
			if record.state in ('draft', 'sent', 'cancel'):
				record.type_name = _("Quotation")
			else:
				record.type_name = _("Order Confirmation")
	

	def _compute_l10n_din5008_document_subject(self):
		for record in self:
			# Use the order's own subject first; fall back to the linked opportunity's subject
			record.l10n_din5008_document_subject = (
				record.hgr_subject
				or (record.opportunity_id.hgr_subject if record.opportunity_id else '')
			)

	def _has_to_be_signed(self, *args, **kwargs):
		"""Keep customized portal templates compatible with Odoo 19."""
		return super()._has_to_be_signed()

	def _has_to_be_paid(self, *args, **kwargs):
		"""Keep customized portal templates compatible with Odoo 19."""
		return super()._has_to_be_paid()

class SaleOrderLine(models.Model):
	_inherit = "sale.order.line"

	@api.model_create_multi
	def create(self, vals_list):
		lines = super().create(vals_list)
		if not self.env.context.get('hgr_skip_analytic_sync'):
			lines._hgr_sync_project_analytic_distribution()
		return lines

	def write(self, vals):
		result = super().write(vals)
		if (
			not self.env.context.get('hgr_skip_analytic_sync')
			and {'order_id', 'analytic_distribution', 'display_type'} & vals.keys()
		):
			self._hgr_sync_project_analytic_distribution()
		return result

	def _hgr_sync_project_analytic_distribution(self):
		updated_lines = self.env['sale.order.line']
		for line in self.filtered(lambda item: not item.display_type):
			account = line.order_id._hgr_project_analytic_account()
			if account:
				updated_lines |= line._hgr_apply_project_analytic_account(account)
		return updated_lines

	def _hgr_apply_project_analytic_account(self, account):
		"""Replace only the project-plan component of the distribution."""
		updated_lines = self.env['sale.order.line']
		for line in self.filtered(lambda item: not item.display_type):
			distribution = dict(line.analytic_distribution or {})
			if any(
				str(account.id) in str(key).split(',')
				for key in distribution
			):
				continue

			if not distribution:
				new_distribution = {str(account.id): 100.0}
			else:
				new_distribution = {}
				for key, percentage in distribution.items():
					key_accounts = self.env['account.analytic.account'].browse([
						int(account_id)
						for account_id in str(key).split(',')
						if account_id
					]).exists()
					other_plan_ids = key_accounts.filtered(
						lambda key_account: key_account.plan_id != account.plan_id
					).ids
					new_key = ','.join(map(str, [*other_plan_ids, account.id]))
					new_distribution[new_key] = (
						new_distribution.get(new_key, 0.0) + percentage
					)

			line.with_context(hgr_skip_analytic_sync=True).analytic_distribution = new_distribution
			updated_lines |= line
		return updated_lines

	hgr_work_category_id = fields.Many2one(
		'hgr.work.category', string='Work Category', ondelete='restrict', index=True,
		help='Groups quoted and actual labour in the project profitability report.',
	)

	@api.model
	def _hgr_first_plain_line(self, value):
		# html2plaintext joins <li> items on one line; break on block ends first
		html = re.sub(r'(?i)</(li|p|div|h\d)>|<br\s*/?>', '\n', value or '')
		for part in html2plaintext(html).splitlines():
			part = part.replace('\xa0', ' ').strip(' -*•\t')
			if part:
				return part
		return ''

	def _hgr_section_text(self):
		"""Return the title of the section this line sits in, as plain text."""
		self.ensure_one()
		section = False
		for line in self.order_id.order_line.sorted(lambda l: (l.sequence, l.id)):
			if line == self:
				break
			if line.display_type == 'line_section':
				section = line
		return self._hgr_first_plain_line(section.name) if section else ''

	def _hgr_service_label(self, with_order=False, prefer_product=False):
		"""Short label telling apart lines that share a product, e.g.
		"Pos. 2 – Arbeitsaufwand Freilegearbeiten". Materials read better
		with the product name ("Pos. 1 – Abdeckmaterial")."""
		self.ensure_one()
		description = (
			(prefer_product and self.product_id.display_name)
			or self._hgr_first_plain_line(self.name)
			or self.product_id.display_name
			or self.display_name
		)
		section = self._hgr_section_text()
		# "Pos. 2 / Freilegearbeiten ..." -> "Pos. 2"
		position = section.split(' / ', 1)[0] if section else ''
		label = f"{position} – {description}" if position else description
		if with_order:
			label = f"{self.order_id.name} – {label}"
		return label

	def _timesheet_create_task_prepare_values(self, project):
		res = super(SaleOrderLine, self)._timesheet_create_task_prepare_values(project)
		sale_line_name_parts = self.name.split('\n')
		title =  self.product_id.name
		description = '<br/>'.join(sale_line_name_parts)
		res.update({'name': title,'description':description})
		return res
