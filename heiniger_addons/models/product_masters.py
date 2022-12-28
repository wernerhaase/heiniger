from odoo import api, fields, models

class OrchidProductBrand(models.Model):
	_name = 'orchid.product.brand'
	_description = "Product Brand"

	code = fields.Char(string='Code',required=True)
	name = fields.Char(string='Name',required=True)

class OrchidProductType(models.Model):
	_name = 'orchid.product.type'
	_description = "Product Type"

	code = fields.Char(string='Code',required=True)
	name = fields.Char(string='Name',required=True)
	

class OrchidProductSubType(models.Model):
	_name = 'orchid.product.sub.type'
	_description = "Product Sub Type"

	code = fields.Char(string='Code',required=True)
	name = fields.Char(string='Name',required=True)
	type_id =  fields.Many2one('orchid.product.type', string='Type')

class OrchidProductGroup(models.Model):
	_name = 'orchid.product.group'
	_description = "Product Group"

	code = fields.Char(string='Code',required=True)
	name = fields.Char(string='Name',required=True)

class OrchidProductSubGroup(models.Model):
	_name = 'orchid.product.sub.group'
	_description = "Product Sub Group"

	code = fields.Char(string='Code',required=True)
	name = fields.Char(string='Name',required=True)
	group_id =  fields.Many2one('orchid.product.group', string='Group')

class OrchidProductClassification(models.Model):
	_name = 'orchid.product.classification'
	_description = "Product Classification"

	code = fields.Char(string='Code',required=True)
	name = fields.Char(string='Name',required=True)

class OrchidProductHscode(models.Model):
	_name = 'orchid.product.hscode' 
	_description = "Product HS Code"

	name = fields.Char(string='Number',required=True)
	orchid_country_id = fields.Many2one('res.country', string='Country Of Origin')
	description=fields.Text(string='Description')

class OdTransactionType(models.Model):
	_name = "od.transaction.type"

	name = fields.Char(string="Transaction Type")
	code = fields.Char(string="Code")