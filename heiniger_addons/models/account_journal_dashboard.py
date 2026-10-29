from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def _hgr_get_dashboard_ledger_balance(self, balance_date=None):
        """Return the posted GL balance of the journal's liquidity account."""
        self.ensure_one()
        balance_date = balance_date or fields.Date.context_today(self)
        return self._get_journal_bank_account_balance([
            ('parent_state', '=', 'posted'),
            ('date', '<=', balance_date),
        ])

    def _fill_bank_cash_dashboard_data(self, dashboard_data):
        super()._fill_bank_cash_dashboard_data(dashboard_data)

        journals = self.filtered(
            lambda journal: (
                journal.type == 'cash'
                or journal.default_account_id.account_type == 'liability_credit_card'
            )
            and journal.default_account_id
        )
        for journal in journals:
            balance, line_count = journal._hgr_get_dashboard_ledger_balance()
            currency = journal.currency_id or journal.company_id.sudo().currency_id
            accessible = journal.company_id.id in journal.company_id._accessible_branches().ids
            dashboard_data[journal.id].update({
                'account_balance': currency.format(balance),
                'nb_lines_bank_account_balance': bool(line_count) and accessible,
            })
