from odoo import api, fields, models, _

class AccountInvoice(models.Model):
	_inherit = "account.move"

	od_gross_weight = fields.Float(string='Gross Weight')
	od_no_of_packages = fields.Char(string='No.of Packages')
	od_transportation = fields.Selection([('sea', 'Sea'),('road', 'Road'),('air', 'Air'),('express', 'Express')], string='Transportation',default='sea')
	od_packing_list_no = fields.Char(string="Packing List No.")
	od_packing_type = fields.Char(string="Packing Type")
	od_packing_qty = fields.Char(string="Packing Qty")
	od_warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
	od_destination = fields.Char(string="Destination")
	# od_be_ref_no = fields.Char(string="B/E Ref No.")
	od_be_ref_no = fields.Text(string="B/E Ref No.")
	od_customs_bill = fields.Selection([('import', 'Import'),('temporary_exit', 'Temporary Exit'),('export', 'Export'),('re_export', 'Import for Re-Export'),
										('free_zone', 'Freezone Internal Transfer'),('fze', 'FZE Bill of Entry')], string='Customs Bill')
	od_cbm_vol = fields.Float(string="Volume CBM")
	od_forwarder = fields.Char(string="Forwarder")
	od_gbw_ref_no = fields.Char(string="GBW Reference No")
	od_cos_entry_id = fields.Many2one('account.move', string="Cost of Sales Entry")
	excel_file = fields.Binary(string='Excel Report',readonly="1")
	od_exchange_rate=fields.Float(string="Exchange Rate", digits=(12, 6), help="Company currency to foreign currency rate")
	# od_amount_untaxed = fields.Monetary(string='Local Untaxed Amount', store=True, readonly=True, compute='od_local_amounts', digits=(12, 4))
	# od_amount_tax = fields.Monetary(string='Local Taxes', store=True, readonly=True, compute='od_local_amounts')
	# od_amount_total = fields.Monetary(string='Local Total', store=True, readonly=True, compute='od_local_amounts')
	od_transaction_type = fields.Selection([('Transfer', 'Transfer'),('STD', 'STD'),('Marketing', 'Marketing'),('Return', 'Return'),('Office Use', 'Office Use'),('Quality', 'Quality'),('Warranty', 'Warranty'),('In House', 'In House')], string='Transaction Type')
	stamp = fields.Boolean(string="Stamp & Sign")

	@api.onchange('invoice_line_ids')
	def total_gross_weight(self):
		gross=0
		for line in self.invoice_line_ids:
			gross=gross+line.od_gross_weight
		self.od_gross_weight=gross


	# @api.depends('od_exchange_rate','amount_total','date_invoice')
	# def od_local_amounts(self):
	# 	for record in self:
	# 		if record.od_exchange_rate:
	# 			exchange_rate = self.od_exchange_rate
	# 			record.od_amount_untaxed = record.amount_untaxed / exchange_rate
	# 			record.od_amount_tax = record.amount_tax / exchange_rate
	# 			record.od_amount_total = record.amount_total / exchange_rate

	# 			#creating or checking the exchange rate with given rate and invoice date
	# 			if self.type == 'out_invoice':
	# 				date = self.date_invoice if self.date_invoice else datetime.today().date()
	# 				currency_rate_id = self.env['res.currency.rate'].search([('currency_id','=',self.currency_id.id),('name','=',date)])
	# 				if not currency_rate_id:
	# 					vals={'rate':exchange_rate,'name':date,'currency_id':self.currency_id.id}
	# 					self.env['res.currency.rate'].create(vals)
	

	class AccountInvoiceLine(models.Model):
	_inherit = "account.move.line"

	od_gross_weight = fields.Float(string='Gross Weight',compute="compute_gross_weight")
	orchid_country_id = fields.Many2one('res.country', string='Country Of Origin')
	od_free_qty=fields.Float(string="Free quantity", digits=dp.get_precision('Product Unit of Measure'))
	od_adjustment_qty=fields.Float(string="Adjustment quantity", digits=dp.get_precision('Product Unit of Measure'))
	od_ttl_qty = fields.Float(string="Total quantity",digits=dp.get_precision('Product Unit of Measure'))
	od_transaction_type = fields.Many2one('od.transaction.type', string="Transaction Type", default=lambda self: self.env['od.transaction.type'].search([('code','=','SALE')], limit=1).id)

	@api.depends('quantity','od_free_qty','od_adjustment_qty')
	def compute_gross_weight(self):
		for line in self:
			line.od_gross_weight=(line.quantity+line.od_free_qty+line.od_adjustment_qty)*line.product_id.od_ttl_weight
			line.od_ttl_qty = line.quantity + line.od_free_qty + line.od_adjustment_qty

	@api.onchange('product_id')
	def od_onchange_country(self):
		for line in self:
			if line.product_id:
				line.orchid_country_id = line.product_id.orchid_country_id and line.product_id.orchid_country_id.id
