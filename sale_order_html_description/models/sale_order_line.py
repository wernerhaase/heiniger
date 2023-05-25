# -*- coding: utf-8 -*-


from odoo import models, api, tools, fields, _


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
