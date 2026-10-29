from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import format_date, formatLang


class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    hgr_second_early_discount = fields.Boolean(string='Second Early Discount')
    hgr_second_discount_percentage = fields.Float(
        string='Second Discount %',
        help='Lower cash discount available after the first discount deadline.',
        default=2.0,
    )
    hgr_second_discount_days = fields.Integer(
        string='Second Discount Days',
        help='Last day on which the second cash discount is available.',
        default=30,
    )

    @api.constrains(
        'early_discount', 'discount_percentage', 'discount_days',
        'hgr_second_early_discount', 'hgr_second_discount_percentage',
        'hgr_second_discount_days', 'line_ids',
    )
    def _check_hgr_second_early_discount(self):
        for term in self.filtered('hgr_second_early_discount'):
            if not term.early_discount:
                raise ValidationError(_('Enable the first early discount before adding a second discount.'))
            if len(term.line_ids) != 1:
                raise ValidationError(_('Two early discounts require one 100% due line.'))
            if not 0 < term.hgr_second_discount_percentage < term.discount_percentage:
                raise ValidationError(
                    _('The second discount must be positive and lower than the first discount.')
                )
            if term.hgr_second_discount_days <= term.discount_days:
                raise ValidationError(
                    _('The second discount deadline must be later than the first discount deadline.')
                )

    def _hgr_discount_tier(self, invoice_date, reference_date):
        """Return the applicable (percentage, deadline, tier) for a payment date."""
        self.ensure_one()
        invoice_date = fields.Date.to_date(invoice_date)
        reference_date = fields.Date.to_date(reference_date)
        if not self.early_discount or not invoice_date or not reference_date:
            return False
        first_date = invoice_date + relativedelta(days=self.discount_days)
        if reference_date <= first_date:
            return self.discount_percentage, first_date, 'first'
        if self.hgr_second_early_discount:
            second_date = invoice_date + relativedelta(days=self.hgr_second_discount_days)
            if reference_date <= second_date:
                return self.hgr_second_discount_percentage, second_date, 'second'
        return False

    def _hgr_amount_due_for_percentage(
        self, total_amount, untaxed_amount, percentage, currency, cash_rounding=False,
    ):
        self.ensure_one()
        if self.early_pay_discount_computation in ('excluded', 'mixed'):
            discount = untaxed_amount * percentage / 100.0
        else:
            discount = total_amount * percentage / 100.0
        amount_due = currency.round(total_amount - discount)
        if cash_rounding:
            amount_due += cash_rounding.compute_difference(currency, amount_due)
        return currency.round(amount_due)

    def _hgr_discount_options(
        self, invoice_date, total_amount, untaxed_amount, currency, cash_rounding=False,
    ):
        self.ensure_one()
        invoice_date = fields.Date.to_date(invoice_date)
        if not self.early_discount or not invoice_date:
            return []
        options = [{
            'tier': 'first',
            'percentage': self.discount_percentage,
            'date': invoice_date + relativedelta(days=self.discount_days),
            'date_formatted': format_date(
                self.env, invoice_date + relativedelta(days=self.discount_days)
            ),
            'amount': self._hgr_amount_due_for_percentage(
                total_amount, untaxed_amount, self.discount_percentage, currency, cash_rounding
            ),
        }]
        if self.hgr_second_early_discount:
            options.append({
                'tier': 'second',
                'percentage': self.hgr_second_discount_percentage,
                'date': invoice_date + relativedelta(days=self.hgr_second_discount_days),
                'date_formatted': format_date(
                    self.env, invoice_date + relativedelta(days=self.hgr_second_discount_days)
                ),
                'amount': self._hgr_amount_due_for_percentage(
                    total_amount, untaxed_amount, self.hgr_second_discount_percentage,
                    currency, cash_rounding
                ),
            })
        return options

    def _hgr_format_discount_option(self, option, currency):
        self.ensure_one()
        return _(
            '%(percentage)s%% discount: pay %(amount)s by %(date)s',
            percentage=option['percentage'],
            amount=formatLang(self.env, option['amount'], currency_obj=currency),
            date=option['date_formatted'],
        )

    @api.depends(
        'currency_id', 'example_amount', 'example_date', 'line_ids.value',
        'line_ids.value_amount', 'line_ids.nb_days', 'early_discount',
        'discount_percentage', 'discount_days', 'hgr_second_early_discount',
        'hgr_second_discount_percentage', 'hgr_second_discount_days',
    )
    def _compute_example_preview(self):
        super()._compute_example_preview()
        for term in self.filtered(lambda record: record.early_discount and record.hgr_second_early_discount):
            options = term._hgr_discount_options(
                term.example_date or fields.Date.context_today(term),
                term.example_amount,
                term.example_amount,
                term.currency_id,
            )
            term.example_preview_discount = '<br/>'.join(
                _(
                    '%(percentage)s%% discount: <b>%(amount)s</b> if paid by <b>%(date)s</b>',
                    percentage=option['percentage'],
                    amount=formatLang(self.env, option['amount'], currency_obj=term.currency_id),
                    date=format_date(self.env, option['date']),
                )
                for option in options
            )


