from odoo import fields, models, Command


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    hgr_tax_id = fields.Many2one(
        'account.tax',
        string='Tax',
        check_company=True,
        help='Tax applied to the counterpart journal item when creating the transaction.',
    )

    def set_account_bank_statement_line(self, aml_id, account_id):
        result = super().set_account_bank_statement_line(aml_id, account_id)
        for statement_line in self.filtered('hgr_tax_id'):
            counterpart_line = statement_line.line_ids.filtered(
                lambda line: (
                    line.account_id.id == account_id
                    and not line.tax_line_id
                    and not line.reconciled_lines_ids
                )
            )[-1:]
            if counterpart_line:
                statement_line.edit_reconcile_line(counterpart_line.id, {
                    'tax_ids': [Command.set(statement_line.hgr_tax_id.ids)],
                })
        return result
