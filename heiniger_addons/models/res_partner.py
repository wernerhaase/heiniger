# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, SUPERUSER_ID

class ResPartner(models.Model):
	_inherit = 'res.partner'


	hgr_is_insurance = fields.Boolean(string="Insurance Company", help="help to classify insurance comapny seperately")
