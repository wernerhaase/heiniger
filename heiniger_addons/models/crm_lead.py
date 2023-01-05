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

	@api.onchange('name')
	def onchange_name(self):
		self.hgr_subject = self.name


	@api.onchange('partner_id')
	def onchange_partner(self):
		self.hgr_object_id = self.partner_id.id

		