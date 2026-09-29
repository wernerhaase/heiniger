# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.tools import html2plaintext


HTML_TAG_RE = '<[A-Za-z/][^>]*>'

ACCOUNTING_HTML_FIELDS = (
    ('account_bank_statement_line', 'payment_ref'),
    ('account_analytic_line', 'name'),
    ('account_analytic_line', 'ref'),
    ('account_move_line', 'ref'),
)


def _html_to_clean_text(value):
    clean_value = html2plaintext(value or '')
    clean_value = clean_value.replace('&nbsp;', ' ').replace('<br>', ' ')
    return ' '.join(clean_value.split())


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    @api.model
    def hgr_action_audit_accounting_html_tags(self):
        counts = self.hgr_count_accounting_html_tags()
        message = '\n'.join(
            f'{field_name}: {count}'
            for field_name, count in counts.items()
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Accounting HTML Tags Found',
                'message': message or 'No HTML tags found in accounting cleanup fields.',
                'type': 'warning' if any(counts.values()) else 'success',
                'sticky': True,
            },
        }

    @api.model
    def hgr_action_cleanup_accounting_html_tags(self):
        before = self.hgr_count_accounting_html_tags()
        cleaned = self.hgr_cleanup_accounting_html_tags()
        after = self.hgr_count_accounting_html_tags()
        lines = []
        for field_name in before:
            lines.append(
                f'{field_name}: cleaned {cleaned.get(field_name, 0)} '
                f'(before {before[field_name]}, after {after[field_name]})'
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Accounting HTML Tags Cleanup',
                'message': '\n'.join(lines),
                'type': 'success',
                'sticky': True,
            },
        }

    @api.model
    def hgr_cron_cleanup_accounting_html_tags(self):
        return self.hgr_cleanup_accounting_html_tags()

    @api.model
    def hgr_count_html_payment_refs(self):
        self.env.cr.execute("""
            SELECT count(*)
              FROM account_bank_statement_line
             WHERE payment_ref ~ '<[A-Za-z/][^>]*>'
        """)
        return self.env.cr.fetchone()[0]

    @api.model
    def hgr_cleanup_html_payment_refs(self, limit=None):
        return self._hgr_cleanup_html_column('account_bank_statement_line', 'payment_ref', limit)

    @api.model
    def hgr_count_accounting_html_tags(self):
        result = {}
        for table_name, column_name in ACCOUNTING_HTML_FIELDS:
            self.env.cr.execute(
                f'SELECT count(*) FROM {table_name} WHERE {column_name} ~ %s',
                [HTML_TAG_RE],
            )
            result[f'{table_name}.{column_name}'] = self.env.cr.fetchone()[0]
        return result

    @api.model
    def hgr_cleanup_accounting_html_tags(self, limit_per_field=None):
        result = {}
        for table_name, column_name in ACCOUNTING_HTML_FIELDS:
            result[f'{table_name}.{column_name}'] = self._hgr_cleanup_html_column(
                table_name, column_name, limit_per_field
            )
        return result

    @api.model
    def _hgr_cleanup_html_column(self, table_name, column_name, limit=None):
        if (table_name, column_name) not in ACCOUNTING_HTML_FIELDS:
            raise ValueError('Unsupported accounting cleanup field')

        query = f"""
            SELECT id, {column_name}
              FROM {table_name}
             WHERE {column_name} ~ %s
             ORDER BY id
        """
        params = [HTML_TAG_RE]
        if limit:
            query += " LIMIT %s"
            params.append(limit)

        self.env.cr.execute(query, params)
        updates = []
        for record_id, html_value in self.env.cr.fetchall():
            clean_value = _html_to_clean_text(html_value)
            updates.append((clean_value, record_id, html_value))

        if updates:
            self.env.cr.executemany(f"""
                UPDATE {table_name}
                   SET {column_name} = %s
                 WHERE id = %s
                   AND {column_name} = %s
            """, updates)
        return len(updates)
