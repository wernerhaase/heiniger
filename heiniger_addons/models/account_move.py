from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
import re

class AccountMove(models.Model):
	_name = "account.move"
	_inherit = ["account.move", "analytic.mixin"]

	l10n_din5008_document_subject = fields.Char(compute='_compute_l10n_din5008_document_subject')
	l10n_din5008_addresses = fields.Binary(compute='_compute_l10n_din5008_addresses')
	
	invoice_discount_date_due = fields.Date(
		string='Due Date with discount',
		compute='_compute_invoice_discount_date_due',
		copy=False,
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
