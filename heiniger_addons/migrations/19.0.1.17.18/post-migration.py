import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Offer only one unit per name on quotation/invoice lines."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    hidden = env['uom.uom']._hgr_dedupe_selectable()
    _logger.info('Heiniger: %s duplicate/unused units hidden from quote lines', len(hidden))