class AccountMove(models.Model):
    _inherit = 'account.move'

    hgr_payment_discount_summary = fields.Html(
        string='Early-payment options',
        compute='_compute_hgr_payment_discount_summary',
        sanitize=True,
    )

    @api.depends(
        'invoice_date', 'invoice_date_due', 'amount_total', 'amount_untaxed', 'currency_id',
        'invoice_payment_term_id.early_discount',
        'invoice_payment_term_id.discount_percentage',
        'invoice_payment_term_id.discount_days',
        'invoice_payment_term_id.hgr_second_early_discount',
        'invoice_payment_term_id.hgr_second_discount_percentage',
        'invoice_payment_term_id.hgr_second_discount_days',
    )
    def _compute_hgr_payment_discount_summary(self):
        for move in self:
            term = move.invoice_payment_term_id
            options = term._hgr_discount_options(
                move.invoice_date, move.amount_total, move.amount_untaxed,
                move.currency_id, move.invoice_cash_rounding_id,
            ) if term else []
            if not options:
                move.hgr_payment_discount_summary = False
                continue
            rows = []
            for option in options:
                rows.append(_(
                    '<div><b>%(percentage)s%% discount</b>: pay %(amount)s by %(date)s</div>',
                    percentage=option['percentage'],
                    amount=formatLang(self.env, option['amount'], currency_obj=move.currency_id),
                    date=format_date(self.env, option['date']),
                ))
            if move.invoice_date_due:
                rows.append(_(
                    '<div><b>Net amount</b>: pay %(amount)s by %(date)s</div>',
                    amount=formatLang(self.env, move.amount_total, currency_obj=move.currency_id),
                    date=format_date(self.env, move.invoice_date_due),
                ))
            move.hgr_payment_discount_summary = ''.join(rows)

    def _hgr_format_net_due(self):
        self.ensure_one()
        return _(
            'Net amount: pay %(amount)s by %(date)s',
            amount=formatLang(self.env, self.amount_total, currency_obj=self.currency_id),
            date=format_date(self.env, self.invoice_date_due),
        )

    def _hgr_second_discount_ratio(self, payment_line):
        self.ensure_one()
        term = self.invoice_payment_term_id
        options = term._hgr_discount_options(
            self.invoice_date, self.amount_total, self.amount_untaxed,
            self.currency_id, self.invoice_cash_rounding_id,
        )
        if len(options) < 2:
            return False
        signed_second_due = -self.direction_sign * options[1]['amount']
        first_discount = payment_line.amount_currency - payment_line.discount_amount_currency
        second_discount = payment_line.amount_currency - signed_second_due
        return second_discount / first_discount if first_discount else False

    def _is_eligible_for_early_payment_discount(self, currency, reference_date):
        if super()._is_eligible_for_early_payment_discount(currency, reference_date):
            return True
        self.ensure_one()
        term = self.invoice_payment_term_id
        payment_lines = self.line_ids.filtered(lambda line: line.display_type == 'payment_term')
        return bool(
            term.hgr_second_early_discount
            and self.currency_id == currency
            and self.move_type in self._early_payment_discount_move_types()
            and term._hgr_discount_tier(self.invoice_date, reference_date)
            and not (payment_lines.sudo().matched_debit_ids + payment_lines.sudo().matched_credit_ids)
        )

    def _get_invoice_counterpart_amls_for_early_payment_discount(self, aml_values_list, open_balance):
        result = super()._get_invoice_counterpart_amls_for_early_payment_discount(
            aml_values_list, open_balance
        )
        custom_lines = [
            values['aml'] for values in aml_values_list
            if values['aml'].move_id.invoice_payment_term_id.hgr_second_early_discount
        ]
        if not custom_lines or len(custom_lines) != len(aml_values_list):
            return result

        ratios = {line.move_id._hgr_second_discount_ratio(line) for line in custom_lines}
        ratios.discard(False)
        if len(ratios) != 1:
            return result
        ratio = ratios.pop()
        company_currency = custom_lines[0].company_currency_id
        second_discount = company_currency.round(sum(
            values['balance']
            * ((values['aml'].balance - values['aml'].discount_balance) / values['aml'].balance)
            * ratio
            for values in aml_values_list
            if values['aml'].balance
        ))
        if company_currency.compare_amounts(abs(open_balance), abs(second_discount)) != 0:
            return result

        for key in ('term_lines', 'tax_lines', 'base_lines'):
            for values in result.get(key, []):
                currency = self.env['res.currency'].browse(values.get('currency_id'))
                values['amount_currency'] = currency.round(values['amount_currency'] * ratio)
                values['balance'] = company_currency.round(values['balance'] * ratio)
        scaled_balance = sum(
            values['balance']
            for key in ('term_lines', 'tax_lines', 'base_lines')
            for values in result.get(key, [])
        )
        exchange_balance = company_currency.round(open_balance - scaled_balance)
        if company_currency.is_zero(exchange_balance):
            result['exchange_lines'] = []
        elif result.get('exchange_lines'):
            result['exchange_lines'][0]['balance'] = exchange_balance
            result['exchange_lines'] = result['exchange_lines'][:1]
        return result


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_installments_data(self, payment_currency=None, payment_date=None, next_payment_date=None):
        installments = super()._get_installments_data(
            payment_currency=payment_currency,
            payment_date=payment_date,
            next_payment_date=next_payment_date,
        )
        payment_date = fields.Date.to_date(payment_date or fields.Date.context_today(self))
        for installment in installments:
            line = installment['line']
            term = line.move_id.invoice_payment_term_id
            if not term:
                continue
            tier = term._hgr_discount_tier(line.move_id.invoice_date, payment_date)
            if installment['type'] != 'early_payment_discount' or not tier or tier[2] != 'second':
                continue
            ratio = line.move_id._hgr_second_discount_ratio(line)
            currency = line.currency_id
            company_currency = line.company_currency_id
            discount_currency = currency.round((line.amount_currency - line.discount_amount_currency) * ratio)
            discount_balance = company_currency.round((line.balance - line.discount_balance) * ratio)
            discounted_currency = line.amount_currency - discount_currency
            discounted_balance = line.balance - discount_balance
            sign = line.move_id.direction_sign
            installment.update({
                'amount_residual_currency': discounted_currency,
                'amount_residual': discounted_balance,
                'amount_residual_currency_unsigned': -sign * discounted_currency,
                'amount_residual_unsigned': -sign * discounted_balance,
                'discount_amount_currency': discount_currency,
                'discount_amount': discount_balance,
                'hgr_discount_tier': 'second',
            })
        return installments
