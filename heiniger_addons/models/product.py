
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class Product(models.Model):
    _inherit = 'product.product'

    def get_product_multiline_description_sale(self):
        """ Compute a multiline description of this product, in the context of sales
                (do not use for purchases or other display reasons that don't intend to use "description_sale").
            It will often be used as the default description of a sale order line referencing this product.
        Defualt changed as heiniger wants to print product name in bold
        """
        name = self.display_name
        if self.description_sale:
            # name += '\n' + self.description_sale
            name =  self.description_sale
        print ("????????????????????????????????????????",name)    
        return name