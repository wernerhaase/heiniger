# -*- coding: utf-8 -*-


import re
from html import unescape

from odoo import models, api, fields
from odoo.tools import plaintext2html


def _looks_like_html(value):
    value = value or ''
    return bool(re.search(r'</?[A-Za-z][^>]*>', value))


def _plain_description(value):
    value = value or ''
    if not _looks_like_html(value):
        return value.strip()

    text = re.sub(r'<li[^>]*>', '\n- ', value, flags=re.IGNORECASE)
    text = re.sub(r'</li\s*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>|</p\s*>|</div\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>|<div[^>]*>|</?ul[^>]*>|</?ol[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text).replace('\xa0', ' ')
    lines = [' '.join(line.split()) for line in text.splitlines()]
    return '\n'.join(line for line in lines if line)

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

    @api.model
    def _hgr_description_values(self, values):
        values = dict(values)
        if values.get('hgr_html_description') or ('hgr_html_description' in values and 'name' not in values):
            # The rich editor is authoritative when both fields are submitted.
            values['name'] = _plain_description(values['hgr_html_description'])
        elif 'name' in values:
            value = values['name'] or ''
            values['hgr_html_description'] = value if _looks_like_html(value) else plaintext2html(value)
            values['name'] = _plain_description(value)
        return values

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create([self._hgr_description_values(vals) for vals in vals_list])
        for line in lines.filtered(lambda item: not item.hgr_html_description):
            description = line.name or ''
            if line.product_id and line.journal_id.type == 'sale':
                product = line.product_id.with_context(lang=line.partner_id.lang or self.env.lang)
                rich = '\n'.join(filter(None, [product.display_name, product.description_sale]))
                if _plain_description(rich) == description:
                    description = rich
            line.hgr_html_description = description if _looks_like_html(description) else plaintext2html(description)
        return lines

    def write(self, vals):
        if 'name' in vals and 'hgr_html_description' not in vals:
            # Re-saving the generated plain label must not erase existing styling.
            preserved = self.filtered(lambda line: line.hgr_html_description and
                                       vals['name'] == _plain_description(line.hgr_html_description))
            if preserved:
                super(AccountMoveline, preserved).write(vals)
                return super(AccountMoveline, self - preserved).write(self._hgr_description_values(vals)) if self - preserved else True
        return super().write(self._hgr_description_values(vals))

    @api.onchange('hgr_html_description')
    def _onchange_hgr_html_description(self):
        for line in self:
            line.name = _plain_description(line.hgr_html_description)

    @api.depends('product_id', 'move_id.ref', 'move_id.payment_reference')
    def _compute_name(self):
        super()._compute_name()
        for line in self:
            if _looks_like_html(line.name):
                line.hgr_html_description = line.name
                line.name = _plain_description(line.name)

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
            plain_name = _plain_description(html_name)
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
        self.invalidate_model(['name', 'hgr_html_description'])
        return len(updates)

    @api.model
    def hgr_action_check_html_invoice_labels(self):
        remaining = self.hgr_count_html_names_without_print_description()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'HTML Invoice Label Check',
                'message': 'Remaining HTML labels: %s' % remaining,
                'type': 'info',
                'sticky': True,
            },
        }

    @api.model
    def hgr_action_migrate_html_invoice_labels(self, limit=10000):
        migrated = self.hgr_migrate_html_names_to_print_description(limit=limit)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'HTML Invoice Label Cleanup',
                'message': 'Migrated %s journal items.' % migrated,
                'type': 'success',
                'sticky': True,
            },
        }

    @api.model
    def hgr_cron_migrate_html_invoice_labels(self, limit=10000):
        return self.hgr_migrate_html_names_to_print_description(limit=limit)

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
    hgr_plain_description = fields.Text(
        string="Plain Description",
        compute='_compute_hgr_plain_description',
        store=True,
    )

    sequence_no = fields.Integer('Position', related='sequence', store=False)

    @api.depends('name')
    def _compute_hgr_plain_description(self):
        for line in self:
            line.hgr_plain_description = _plain_description(line.name)

    def write(self, vals):
        res = super().write(vals)
        dontcall_function = self.env.context.get('dontcall_function')
        if not dontcall_function:
            for rec in self:
                order_id = rec.order_id
                order_id.reorder_sequence()
        return res

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        if self.name:
            vals['hgr_html_description'] = self.name
            vals['name'] = _plain_description(self.name)
        return vals
