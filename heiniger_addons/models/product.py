from odoo import api, fields, models, _


# class OrchidProductGroup(models.Model):
# 	_inherit = 'orchid.product.group'
   
# 	arab_name = fields.Char(string='Arabic Name',required=True)

class OrchidProductCategory(models.Model):
	_inherit = 'product.category'
   
	od_code = fields.Char(string='Code',required=True)    


# Modification in Inventory Product
class ProducTemplate(models.Model):
	_inherit = 'product.template' 

	od_com_code = fields.Char(string='Commodity Code')
	od_mult_qty = fields.Float(string='Multiple Quantity')
	od_pcs_box = fields.Float(string='Pcs/Box')
	od_depth = fields.Float(string='Depth(mm)')
	od_width = fields.Float(string='Width(mm)')
	od_height = fields.Float(string='Height(mm)')
	od_weight = fields.Float(string='Weight(kg)')
	od_pkg_weight = fields.Float(string='Packaging Weight')
	od_ttl_weight = fields.Float(string='Total Weight')
	od_pcs_pallet = fields.Float(string='Pcs/Pallet')
	od_box_layer = fields.Float(string='Nb box/Layer')
	od_layer = fields.Float(string='Nb of Layers')
	od_box_pallet = fields.Float(string='Nb Boxes/ pallet')
	od_max_pallet_ht = fields.Float(string='Pallet Max Height(mm)')
	od_cbm_vol = fields.Float(string='CBM')
	od_factory_cost = fields.Float(string="Factory Cost")

	orchid_brand_id =  fields.Many2one('orchid.product.brand', string='Brand')
	orchid_type_id =  fields.Many2one('orchid.product.type', string='Type')
	orchid_sub_type_id =  fields.Many2one('orchid.product.sub.type', string='Sub Type')
	orchid_group_id =  fields.Many2one('orchid.product.group', string='Group')
	orchid_sub_group_id =  fields.Many2one('orchid.product.sub.group', string='Sub Group')
	orchid_class_id =  fields.Many2one('orchid.product.classification', string='Classification')
	orchid_country_id = fields.Many2one('res.country', string='Country Of Origin')
	orchid_hscode_id = fields.Many2one('orchid.product.hscode', string='HS Code')
	# orchid_arabic = fields.Char(string='Arabic Name')
	
	
class ProductProduct(models.Model):
	_inherit = "product.product"

	#to pass costcenter to movelines from vendorbill
	@api.model
	def _convert_prepared_anglosaxon_line(self, line, partner):
		res = super(ProductProduct,self)._convert_prepared_anglosaxon_line(line, partner)
		if 'orchid_cc_id' in line:
			res['orchid_cc_id'] = line['orchid_cc_id']
		return res



