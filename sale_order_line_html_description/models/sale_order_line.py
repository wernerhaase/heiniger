from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class SaleOrderLine(models.Model):

    _inherit = "sale.order.line"
    
    html_description = fields.Html(string="Description")
    
    def open_form(self):
        return {
            'name': 'Sale Order Line Html Description',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.order.line',
            'view_id': self.env.ref('sale_order_line_html_description.sale_order_line_view_html_description_form').id,
            'res_id': self.id,
            'target': 'new',
        }

    @api.onchange('product_id')
    def onchange_product_id(self):
        self.html_description = ''
        if self.product_id:
            self.html_description = self.product_id.html_description
