# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.tools import format_date

class Saleorder(models.Model):
	_inherit = "sale.order"

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
	def _compute_type_name(self):
		for record in self:
			if record.state in ('draft', 'sent', 'cancel'):
				record.type_name = _("Offerte") ## Quotation
			else:
				record.type_name = _("Auftragsbestätigung") ## Sales Order
	

	def _compute_l10n_din5008_document_subject(self):
		for record in self:
			# Use the order's own subject first; fall back to the linked opportunity's subject
			record.l10n_din5008_document_subject = (
				record.hgr_subject
				or (record.opportunity_id.hgr_subject if record.opportunity_id else '')
			)

	def _compute_l10n_din5008_template_data(self):
		for record in self:
			data = []
			# ── Document reference numbers ────────────────────────────
			if record.state in ('draft', 'sent'):
				if record.name:
					data.append((_("Angebotsnummer"), record.name))
				if record.date_order:
					data.append((_("Angebotsdatum"), format_date(self.env, record.date_order)))
				if record.validity_date:
					data.append((_("Gültig bis"), format_date(self.env, record.validity_date)))
			else:
				if record.name:
					data.append((_("Auftragsnummer"), record.name))
				if record.date_order:
					data.append((_("Auftragsdatum"), format_date(self.env, record.date_order)))
			# ── Order metadata ────────────────────────────────────────
			if record.client_order_ref:
				data.append((_("Ihre Referenz"), record.client_order_ref))
			if record.user_id:
				data.append((_("Sachbearbeiter"), record.user_id.name))
			# ── Object (property / site) ──────────────────────────────
			if record.hgr_object_id:
				data.append((_("Objekt"), record.hgr_object_id._get_name()))
			# ── Insurance details (only when insurance case) ──────────
			if record.hgr_insurance_id:
				data.append((_("Versicherung"), record.hgr_insurance_id.name))
			if record.hgr_claim_person_id:
				data.append((_("Schadenexperte"), record.hgr_claim_person_id.name))
			if record.hgr_insurance_policy_no:
				data.append((_("Police Nr."), record.hgr_insurance_policy_no))
			if record.hgr_insurance_claim_no:
				data.append((_("Schaden Nr."), record.hgr_insurance_claim_no))
			if record.hgr_insurance_record_date:
				data.append((_("Schadenaufnahme"), format_date(self.env, record.hgr_insurance_record_date)))
			record.l10n_din5008_template_data = data

	def _compute_l10n_din5008_addresses(self):
		for record in self:
			data = []
			# Only show invoice address block when it differs from the main partner
			if record.partner_invoice_id and record.partner_invoice_id != record.partner_id:
				data.append((_("Rechnungsadresse:"), record.partner_invoice_id))
			record.l10n_din5008_addresses = data

	def _compute_l10n_din5008_document_title(self):
		for record in self:
			if self._context.get('proforma'):
				record.l10n_din5008_document_title = _('Proformarechnung') ##Pro Forma Invoice
			elif record.state in ('draft', 'sent'):
				record.l10n_din5008_document_title = _('Offerte') ## Quotation
			else:
				record.l10n_din5008_document_title = _('Auftragsbestätigung') ## Sales Order

class SaleOrderLine(models.Model):
	_inherit = "sale.order.line"

	def _timesheet_create_task_prepare_values(self, project):
		res = super(SaleOrderLine, self)._timesheet_create_task_prepare_values(project)
		sale_line_name_parts = self.name.split('\n')
		title =  self.product_id.name
		description = '<br/>'.join(sale_line_name_parts)
		res.update({'name': title,'description':description})
		return res