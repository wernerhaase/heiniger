# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.tools import format_date

class Saleorder(models.Model):
	_inherit = "sale.order"

	hgr_object_id = fields.Many2one(related="opportunity_id.hgr_object_id",string="Object",store=True)
	hgr_subject = fields.Char(string="Subject", related="opportunity_id.hgr_subject",store=True)
	hgr_case_of_insurance = fields.Boolean(string="Insurance case",related="opportunity_id.hgr_case_of_insurance",store=True)

	hgr_insurance_id = fields.Many2one(string="Insurance Company", related="opportunity_id.hgr_insurance_id",store=True)
	hgr_claim_person_id = fields.Many2one(string="Claims Expert", related="opportunity_id.hgr_claim_person_id",store=True)
	hgr_insurance_policy_no = fields.Char(string="Policy No",related="opportunity_id.hgr_insurance_policy_no",store=True)
	hgr_insurance_claim_no = fields.Char(string="Claim No",related="opportunity_id.hgr_insurance_claim_no",store=True)
	hgr_insurance_record_date = fields.Date(string="Date",related="opportunity_id.hgr_insurance_record_date",store=True)
	hgr_insurance_description = fields.Html(string="Insurance Notes",related="opportunity_id.hgr_insurance_description",store=True)

	l10n_din5008_document_subject = fields.Char(compute='_compute_l10n_din5008_document_subject')
	

	def _compute_l10n_din5008_document_subject(self):
		for record in self:
			record.l10n_din5008_document_subject = record.hgr_subject

	def _compute_l10n_din5008_template_data(self):
		for record in self:
			record.l10n_din5008_template_data = data = []
			if record.state in ('draft', 'sent'):
				if record.name:
					data.append((_("Quotation No."), record.name))
				if record.date_order:
					data.append((_("Quotation Date"), format_date(self.env, record.date_order)))
				if record.validity_date:
					data.append((_("Expiration"), format_date(self.env, record.validity_date)))
			else:
				if record.name:
					data.append((_("Order No."), record.name))
				if record.date_order:
					data.append((_("Order Date"), format_date(self.env, record.date_order)))
			if record.client_order_ref:
				data.append((_('Customer Reference'), record.client_order_ref))
			if record.user_id:
				data.append((_("Salesperson"), record.user_id.name))
			if 'incoterm' in record._fields and record.incoterm:
				data.append((_("Incoterm"), record.incoterm.code))
			if record.hgr_insurance_id:
				data.append((_("Sachbearbeiter"), record.hgr_insurance_id.name))
			if record.hgr_insurance_claim_no:
				data.append((_("Schaden Nr"), record.hgr_insurance_claim_no))
			if record.hgr_insurance_record_date:
				data.append((_("Annahme Datum"), format_date(self.env, record.hgr_insurance_record_date)))       


	def _compute_l10n_din5008_addresses(self):
		for record in self:
			record.l10n_din5008_addresses = data = []
			data.append((_("Objekt:"), record.partner_shipping_id))
			data.append((_("Invoicing Address:"), record.partner_invoice_id))
			# data.append((_("Subject:"), record.hgr_subject))
			# if record.partner_shipping_id == record.partner_invoice_id:
			#     data.append((_("Invoicing and Shipping Address:"), record.partner_shipping_id))
			# else:
			#     data.append((_("Shipping Address:"), record.partner_shipping_id))
			#     data.append((_("Invoicing Address:"), record.partner_invoice_id))

	# @api.depends('order_line','order_line.od_gross_weight')
	# def total_gross_weight(self):
	# 	gross=0
	# 	for line in self.order_line:
	# 		gross=gross+line.od_gross_weight
	# 	self.od_gross_weight=gross


# class Saleorderline(models.Model):
# 	_inherit = "sale.order.line"

# 	od_free_qty=fields.Float(string="Free quantity", digits=dp.get_precision('Product Unit of Measure'))
# 	od_adjustment_qty=fields.Float(string="Adjustment quantity", digits=dp.get_precision('Product Unit of Measure'))
# 	od_gross_weight = fields.Float(string='Gross Weight',compute="compute_gross_weight")
# 	od_transaction_type = fields.Many2one('od.transaction.type', string="Transaction Type", default=lambda self: self.env['od.transaction.type'].search([('code','=','SALE')], limit=1).id)

# 	@api.depends('product_uom_qty','od_free_qty','od_adjustment_qty')
# 	def compute_gross_weight(self):
# 		for line in self:
# 			line.od_gross_weight=(line.product_uom_qty+line.od_free_qty+line.od_adjustment_qty)*line.product_id.od_ttl_weight
# 	