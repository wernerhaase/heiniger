from datetime import datetime

from odoo import api, fields, models, _


class BusinessEntityType(models.Model):
	_name = "orchid.buss.type"
	_description = "Orchid Business Entity Type"

	name = fields.Char(string='Name')
	code = fields.Char(string='Code')

class LineofBusiness(models.Model):
	_name = "orchid.line.of.business"
	_description = "Line of Business"

	name = fields.Char(string="Name")
	code = fields.Char(string="Code")

class DistributionChannel(models.Model):
	_name = "orchid.distribution.channel"
	_description = "Distribution Channel"

	name = fields.Char(string="Name")
	code = fields.Char(string="Code")