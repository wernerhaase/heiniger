# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, SUPERUSER_ID

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

	project_use_documents = fields.Boolean("Use Documents", related='project_id.use_documents')
	documents_folder_id = fields.Many2one('documents.folder', related='project_id.documents_folder_id')
	document_count = fields.Integer(compute='_compute_attached_document_count', string="Number of documents", groups='documents.group_documents_user')
	hgr_insurance_description = fields.Html('Insurance Notes')

	@api.onchange('name')
	def onchange_name(self):
		self.hgr_subject = self.name


	@api.onchange('partner_id')
	def onchange_partner(self):
		self.hgr_object_id = self.partner_id.id

	@api.model
	def create(self, vals):
		if 'hgr_subject' not in vals:
			vals['hgr_subject'] = vals['name']
		return super().create(vals)
	
	# @api.model_create_multi
	# def create(self, vals_list):
	# 	res = super().create(vals_list)
	# 	if not self.project_id:
	# 		# projects.filtered(lambda project: project.use_documents)._create_missing_folders()
	# 		print ("??????????????????????????????????")
	# 		project = self.create_project()
	# 		self.write({'project_id': project.id})
	# 	return res

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
		Task = self.env['project.task']
		task_read_group = Task._read_group(
			[('project_id', 'in', self.ids)],
			['project_id', 'ids:array_agg(id)'],
			['project_id'],
		)
		task_ids = []
		task_ids_per_project_id = {}
		for res in task_read_group:
			task_ids += res['ids']
			task_ids_per_project_id[res['project_id'][0]] = res['ids']
		Document = self.env['documents.document']
		project_document_read_group = Document._read_group(
			[('res_model', '=', 'project.project'), ('res_id', 'in', self.ids)],
			['res_id'],
			['res_id'],
		)
		document_count_per_project_id = {res['res_id']: res['res_id_count'] for res in project_document_read_group}
		document_count_per_task_id = Task.browse(task_ids)._get_task_document_data()
		for project in self:
			task_ids = task_ids_per_project_id.get(self.id, [])
			project.document_count = document_count_per_project_id.get(self.id, 0) \
				+ sum([
					document_count
					for task_id, document_count in document_count_per_task_id.items()
					if task_id in task_ids
				])	

	
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
			'default_tag_ids': [(6, 0, self.tag_ids.ids)]
		}
		if self.team_id:
			quotation_context['default_team_id'] = self.team_id.id
		if self.user_id:
			quotation_context['default_user_id'] = self.user_id.id
		
		quotation_context['default_project_id'] = self.project_id.id
		quotation_context['default_analytic_account_id'] = self.project_id.analytic_account_id.id
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
		