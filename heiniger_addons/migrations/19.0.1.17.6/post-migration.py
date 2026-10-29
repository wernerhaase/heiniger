import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    projects = env['project.project'].search([('account_id', '!=', False)])
    orders = env['sale.order']
    for project in projects:
        orders |= project._hgr_profitability_sale_orders()
    updated_lines = orders._hgr_sync_line_analytic_distributions()
    _logger.info(
        'Corrected project analytic distributions on %s sale order line(s)',
        len(updated_lines),
    )
