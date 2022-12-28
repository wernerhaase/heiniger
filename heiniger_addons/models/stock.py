from odoo import api, fields, models, _

# for gulf saleupload purpose
class WarehouseStock(models.Model):
	_inherit = 'stock.warehouse'

	od_code = fields.Char(string="Code")
