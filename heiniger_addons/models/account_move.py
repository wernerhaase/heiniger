from odoo import api, fields, models, _
from odoo.tools import format_date
import re

class AccountMove(models.Model):
	_inherit = "account.move"

	l10n_din5008_document_subject = fields.Char(compute='_compute_l10n_din5008_document_subject')
	l10n_din5008_addresses = fields.Binary(compute='_compute_l10n_din5008_addresses')
	
	invoice_discount_date_due = fields.Date(
		string='Due Date with discount',
		compute='_compute_invoice_discount_date_due', store=True, readonly=False,
		states={'draft': [('readonly', False)]},
		index=True,
		copy=False,
	)

	def _post(self, soft=True):
		# OVERRIDE
		posted = super()._post(soft)

		# correct the nbsp issue in name
		posted._correct_nbsp_issue()

		# remove the html tags in label
		posted._remove_html_tags()

		return posted
	
	def _correct_nbsp_issue(self):
		for move in self:
			if move.move_type =='out_invoice':
				move.env.cr.execute("UPDATE account_move_line SET name = REPLACE (name,'&nbsp;','&#160;')")

	def _remove_html_tags(self):
		for move in self:
			if move.move_type not in ('out_invoice','in_invoice','out_refund','in_refund'):
				clean = re.compile('<.*?>')
				ref = re.sub(clean, '', move.ref)
				move.write({'ref': ref})
				# for line in move.line_ids:
				# 	name = re.sub(clean, '', line.name)
				# 	move.write({'name': name})
						

	@api.depends('needed_terms')
	def _compute_invoice_discount_date_due(self):
		for invoice in self:
			for line in invoice.line_ids.filtered(lambda l: l.display_type == 'payment_term').sorted('date_maturity'):
				invoice.invoice_discount_date_due =  line.discount_date or invoice.invoice_date_due

	def _compute_l10n_din5008_document_subject(self):
		for record in self:
			record.l10n_din5008_document_subject = record.line_ids.sale_line_ids.order_id.hgr_subject	
	
	def _compute_l10n_din5008_addresses(self):
		for record in self:
			record.l10n_din5008_addresses = data = []
			sale_order = record.line_ids.sale_line_ids.order_id
			data.append((_("Objekt:"), sale_order.hgr_object_id))
			data.append((_("Rechnungsadresse:"), record.partner_id)) ##Invoicing Address:

	def _compute_l10n_din5008_template_data(self):
		for record in self:
			record.l10n_din5008_template_data = data = []
			sale_order = record.line_ids.sale_line_ids.order_id
			if record.name:
				data.append((_("Rechnungsnummer"), record.name)) ##Invoice No.
			if record.invoice_date:
				data.append((_("Rechnungsdatum"), format_date(self.env, record.invoice_date)))## Invoice Date
			if record.invoice_date_due:
				data.append((_("Fälligkeitsdatum"), format_date(self.env, record.invoice_date_due))) ##Due Date
			if record.invoice_origin:
				data.append((_("Quelle"), record.invoice_origin)) ##Source
			if record.ref:
				data.append((_("Referenz"), record.ref)) ## Reference
			if sale_order.hgr_insurance_id:
				data.append((_("Versicherung"), sale_order.hgr_insurance_id.name))
			if sale_order.hgr_insurance_claim_no:
				data.append((_("Schaden Nr"), sale_order.hgr_insurance_claim_no))
			if sale_order.hgr_insurance_record_date:
				data.append((_("Annahme Datum"), format_date(self.env, sale_order.hgr_insurance_record_date)))       
	

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
