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
	hgr_has_timesheet_project = fields.Boolean(
		compute='_compute_hgr_has_timesheet_project', export_string_translation=False,
	)

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

	hgr_work_category_id = fields.Many2one(
		'hgr.work.category', string='Work Category', ondelete='restrict', index=True,
		help='Groups quoted and actual labour in the project profitability report.',
	)

	def _timesheet_create_task_prepare_values(self, project):
		res = super(SaleOrderLine, self)._timesheet_create_task_prepare_values(project)
		sale_line_name_parts = self.name.split('\n')
		title =  self.product_id.name
		description = '<br/>'.join(sale_line_name_parts)
		res.update({'name': title,'description':description})
		return res
