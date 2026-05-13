# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, SUPERUSER_ID
from odoo.osv import expression

class Lead(models.Model):
	_inherit = 'crm.lead'


	hgr_object_id = fields.Many2one('res.partner', string="Object", ondelete='restrict', help="Partner object")
	hgr_subject = fields.Char(string="Subject", help="Subject of the lead")
	hgr_case_of_insurance = fields.Boolean(string="Insurance case")

	hgr_insurance_id = fields.Many2one('res.partner',string="Insurance Company", ondelete='restrict', domain="[('hgr_is_insurance','=',True)]",help="Insurance Company")
	hgr_claim_person_id = fields.Many2one('res.partner',string="Claims Expert", ondelete='restrict', domain="[('parent_id','=',hgr_insurance_id)]", help="Claims contact person")
	hgr_insurance_policy_no = fields.Char(string="Policy No")
	hgr_insurance_claim_no = fields.Char(string="Claim No")
	hgr_insurance_record_date = fields.Date(string="Date")

	project_id = fields.Many2one('project.project', 'Project', readonly=True,help='Select a billable project on which tasks can be created.')

	# project_use_documents = fields.Boolean("Use Documents", related='project_id.use_documents')
	# documents_folder_id = fields.Many2one('documents.folder', related='project_id.documents_folder_id')
	document_count = fields.Integer(compute='_compute_attached_document_count', string="Number of documents", groups='documents.group_documents_user')
	hgr_insurance_description = fields.Html('Insurance Notes')

	insurance_line = fields.One2many('crm.lead.insurance','lead_id',string='Insurances For Quotation', copy=True)
	multi_insurance = fields.Boolean(string="Multiple Insurance")

	@api.onchange('name')
	def onchange_name(self):
		self.hgr_subject = self.name

	@api.onchange('partner_id')
	def onchange_partner(self):
		self.hgr_object_id = self.partner_id.id

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			if 'hgr_subject' not in vals:
				vals['hgr_subject'] = vals.get('name', '')
		return super().create(vals_list)

	def _get_employee_document_domain(self):
		self.ensure_one()
		user_domain = [('res_model', '=', 'project.task')]
		if self.user_id:
			user_domain = expression.OR([user_domain,
										[('owner_id', '=', self.user_id.id)]])
		return user_domain	

	def action_open_documents(self):
		self.ensure_one()
		# if not self.address_home_id:
			# Prevent opening documents if the employee's address is not set or no user is linked.
			# raise ValidationError(_('You must set an address on the employee to use Documents features.'))
		# hr_folder = self._get_document_folder()
		project_id = self.project_id
		if not self.project_id:
			folder = self.create_missing_folder()
			project_id = self.create_project(folder)
			self.write({'project_id': project_id.id})

		prj_folder = project_id.documents_folder_id and project_id.documents_folder_id.id
		action = self.env['ir.actions.act_window']._for_xml_id('documents.document_action')
		# Documents created within that action will be 'assigned' to the employee
		# Also makes sure that the views starts on the hr_holder
		action['context'] = {
			'default_partner_id': self.user_id.id,
			'searchpanel_default_folder_id': prj_folder,
		}
		# action['domain'] = self._get_employee_document_domain()
		return action
	
	def _compute_attached_document_count(self):
		folder_ids = []
		for record in self:
			if record.project_id and record.project_id.documents_folder_id:
				folder_ids.append(record.project_id.documents_folder_id.id)

		if folder_ids:
			groups = self.env['documents.document']._read_group(
				[('folder_id', 'in', folder_ids)],
				groupby=['folder_id'],
				aggregates=['__count'],
			)
			document_count_dict = {folder.id: count for folder, count in groups}
		else:
			document_count_dict = {}

		for record in self:
			if record.project_id and record.project_id.documents_folder_id:
				folder_id = record.project_id.documents_folder_id.id
				record.document_count = document_count_dict.get(folder_id, 0)
			else:
				record.document_count = 0

	
	def create_project(self,folder):
		account = self.create_analytic_account()
		values = {
			'name': '%s - %s' % (self.hgr_object_id.name, self.name) if self.hgr_object_id else self.name,
			'analytic_account_id': account.id,
			'partner_id': self.partner_id.id,
			'documents_folder_id': folder.id,
			# 'sale_line_id': self.id,
			'active': True,
			'company_id': self.company_id.id,
			'allow_billable': True,
		}
		return self.env['project.project'].with_context(no_create_folder=True).create(values)	

	def create_analytic_account(self):
		company_id = self.env.company
		analytic_account = self.env['account.analytic.account'].create({
			'name': '%s - %s' % (self.hgr_object_id.name, self.name) if self.hgr_object_id else self.name,
			'company_id': self.company_id.id,
			'partner_id': self.partner_id.id,
			'plan_id': self.company_id.analytic_plan_id.id,
			'active': True,
		})
		return analytic_account

	def create_missing_folder(self):
		documents_project_folder_id = self.env.ref('documents_project.documents_project_folder').id
		folder = self.env['documents.folder'].create({
			'name': '%s - %s' % (self.hgr_object_id.name, self.name) if self.hgr_object_id else self.name,
			'parent_folder_id': documents_project_folder_id,
			'company_id': self.company_id.id,
		})
		return folder
	
	def _prepare_opportunity_quotation_context(self):
		""" Prepares the context for a new quotation (sale.order) by sharing the values of common fields """
		self.ensure_one()
		quotation_context = {
			'default_opportunity_id': self.id,
			'default_partner_id': self.partner_id.id,
			'default_campaign_id': self.campaign_id.id,
			'default_medium_id': self.medium_id.id,
			'default_origin': self.name,
			'default_source_id': self.source_id.id,
			'default_company_id': self.company_id.id or self.env.company.id,
			'default_tag_ids': [(6, 0, self.tag_ids.ids)],
			'default_hgr_insurance_id': self.hgr_insurance_id.id,
			'default_hgr_claim_person_id': self.hgr_claim_person_id.id,
			'default_hgr_insurance_policy_no': self.hgr_insurance_policy_no,
			'default_hgr_insurance_claim_no': self.hgr_insurance_claim_no,
			'default_hgr_insurance_record_date': self.hgr_insurance_record_date,
			'default_hgr_subject': self.hgr_subject,
		}
		if self.team_id:
			quotation_context['default_team_id'] = self.team_id.id
		if self.user_id:
			quotation_context['default_user_id'] = self.user_id.id
		
		if self.project_id:
			quotation_context['default_project_id'] = self.project_id.id
			quotation_context['default_analytic_account_id'] = self.project_id.analytic_account_id.id
		else:
			folder = self.create_missing_folder()
			project_id = self.create_project(folder)
			self.write({'project_id': project_id.id})
			quotation_context['default_project_id'] = project_id.id
			quotation_context['default_analytic_account_id'] = project_id.analytic_account_id.id
		return quotation_context

	def action_view_insurance_details(self):
		self.ensure_one()
		self.insurance_line.unlink()
		for order in self.order_ids:
			self.env['crm.lead.insurance'].create({
			'order_id': order.id,
			'hgr_insurance_id': order.hgr_insurance_id.id,
			'hgr_claim_person_id': order.hgr_claim_person_id.id,
			'hgr_insurance_policy_no': order.hgr_insurance_policy_no,
			'hgr_insurance_record_date': order.hgr_insurance_record_date,
			'hgr_insurance_claim_no': order.hgr_insurance_claim_no,
			'hgr_subject': order.hgr_subject,
			'lead_id': self.id,
		})
		

	# def _get_lead_order_domain(self):
	# 	return [('state', 'not in', ('cancel'))]

