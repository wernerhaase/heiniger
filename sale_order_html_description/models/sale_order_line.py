# -*- coding: utf-8 -*-


from odoo import models, api, tools, fields, _

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    description_sale = fields.Html(
        'Sales Description', translate=True,
        help="A description of the Product that you want to communicate to your customers. "
             "This description will be copied to every Sales Order, Delivery Order and Customer Invoice/Credit Note")
class ProjectMilestone(models.Model):
    _inherit = 'project.milestone'
    sale_line_name = fields.Html(related='sale_line_id.name')


class AccountMoveline(models.Model):
    _inherit = 'account.move.line'

    name = fields.Html(
        string='Label',
        compute='_compute_name', store=True, readonly=False, precompute=True,
        tracking=True,
    )


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    name = fields.Html(
        string="Description",
        compute='_compute_name',
        store=True, readonly=False, required=True, precompute=True)

    sequence_no = fields.Integer('Sequence',related='sequence',store=False)