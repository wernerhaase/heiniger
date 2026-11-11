from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
import re

class AccountMove(models.Model):
	_name = "account.move"
	_inherit = ["account.move", "analytic.mixin"]

	l10n_din5008_document_subject = fields.Char(compute='_compute_l10n_din5008_document_subject')
	l10n_din5008_addresses = fields.Binary(compute='_compute_l10n_din5008_addresses')
	hgr_has_advance_summary = fields.Boolean(
		string="Show advance summary",
		compute="_compute_hgr_advance_summary",
		export_string_translation=False,
	)
	hgr_sale_order_total = fields.Monetary(
		string="Order total incl. tax",
		compute="_compute_hgr_advance_summary",
		currency_field="currency_id",
	)
	hgr_sale_order_untaxed = fields.Monetary(
		string="Order total excl. tax",
		compute="_compute_hgr_advance_summary",
		currency_field="currency_id",
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
	
	invoice_discount_date_due = fields.Date(
		string='Due Date with discount',
		compute='_compute_invoice_discount_date_due',
		copy=False,
	)

	@api.depends(
		'currency_id',
		'invoice_date',
		'line_ids.sale_line_ids.order_id.amount_untaxed',
		'line_ids.sale_line_ids.order_id.amount_total',
		'line_ids.sale_line_ids.order_id.hgr_has_advance_invoices',
		'line_ids.sale_line_ids.order_id.hgr_advance_invoiced_total',
		'line_ids.sale_line_ids.order_id.hgr_remaining_after_advance',
	)
	def _compute_hgr_advance_summary(self):
		for move in self:
			orders = move.line_ids.sale_line_ids.order_id
			show_summary = (
				move.move_type in ('out_invoice', 'out_refund')
				and len(orders) == 1
				and orders.hgr_has_advance_invoices
			)
			move.hgr_has_advance_summary = show_summary
			move.hgr_sale_order_untaxed = 0.0
			move.hgr_sale_order_total = 0.0
			move.hgr_advance_invoiced_total = 0.0
			move.hgr_remaining_after_advance = 0.0
			if not show_summary:
				continue

			order = orders
			conversion_date = move.invoice_date or fields.Date.context_today(move)
			move.hgr_sale_order_untaxed = order.currency_id._convert(
				order.amount_untaxed, move.currency_id, move.company_id, conversion_date
			)
			move.hgr_sale_order_total = order.currency_id._convert(
				order.amount_total, move.currency_id, move.company_id, conversion_date
			)
			move.hgr_advance_invoiced_total = order.currency_id._convert(
				order.hgr_advance_invoiced_total, move.currency_id, move.company_id, conversion_date
			)
			move.hgr_remaining_after_advance = order.currency_id._convert(
				order.hgr_remaining_after_advance, move.currency_id, move.company_id, conversion_date
			)

	def _hgr_apply_analytic_distribution_to_bill_lines(self):
		for move in self.filtered(
			lambda record: record.move_type in ('in_invoice', 'in_refund', 'in_receipt')
		):
			distribution = dict(move.analytic_distribution or {}) or False
			for line in move.invoice_line_ids.filtered(
				lambda record: record.display_type == 'product'
			):
				line.analytic_distribution = distribution

	@api.onchange('analytic_distribution')
	def _onchange_hgr_analytic_distribution(self):
		self._hgr_apply_analytic_distribution_to_bill_lines()

	@api.model_create_multi
	def create(self, vals_list):
		moves = super().create(vals_list)
		for move, vals in zip(moves, vals_list):
			if 'analytic_distribution' in vals:
				move._hgr_apply_analytic_distribution_to_bill_lines()
		return moves

	def write(self, vals):
		result = super().write(vals)
		if 'analytic_distribution' in vals:
			self._hgr_apply_analytic_distribution_to_bill_lines()
		return result

	def _post(self, soft=True):
		# OVERRIDE
		# correct the nbsp issue in name
		self._correct_nbsp_issue()

		posted = super()._post(soft)

		# remove the html tags in label
		posted._remove_html_tags()

		return posted
	
	def _correct_nbsp_issue(self):
		for move in self:
			if move.move_type == 'out_invoice':
				for line in move.line_ids.filtered('name'):
					line.name = line.name.replace('&nbsp;', '&#160;').replace('<br>', '<br/>')

	def _remove_html_tags(self):
		for move in self:
			if move.move_type not in ('out_invoice','in_invoice','out_refund','in_refund'):
				clean = re.compile('<.*?>')
				if move.ref:
					ref = re.sub(clean, '', move.ref)
					move.write({'ref': ref})
				# for line in move.line_ids:
				# 	name = re.sub(clean, '', line.name)
				# 	move.write({'name': name})
						

	@api.depends(
		'invoice_date', 'invoice_date_due',
		'invoice_payment_term_id.early_discount',
		'invoice_payment_term_id.discount_days',
		'invoice_payment_term_id.hgr_second_early_discount',
		'invoice_payment_term_id.hgr_second_discount_days',
		'line_ids.discount_date', 'line_ids.date_maturity',
	)
	@api.depends_context('hgr_payment_reference_date', 'tz')
	def _compute_invoice_discount_date_due(self):
		for invoice in self:
			reference_date = fields.Date.to_date(
				invoice.env.context.get('hgr_payment_reference_date')
			) or fields.Date.context_today(invoice)
			term = invoice.invoice_payment_term_id
			if term and term.early_discount and invoice.invoice_date:
				first_date = invoice.invoice_date + relativedelta(days=term.discount_days)
				if reference_date <= first_date:
					invoice.invoice_discount_date_due = first_date
					continue
				if term.hgr_second_early_discount:
					second_date = invoice.invoice_date + relativedelta(
						days=term.hgr_second_discount_days
					)
					invoice.invoice_discount_date_due = second_date
					continue
			invoice.invoice_discount_date_due = invoice.invoice_date_due

	def _compute_l10n_din5008_document_subject(self):
		for record in self:
			sale_order = record.line_ids.sale_line_ids.order_id[:1]
			record.l10n_din5008_document_subject = sale_order.hgr_subject or ''

	def _compute_l10n_din5008_addresses(self):
		for record in self:
			data = []
			# Only show invoice address block when it differs from the main partner
			if record.partner_id and record.partner_shipping_id and record.partner_shipping_id != record.partner_id:
				data.append((_("Shipping Address:"), record.partner_shipping_id))
			record.l10n_din5008_addresses = data


class AccountMoveLine(models.Model):
	_inherit = 'account.move.line'

	hgr_sale_line_id = fields.Many2one(
		'sale.order.line', string='Quoted Material', index='btree_not_null',
		ondelete='set null', copy=False,
		help='Quotation line this vendor cost belongs to. Used to match the cost '
			 'against the quoted material in the project profitability report.',
	)
	hgr_sale_line_distribution = fields.Json(
		string='Quoted Material by Analytic Distribution',
		copy=False,
		help='Quotation line selected for each analytic distribution row. This '
			 'keeps split vendor costs matched independently line by line.',
	)

	def _hgr_distribution_keys_for_account(self, analytic_account):
		self.ensure_one()
		account_id = str(analytic_account.id)
		return [
			key for key in (self.analytic_distribution or {})
			if account_id in str(key).split(',')
		]

	@staticmethod
	def _hgr_key_ids(distribution_key):
		return frozenset(part for part in str(distribution_key or '').split(',') if part)

	def _hgr_sale_line_rows(self):
		"""Return the per-row quoted material list, or False for legacy data.

		New format: ``{"rows": [{"key": "12", "percentage": 36.75,
		"sale_line_id": 5}, ...]}`` -- one entry per row of the analytic
		distribution popup. Legacy format: ``{"<key>": <sale_line_id>}``.
		"""
		self.ensure_one()
		value = self.hgr_sale_line_distribution
		if isinstance(value, dict) and isinstance(value.get('rows'), list):
			return [row for row in value['rows'] if isinstance(row, dict)]
		return False

	def _hgr_sale_line_splits(self, distribution_key):
		"""Return ``[(sale_line, fraction, row_index)]`` for one distribution key.

		Several popup rows may use the same analytic account (for example
		36.75 % and 63.25 % of one bill line on the same project) with a
		different quoted material each. Odoo merges such rows into a single
		``analytic_distribution`` key, so the row split is kept in
		``hgr_sale_line_distribution['rows']`` and re-applied here as fractions
		of that key. ``row_index`` is None for legacy, key-based data.
		"""
		SaleLine = self.env['sale.order.line']
		if not self:
			return [(SaleLine, 1.0, None)]
		self.ensure_one()
		rows = self._hgr_sale_line_rows()
		if rows is False:
			return [(self._hgr_sale_line_for_distribution_key(distribution_key), 1.0, None)]
		account_ids = self._hgr_key_ids(distribution_key)
		matching = []
		for index, row in enumerate(rows):
			try:
				percentage = max(float(row.get('percentage') or 0.0), 0.0)
			except (TypeError, ValueError):
				percentage = 0.0
			if percentage and self._hgr_key_ids(row.get('key')) == account_ids:
				matching.append((index, row, percentage))
		total = sum(percentage for _index, _row, percentage in matching)
		if not total:
			return [(SaleLine, 1.0, None)]
		splits = []
		for index, row, percentage in matching:
			sale_line = SaleLine
			if row.get('sale_line_id'):
				sale_line = SaleLine.browse(int(row['sale_line_id'])).exists()
			splits.append((sale_line, percentage / total, index))
		return splits

	def _hgr_sale_line_for_distribution_key(self, distribution_key):
		"""Return the quoted material assigned to one distribution row.

		``hgr_sale_line_id`` was the original, line-wide value. Keep it as a
		fallback for existing vendor bills while new edits use the per-row JSON
		data. When one key is split over several quoted materials, only the
		first one is returned; use ``_hgr_sale_line_splits`` for the full split.
		"""
		if not self:
			return self.env['sale.order.line']
		self.ensure_one()
		if self._hgr_sale_line_rows() is not False:
			splits = self._hgr_sale_line_splits(distribution_key)
			return next((line for line, _fraction, _index in splits if line), self.env['sale.order.line'])
		mapping = self.hgr_sale_line_distribution or {}
		distribution_key = str(distribution_key or '')
		sale_line_id = mapping.get(distribution_key)
		if not sale_line_id and distribution_key:
			account_ids = self._hgr_key_ids(distribution_key)
			matching_key = next((
				key for key in mapping
				if self._hgr_key_ids(key) == account_ids
			), False)
			if matching_key:
				sale_line_id = mapping[matching_key]
		if sale_line_id:
			return self.env['sale.order.line'].browse(int(sale_line_id)).exists()
		return self.hgr_sale_line_id if not mapping else self.env['sale.order.line']

	def _hgr_assign_sale_line(self, sale_line, distribution_key=False, row_index=None):
		"""Assign a quoted material to one row (or key) of this bill line."""
		self.ensure_one()
		rows = self._hgr_sale_line_rows()
		if rows is not False:
			if row_index is not None and 0 <= row_index < len(rows):
				targets = [row_index]
			else:
				account_ids = self._hgr_key_ids(distribution_key)
				targets = [
					index for index, row in enumerate(rows)
					if not distribution_key or self._hgr_key_ids(row.get('key')) == account_ids
				]
			rows = [dict(row) for row in rows]
			for index in targets:
				rows[index]['sale_line_id'] = sale_line.id or False
			self.hgr_sale_line_distribution = {'rows': rows}
		elif distribution_key:
			mapping = dict(self.hgr_sale_line_distribution or {})
			mapping[str(distribution_key)] = sale_line.id
			self.hgr_sale_line_distribution = mapping
		else:
			self.hgr_sale_line_id = sale_line

	@api.model
	def hgr_quoted_material_options(self, account_ids):
		"""Quoted material lines of the projects behind the given analytic
		accounts, offered in the analytic distribution popup of vendor bills."""
		hour_uom = self.env.ref('uom.product_uom_hour')
		options = []
		projects = self.env['project.project'].search([('account_id', 'in', account_ids or [])])
		for project in projects:
			lines = project.sudo()._hgr_profitability_sale_orders().order_line.filtered(
				lambda item: not item.display_type
				and item.product_id
				and not project._hgr_is_time_uom(item.product_uom_id, hour_uom)
			)
			with_order = len(lines.order_id) > 1
			options += [{
				'id': line.id,
				'name': line._hgr_service_label(with_order=with_order, prefer_product=True),
				'account_id': project.account_id.id,
			} for line in lines]
		return options

	@api.depends(
		'account_id', 'partner_id', 'product_id',
		'move_id.analytic_distribution',
	)
	def _compute_analytic_distribution(self):
		super()._compute_analytic_distribution()
		for line in self.filtered(
			lambda record: record.display_type == 'product'
			and record.move_id.move_type in ('in_invoice', 'in_refund', 'in_receipt')
			and record.move_id.analytic_distribution
		):
			line.analytic_distribution = dict(line.move_id.analytic_distribution)


	# class AccountInvoiceLine(models.Model):
	# _inherit = "account.move.line"

	# def _remove_html_tags(self):
	# 		for move in self:
	# 			if move.move_type not in ('out_invoice','in_invoice','out_refund','in_refund'):
	# 			for line in move.line_ids:
	# 				clean = re.compile('<.*?>')
	# 				name = re.sub(clean, '', line.name)
	# 				line.write({'name': name})


	# od_gross_weight = fields.Float(string='Gross Weight',compute="compute_gross_weight")
	# orchid_country_id = fields.Many2one('res.country', string='Country Of Origin')
	# od_free_qty=fields.Float(string="Free quantity", digits=dp.get_precision('Product Unit of Measure'))
	# od_adjustment_qty=fields.Float(string="Adjustment quantity", digits=dp.get_precision('Product Unit of Measure'))
	# od_ttl_qty = fields.Float(string="Total quantity",digits=dp.get_precision('Product Unit of Measure'))
	# od_transaction_type = fields.Many2one('od.transaction.type', string="Transaction Type", default=lambda self: self.env['od.transaction.type'].search([('code','=','SALE')], limit=1).id)

	# @api.depends('quantity','od_free_qty','od_adjustment_qty')
	# def compute_gross_weight(self):
	# 	for line in self:
	# 		line.od_gross_weight=(line.quantity+line.od_free_qty+line.od_adjustment_qty)*line.product_id.od_ttl_weight
	# 		line.od_ttl_qty = line.quantity + line.od_free_qty + line.od_adjustment_qty

	# @api.onchange('product_id')
	# def od_onchange_country(self):
	# 	for line in self:
	# 		if line.product_id:
	# 			line.orchid_country_id = line.product_id.orchid_country_id and line.product_id.orchid_country_id.id
