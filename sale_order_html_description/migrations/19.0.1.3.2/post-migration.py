import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    accounting_model = env['account.bank.statement.line']
    before_accounting = accounting_model.hgr_count_accounting_html_tags()
    cleaned_accounting = accounting_model.hgr_cleanup_accounting_html_tags()
    after_accounting = accounting_model.hgr_count_accounting_html_tags()

    move_lines = env['account.move.line']
    before_invoice_labels = move_lines.hgr_count_html_names_without_print_description()
    migrated_invoice_labels = 0
    while True:
        migrated = move_lines.hgr_migrate_html_names_to_print_description(limit=10000)
        migrated_invoice_labels += migrated
        if migrated < 10000:
            break
    after_invoice_labels = move_lines.hgr_count_html_names_without_print_description()

    if any(after_accounting.values()) or after_invoice_labels:
        raise RuntimeError(
            'HTML cleanup incomplete: '
            f'accounting={after_accounting}, invoice_labels={after_invoice_labels}'
        )

    _logger.info(
        'Heiniger HTML cleanup completed: accounting before=%s cleaned=%s after=%s; '
        'invoice labels before=%s migrated=%s after=%s',
        before_accounting,
        cleaned_accounting,
        after_accounting,
        before_invoice_labels,
        migrated_invoice_labels,
        after_invoice_labels,
    )
