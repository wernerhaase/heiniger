from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):

    _inherit = "product.template"
    
    html_description = fields.Html(string="Description")