class CrmLeadInsurance(models.Model):
	_name = 'crm.lead.insurance'
	_description = 'CRM Insurance Companies'
	
	hgr_insurance_id = fields.Many2one('res.partner',string="Insurance Company", ondelete='restrict', domain="[('hgr_is_insurance','=',True)]",help="Insurance Company",)
	hgr_claim_person_id = fields.Many2one('res.partner',string="Claims Expert", ondelete='restrict', domain="[('parent_id','=',hgr_insurance_id)]", help="Claims contact person",)
	hgr_insurance_policy_no = fields.Char(string="Policy No",)
	hgr_insurance_claim_no = fields.Char(string="Claim No")
	hgr_insurance_record_date = fields.Date(string="Date")
	hgr_subject = fields.Char(string="Subject")
	lead_id = fields.Many2one('crm.lead',string="Lead")
	order_id = fields.Many2one('sale.order',string="Order",readonly=True)
	
	def update_sale_order_insurance(self):
		for rec in self:
			rec.order_id.hgr_insurance_id = rec.hgr_insurance_id
			rec.order_id.hgr_claim_person_id = rec.hgr_claim_person_id
			rec.order_id.hgr_insurance_policy_no = rec.hgr_insurance_policy_no
			rec.order_id.hgr_insurance_claim_no = rec.hgr_insurance_claim_no
			rec.order_id.hgr_insurance_record_date = rec.hgr_insurance_record_date
			rec.order_id.hgr_subject = rec.hgr_subject
			rec.lead_id.action_view_insurance_details()