from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestDashboardLedgerBalance(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cash_account = cls.env['account.account'].create({
            'code': 'HGR.DASH.CASH',
            'name': 'Dashboard cash test',
            'account_type': 'asset_cash',
        })
        cls.counterpart_account = cls.env['account.account'].create({
            'code': 'HGR.DASH.COUNTERPART',
            'name': 'Dashboard counterpart test',
            'account_type': 'liability_current',
        })
        cls.cash_journal = cls.env['account.journal'].create({
            'name': 'Dashboard cash test',
            'code': 'HGDCT',
            'type': 'cash',
            'default_account_id': cls.cash_account.id,
        })

    @classmethod
    def _create_move(cls, date, amount, posted=True):
        move = cls.env['account.move'].create({
            'date': date,
            'journal_id': cls.company_data['default_journal_misc'].id,
            'line_ids': [
                Command.create({
                    'name': 'Dashboard balance test',
                    'account_id': cls.cash_account.id,
                    'debit': amount,
                }),
                Command.create({
                    'name': 'Dashboard balance test',
                    'account_id': cls.counterpart_account.id,
                    'credit': amount,
                }),
            ],
        })
        if posted:
            move.action_post()
        return move

    def test_ledger_balance_uses_posted_entries_through_cutoff(self):
        cutoff = fields.Date.from_string('2026-10-28')
        self._create_move('2026-10-28', 2394.20)
        self._create_move('2026-10-28', 500.00, posted=False)
        self._create_move('2026-10-29', 1000.00)

        balance, line_count = self.cash_journal._hgr_get_dashboard_ledger_balance(cutoff)

        self.assertEqual(balance, 2394.20)
        self.assertEqual(line_count, 1)

    def test_dashboard_displays_ledger_instead_of_statement_balance(self):
        today = fields.Date.context_today(self.cash_journal)
        self._create_move(today, 2394.20)

        dashboard_data = self.cash_journal._get_journal_dashboard_data_batched()[
            self.cash_journal.id
        ]

        self.assertEqual(
            dashboard_data['account_balance'],
            self.company_data['currency'].format(2394.20),
        )
        self.assertTrue(dashboard_data['nb_lines_bank_account_balance'])

    def test_credit_card_dashboard_displays_ledger_balance(self):
        credit_account = self.env['account.account'].create({
            'code': 'HGR.DASH.CREDIT',
            'name': 'Dashboard credit-card test',
            'account_type': 'liability_credit_card',
        })
        credit_journal = self.env['account.journal'].create({
            'name': 'Dashboard credit-card test',
            'code': 'HGDCC',
            'type': 'credit',
            'default_account_id': credit_account.id,
        })
        move = self.env['account.move'].create({
            'date': fields.Date.context_today(credit_journal),
            'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                Command.create({
                    'name': 'Dashboard credit-card balance test',
                    'account_id': self.counterpart_account.id,
                    'debit': 87485.35,
                }),
                Command.create({
                    'name': 'Dashboard credit-card balance test',
                    'account_id': credit_account.id,
                    'credit': 87485.35,
                }),
            ],
        })
        move.action_post()

        dashboard_data = credit_journal._get_journal_dashboard_data_batched()[
            credit_journal.id
        ]

        self.assertEqual(
            dashboard_data['account_balance'],
            self.company_data['currency'].format(-87485.35),
        )
        self.assertTrue(dashboard_data['nb_lines_bank_account_balance'])
