import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    projects = env['project.project'].search([('account_id', '!=', False)])
    updated_accounts = projects._hgr_sync_analytic_quotation_codes()
    without_quotation = projects.filtered(
        lambda project: not project._hgr_profitability_sale_orders()
    )
    _logger.info(
        'Backfilled quotation references on %s project analytic account(s); '
        '%s project(s) have no linked quotation and were left unchanged',
        len(updated_accounts),
        len(without_quotation),
    )
