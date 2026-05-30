# -*- coding: utf-8 -*-


from odoo import models, api, fields
from odoo.tools import html2plaintext


HTML_MARKERS = (
    '<p', '</p', '<br', '<div', '</div', '<ul', '</ul', '<ol', '</ol',
    '<li', '</li', '<strong', '</strong', '<b', '</b', '<em', '</em',
    '<i', '</i', '<span', '</span', '&nbsp;',
)


def _looks_like_html(value):
    value = value or ''
    return any(marker in value.lower() for marker in HTML_MARKERS)

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

    hgr_html_description = fields.Html(string='Print Description')

    # def write(self, vals):
    #     move_lines = super(AccountMoveline, self).write(vals)
    #     return move_lines


    @api.model_create_multi
    def create(self, vals_list):
        for line_vals in vals_list:
            if (
                line_vals.get('name')
                and not line_vals.get('hgr_html_description')
                and _looks_like_html(line_vals['name'])
            ):
                line_vals['hgr_html_description'] = line_vals['name']
                line_vals['name'] = html2plaintext(line_vals['name'])
        move_lines = super(AccountMoveline, self).create(vals_list)
        for rec in move_lines:
            if rec.name:
                rec.name = rec.name.replace('&nbsp;', '&#160;').replace('<br>', '<br/>')
        return move_lines

    @api.model
    def hgr_count_html_names_without_print_description(self):
        self.env.cr.execute("""
            SELECT count(*)
              FROM account_move_line
             WHERE name ~ '<[A-Za-z/][^>]*>'
               AND hgr_html_description IS NULL
        """)
        return self.env.cr.fetchone()[0]

    @api.model
    def hgr_migrate_html_names_to_print_description(self, limit=None):
        query = """
            SELECT id, name
              FROM account_move_line
             WHERE name ~ '<[A-Za-z/][^>]*>'
               AND hgr_html_description IS NULL
             ORDER BY id
        """
        params = []
        if limit:
            query += " LIMIT %s"
            params.append(limit)

        self.env.cr.execute(query, params)
        rows = self.env.cr.fetchall()
        updates = []
        for line_id, html_name in rows:
            plain_name = html2plaintext(html_name or '')
            plain_name = plain_name.replace('&nbsp;', '&#160;').replace('<br>', '<br/>').strip()
            updates.append((html_name, plain_name, line_id, html_name))

        if updates:
            self.env.cr.executemany("""
                UPDATE account_move_line
                   SET hgr_html_description = %s,
                       name = %s
                 WHERE id = %s
                   AND hgr_html_description IS NULL
                   AND name = %s
            """, updates)
        return len(updates)

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
    def create(self, vals_list):
        orders = super(SaleOrder, self).create(vals_list)
        if not self.env.context.get('dontcall_function'):
            orders.reorder_sequence()
        return orders

    def write(self, vals):
        orders = super(SaleOrder, self).write(vals)
        if not self.env.context.get('dontcall_function'):
            self.reorder_sequence()
        return orders




class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    name = fields.Html(
        string="Description",
        compute='_compute_name',
        store=True, readonly=False, required=True, precompute=True)

    sequence_no = fields.Integer('Position', related='sequence', store=False)

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        if self.name:
            vals['hgr_html_description'] = self.name
            vals['name'] = html2plaintext(self.name)
        return vals


    def write(self,vals):
        res = super(SaleOrderLine, self).write(vals)
        dontcall_function = self.env.context.get('dontcall_function')
        if not dontcall_function:
            for rec in self:
                order_id = rec.order_id
                order_id.reorder_sequence()
        return res
