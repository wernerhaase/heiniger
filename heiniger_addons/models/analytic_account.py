from odoo import api, models
from odoo.fields import Domain


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    # Analytic distribution uses name_search. Include the linked project's
    # customer and standard sales-order links so migrated accounts remain
    # searchable even when those values were not copied to the account.
    _rec_names_search = [
        'name',
        'code',
        'partner_id',
        'project_ids.partner_id',
        'project_ids.sale_order_id',
        'project_ids.reinvoiced_sale_order_id',
    ]

    @api.depends('name', 'code', 'partner_id.commercial_partner_id.name')
    def _compute_display_name(self):
        """Show the quotation reference without duplicating legacy names.

        Older analytic accounts sometimes use the quotation number as their
        name. Newer accounts keep the descriptive project name and store the
        primary quotation in ``code`` (the standard Reference field).
        """
        for account in self:
            name = account.name
            if account.code and account.code not in name:
                name = f'[{account.code}] {name}'
            if account.partner_id.commercial_partner_id.name:
                name = f'{name} - {account.partner_id.commercial_partner_id.name}'
            account.display_name = name

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        if operator in Domain.NEGATIVE_OPERATORS or not value:
            return domain

        # A sales order can select an existing project directly. That link is
        # not exposed as an inverse field on project.project, so it cannot be
        # expressed in _rec_names_search like the standard sale_order_id links.
        direct_orders = self.env['sale.order']._search([
            ('name', operator, value),
            ('project_id', '!=', False),
        ])
        return domain | Domain(
            'project_ids.id', 'in', direct_orders.subselect('project_id')
        )
