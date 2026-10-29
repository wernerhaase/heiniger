from math import copysign

from odoo import api, Command, fields, models, _
from odoo.exceptions import ValidationError


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    # Kept for backwards compatibility with transactions created before the
    # multi-tax allocation feature.  New views use hgr_tax_ids instead.
    hgr_tax_id = fields.Many2one(
        'account.tax',
        string='Legacy Quick Tax',
        check_company=True,
        help='Tax applied to the counterpart journal item when creating the transaction.',
    )
    hgr_tax_ids = fields.Many2many(
        'account.tax',
        'hgr_bank_statement_line_tax_rel',
        'statement_line_id',
        'tax_id',
        string='Taxes',
        check_company=True,
        help='Taxes to allocate across the transaction when creating counterpart journal items.',
    )
    hgr_tax_allocation_ids = fields.One2many(
        'hgr.bank.statement.tax.allocation',
        'statement_line_id',
        string='Tax Allocations',
        copy=False,
    )
    hgr_tax_count = fields.Integer(compute='_compute_hgr_tax_allocation_summary')
    hgr_tax_allocation_total = fields.Monetary(
        string='Allocated',
        currency_field='currency_id',
        compute='_compute_hgr_tax_allocation_summary',
    )
    hgr_tax_allocation_remaining = fields.Monetary(
        string='Remaining',
        currency_field='currency_id',
        compute='_compute_hgr_tax_allocation_summary',
    )

    @api.depends('amount', 'hgr_tax_ids', 'hgr_tax_allocation_ids.amount')
    def _compute_hgr_tax_allocation_summary(self):
        for statement_line in self:
            taxes = statement_line._hgr_selected_taxes()
            statement_line.hgr_tax_count = len(taxes)
            if len(taxes) == 1:
                allocated = abs(statement_line.amount)
            else:
                allocated = sum(statement_line.hgr_tax_allocation_ids.mapped('amount'))
            statement_line.hgr_tax_allocation_total = allocated
            statement_line.hgr_tax_allocation_remaining = abs(statement_line.amount) - allocated

    @api.onchange('hgr_tax_ids')
    def _onchange_hgr_tax_ids(self):
        """Keep one editable gross allocation row for each selected tax."""
        for statement_line in self:
            amounts_by_tax = {
                allocation.tax_id.id: allocation.amount
                for allocation in statement_line.hgr_tax_allocation_ids
                if allocation.tax_id
            }
            allocation_commands = [Command.clear()]
            allocation_commands.extend(
                Command.create({
                    'tax_id': tax.id,
                    'amount': amounts_by_tax.get(
                        tax.id,
                        abs(statement_line.amount)
                        if len(statement_line.hgr_tax_ids) == 1
                        else 0.0,
                    ),
                })
                for tax in statement_line.hgr_tax_ids
            )
            statement_line.hgr_tax_allocation_ids = allocation_commands

    @api.model_create_multi
    def create(self, vals_list):
        # Preserve integrations that still send the original single-tax field.
        for vals in vals_list:
            if vals.get('hgr_tax_id') and not vals.get('hgr_tax_ids'):
                vals['hgr_tax_ids'] = [Command.set([vals['hgr_tax_id']])]
        return super().create(vals_list)

    @api.constrains(
        'amount',
        'hgr_tax_ids',
        'hgr_tax_allocation_ids',
    )
    def _check_hgr_tax_allocations(self):
        for statement_line in self:
            statement_line._hgr_get_tax_allocations(validate=True)

    def _hgr_selected_taxes(self):
        self.ensure_one()
        return self.hgr_tax_ids or self.hgr_tax_id

    def _hgr_get_tax_allocations(self, *, validate=False):
        """Return ``(tax, gross amount)`` pairs for the reconciliation.

        A single selected tax always receives the complete transaction amount.
        Multiple taxes require an explicit positive gross allocation per tax.
        """
        self.ensure_one()
        taxes = self._hgr_selected_taxes()
        if not taxes:
            return []
        if len(taxes) == 1:
            return [(taxes, abs(self.amount))]

        allocation_by_tax = {
            allocation.tax_id.id: allocation
            for allocation in self.hgr_tax_allocation_ids
            if allocation.tax_id
        }
        selected_tax_ids = set(taxes.ids)
        allocated_tax_ids = set(allocation_by_tax)
        allocations = [
            (tax, allocation_by_tax[tax.id].amount)
            for tax in taxes
            if tax.id in allocation_by_tax
        ]

        if validate:
            if allocated_tax_ids != selected_tax_ids:
                raise ValidationError(_(
                    'Add one gross allocation for every selected tax.'
                ))
            if any(amount <= 0 for _tax, amount in allocations):
                raise ValidationError(_(
                    'Every selected tax must have a gross allocation greater than zero.'
                ))
            allocated_total = sum(amount for _tax, amount in allocations)
            if self.currency_id.compare_amounts(allocated_total, abs(self.amount)) != 0:
                raise ValidationError(_(
                    'Tax allocations must total %(transaction_amount)s. '
                    'The current allocated total is %(allocated_amount)s.',
                    transaction_amount=self.currency_id.format(abs(self.amount)),
                    allocated_amount=self.currency_id.format(allocated_total),
                ))
        return allocations

    def _hgr_find_counterpart_line(self, account_id, *, without_tax=False):
        self.ensure_one()
        lines = self.line_ids.filtered(
            lambda line: (
                line.account_id.id == account_id
                and not line.tax_line_id
                and not line.reconciled_lines_ids
                and (not without_tax or not line.tax_ids)
            )
        )
        return lines[-1:]

    def _hgr_apply_tax_allocation(self, counterpart_line, tax, gross_amount):
        self.ensure_one()
        amount_currency = copysign(gross_amount, counterpart_line.amount_currency)
        balance = self._prepare_counterpart_amounts_using_st_line_rate(
            counterpart_line.currency_id,
            None,
            amount_currency,
        )['balance']
        self.edit_reconcile_line(counterpart_line.id, {
            'amount_currency': amount_currency,
            'balance': balance,
            'tax_ids': [Command.set(tax.ids)],
        })

    def set_account_bank_statement_line(self, aml_id, account_id):
        result = super().set_account_bank_statement_line(aml_id, account_id)
        for statement_line in self.filtered(lambda line: line._hgr_selected_taxes()):
            allocations = statement_line._hgr_get_tax_allocations(validate=True)
            counterpart_line = statement_line._hgr_find_counterpart_line(account_id)
            if not counterpart_line:
                continue

            for allocation_index, (tax, gross_amount) in enumerate(allocations):
                statement_line._hgr_apply_tax_allocation(counterpart_line, tax, gross_amount)
                if allocation_index == len(allocations) - 1:
                    continue

                _liquidity_lines, suspense_lines, _other_lines = statement_line._seek_for_lines()
                if not suspense_lines:
                    raise ValidationError(_(
                        'The tax allocations exceed the remaining transaction amount.'
                    ))
                super(
                    AccountBankStatementLine,
                    statement_line.with_context(account_default_taxes=False),
                ).set_account_bank_statement_line(suspense_lines[-1:].id, account_id)
                counterpart_line = statement_line._hgr_find_counterpart_line(
                    account_id,
                    without_tax=True,
                )
                if not counterpart_line:
                    raise ValidationError(_(
                        'Odoo could not create the next tax allocation line.'
                    ))
        return result


class HgrBankStatementTaxAllocation(models.Model):
    _name = 'hgr.bank.statement.tax.allocation'
    _description = 'Bank Statement Tax Allocation'
    _order = 'id'

    statement_line_id = fields.Many2one(
        'account.bank.statement.line',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(related='statement_line_id.company_id', store=True)
    currency_id = fields.Many2one(related='statement_line_id.currency_id', store=True)
    tax_id = fields.Many2one(
        'account.tax',
        string='Tax',
        required=True,
        check_company=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
    )
    amount = fields.Monetary(
        string='Gross Amount',
        currency_field='currency_id',
        required=True,
        help='Gross transaction amount belonging to this tax rate.',
    )

    _tax_per_statement_uniq = models.Constraint(
        'UNIQUE(statement_line_id, tax_id)',
        'Each tax can only be allocated once per bank transaction.',
    )
