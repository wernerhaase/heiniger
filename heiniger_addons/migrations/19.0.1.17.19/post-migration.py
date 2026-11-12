import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Merge duplicate units (10x kg, Psch, Stk, Std ...) left by the v17 migration."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Uom = env['uom.uom']
    merged = Uom._hgr_merge_duplicate_uoms()
    hidden = Uom._hgr_dedupe_selectable()
    _logger.info(
        'Heiniger: merged %s duplicate units into %s units, %s units hidden from quotes',
        sum(len(v) for v in merged.values()), len(merged), len(hidden),
    )
