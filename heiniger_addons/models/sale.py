from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp

class Saleorder(models.Model):
	_inherit = "sale.order"

	od_free_qty=fields.Float(string="Free quantity")
	od_gross_weight = fields.Float(string='Gross Weight',compute='total_gross_weight')
	od_transportation = fields.Selection([('sea', 'Sea'),('road', 'Road'),('air', 'Air'),('express', 'Express')], string='Transportation',default='sea')
	od_purchase_id = fields.Many2one('purchase.order', readonly=True, string="Purchase Order")
	od_service = fields.Boolean(string="Service Invoice")
	od_transaction_type = fields.Selection([('Transfer', 'Transfer'),('STD', 'STD'),('Marketing', 'Marketing'),('Return', 'Return'),('Office Use', 'Office Use'),('Quality', 'Quality'),('Warranty', 'Warranty'),('In House', 'In House')], string='Transaction Type', default='STD')
	

	@api.depends('order_line','order_line.od_gross_weight')
	def total_gross_weight(self):
		gross=0
		for line in self.order_line:
			gross=gross+line.od_gross_weight
		self.od_gross_weight=gross


class Saleorderline(models.Model):
	_inherit = "sale.order.line"

	od_free_qty=fields.Float(string="Free quantity", digits=dp.get_precision('Product Unit of Measure'))
	od_adjustment_qty=fields.Float(string="Adjustment quantity", digits=dp.get_precision('Product Unit of Measure'))
	od_gross_weight = fields.Float(string='Gross Weight',compute="compute_gross_weight")
	od_transaction_type = fields.Many2one('od.transaction.type', string="Transaction Type", default=lambda self: self.env['od.transaction.type'].search([('code','=','SALE')], limit=1).id)

	@api.depends('product_uom_qty','od_free_qty','od_adjustment_qty')
	def compute_gross_weight(self):
		for line in self:
			line.od_gross_weight=(line.product_uom_qty+line.od_free_qty+line.od_adjustment_qty)*line.product_id.od_ttl_weight
	