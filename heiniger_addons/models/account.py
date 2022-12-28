from odoo import api, fields, models, _

# for gulf saleupload purpose
class AccountPaymentTerm(models.Model):
	_inherit = 'account.payment.term'

	od_code = fields.Char(string="Code")

# class AccountAccount(models.Model):
# 	_inherit = "account.account"

# 	od_arabic_name=fields.Char(string="Arabic Name")