from odoo import models


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    # Analytic distribution uses name_search. Include both the account's
    # customer and customers of linked projects so migrated accounts remain
    # searchable even when partner_id was not copied to the analytic account.
    _rec_names_search = [
        'name',
        'code',
        'partner_id',
        'project_ids.partner_id',
    ]
