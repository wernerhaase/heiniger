from odoo import fields,models,api,_

class PurchaseOrder(models.Model):
	_inherit='purchase.order'

	old_erp_id = fields.Integer(string="Old ERP ID")

class PurchaseOrderLine(models.Model):
	_inherit='purchase.order.line'

	old_erp_id = fields.Integer(string="Old ERP ID")

class SaleOrder(models.Model):
	_inherit='sale.order'

	old_erp_id = fields.Integer(string="Old ERP ID")

class SalerderLine(models.Model):
	_inherit='sale.order.line'

	old_erp_id = fields.Integer(string="Old ERP ID")

class Partner(models.Model):
	_inherit='res.partner'

	old_erp_id = fields.Integer(string="Old ERP ID")

class ProductTemplate(models.Model):
	_inherit='product.template'

	old_erp_id = fields.Integer(string="Old ERP ID")