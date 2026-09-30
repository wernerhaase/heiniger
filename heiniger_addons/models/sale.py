# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, SUPERUSER_ID, _

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

	def _timesheet_create_task_prepare_values(self, project):
		res = super(SaleOrderLine, self)._timesheet_create_task_prepare_values(project)
		sale_line_name_parts = self.name.split('\n')
		title =  self.product_id.name
		description = '<br/>'.join(sale_line_name_parts)
		res.update({'name': title,'description':description})
		return res
