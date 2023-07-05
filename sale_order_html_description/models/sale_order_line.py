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

    def write(self, vals):
        move_lines = super(AccountMoveline, self).write(vals)
        return move_lines


    @api.model_create_multi
    def create(self, vals):

        move_lines = super(AccountMoveline, self).cretae(vals)

        name = move_lines.name
        new_name = name.replace('&nbsp;', '&#160;')
        move_lines.name = new_name
        return move_lines

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def has_duplicates(self,lst):
        return len(lst) != len(set(lst))

    def reorder_sequence(self):
        for order in self:
            sequence_list = order.order_line.sorted('sequence').mapped('sequence')
            lines = order.order_line.sorted('sequence')
            # print(sequence_list)
            # if self.has_duplicates(sequence_list):
            starting_seq = 10
            for line in lines:
                line.with_context({'dontcall_function': True}).write({'sequence': starting_seq})
                starting_seq += 1


    @api.model_create_multi
    def create(self, vals):
        orders = super(SaleOrder, self).create(vals)
        self.reorder_sequence()
        return orders

    def write(self,vals):
        orders = super(SaleOrder, self).write(vals)
        self.reorder_sequence()
        return orders




class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    name = fields.Html(
        string="Description",
        compute='_compute_name',
        store=True, readonly=False, required=True, precompute=True)

    sequence_no = fields.Integer('Sequence',related='sequence',store=False)


    def write(self,vals):
        res = super(SaleOrderLine, self).write(vals)
        dontcall_function = self.env.context.get('dontcall_function')
        if not dontcall_function:
            for rec in self:
                order_id = rec.order_id
                order_id.reorder_sequence()
        return res