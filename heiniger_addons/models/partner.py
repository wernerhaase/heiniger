from datetime import datetime

from odoo import api, fields, models, _

# Modification in Partner Master
class Partner(models.Model):
	_inherit = 'res.partner' 

	od_bus_type = fields.Many2one('orchid.buss.type',string='Business Entity Type')
	od_license_no = fields.Char(string='Trade License Number')
	od_lic_expiry_date = fields.Date(string='License Expiry Date')
	od_cc_no = fields.Char(string='Chamber of Commerce Number')
	od_cc_expiry_date = fields.Date(string='CoC Expiry Date')
	od_issue_authority = fields.Char(string='License Issuing Authority')
	od_owner_name = fields.Char(string='Name of The Owner')
	od_owner_national = fields.Char(string='Owner Nationality')
	od_spons_name = fields.Char(string='Name of the Sponsor')
	od_spons_national = fields.Char(string='Sponsor Nationality')

	# od_lne_buss = fields.Char(string='Line Of Business')
	# od_distr_chanel = fields.Char(string='Distribution Channel')
	od_lne_buss_id = fields.Many2one('orchid.line.of.business',string='Line Of Business')
	od_distr_chanel_id = fields.Many2one('orchid.distribution.channel',string='Distribution Channel')
	od_branch = fields.Boolean(string='Branch', default=False)
	od_man_assem = fields.Boolean(string='Manufacturing/Assembly', default=False)
	od_ttl_empl = fields.Integer(string='Total employees')
	od_ttl_mgt_staff = fields.Integer(string='Total Management Staff')
	od_tover_prd_1 = fields.Date(string="Turnover Declaration From")
	od_tover_prd_2 = fields.Date(string="Turnover Declaration To")
	potential_tover_1 = fields.Date(string="Potential / Expected Turnover with Somfy From")
	potential_tover_2 = fields.Date(string="Potential / Expected Turnover with Somfy To")
	 
	
	# od_arabic_name=fields.Char(string="Name in Arabic")
	# od_arabic_street = fields.Char(string="Arabic Street")
	# od_arabic_street2 = fields.Char(string="Arabic Street2")
	# od_arabic_city = fields.Char(string="Arabic City")
	# od_arabic_state_id = fields.Char(related='state_id.od_arabic_name', string='Arabic State', ondelete='restrict', store=True)
	# od_arabic_country_id = fields.Char(related='country_id.od_arabic_name', string='Arabic Country', ondelete='restrict', store=True)
	# od_arabic_property_supplier_payment_term_id = fields.Char(related='property_supplier_payment_term_id.od_arabic_name',string="Vendor Payment Terms in Arabic", store=True)
	# od_arabic_property_payment_term_id = fields.Char(related='property_payment_term_id.od_arabic_name',string="Customer Payment Terms in Arabic", store=True)
	od_commercial_identification =fields.Char(string="Commercial Identification")
	od_ban_bp =fields.Char(string="BAN BP Code")
	od_insured_credit_limit =fields.Float(string='Insured Credit Limit')
	od_payment_behaviour = fields.Selection([('regular', 'Regular'),('doubt', 'Doubtful'),('unsatisfied', 'Unsatisfactory')], string='Payment Behaviour',default='regular')
	
	od_credit_insurance_ref =fields.Char(string="Credit Insurance Reference")
	od_name_unamed = fields.Selection([('named', 'Named'),('un_named', 'UnNamed'),('out_of_scope', 'Out of Scope')], string='Named/Un Named')
	# od_coverage_type =fields.Selection([('named','Named Coverage'),('unnamed','Unnamed Coverage')],string='Credit Insurance Coverage Type', default="unnamed")
	od_coverage_value =fields.Float(string='Credit Insurance Coverage Value')

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			if vals.get('is_company') == True:
				seq_obj = self.env['ir.sequence']
				ref_num = seq_obj.next_by_code('res.partner')
				partner = vals.get('name')
				start = 0
				limit = 4
				if len(partner) > 3:
					while True:
						partner_name = partner.find(" ",start,limit)
						if partner_name == -1 :
							partner = partner[start:limit]
							break
						else:
							start = partner_name + 1
							limit = start + 4
				vals['ref'] =str(partner) + ref_num
		return super(Partner, self).create(vals_list)




# class CountrySateInher(models.Model):
# 	_inherit = "res.country.state"

# 	od_arabic_name = fields.Char(string='Arabic Name')


# class CountryInher(models.Model):
# 	_inherit = "res.country"

# 	od_arabic_name = fields.Char(string='Arabic Name')

# class AccountPaymentTermInher(models.Model):
# 	_inherit = "account.payment.term"

# 	od_arabic_name = fields.Char(string='Arabic Name')
# 	od_arabic_note = fields.Text(string='Arabic Description on the Invoice')

