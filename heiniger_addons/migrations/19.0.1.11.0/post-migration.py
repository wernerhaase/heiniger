import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)

_ENGLISH_NOTE = (
    'Payment terms: 3% discount within 10 days, 2% discount within 30 days, '
    'net within 45 days.'
)
_GERMAN_NOTE = (
    'Zahlungsbedingungen: 3% Skonto innert 10 Tagen, 2% Skonto innert 30 Tagen, '
    'netto innert 45 Tagen.'
)
_GERMAN_VIEW_TERMS = {
    'Second early-payment option': 'Zweite Skontooption',
    'if paid within': 'bei Zahlung innerhalb von',
    'days': 'Tagen',
}
_INVOICE_MOVE_TYPES = (
    'out_invoice', 'out_refund', 'out_receipt',
    'in_invoice', 'in_refund', 'in_receipt',
)


def _two_tier_terms(env):
    candidates = env['account.payment.term'].search([
        ('early_discount', '=', True),
        ('discount_percentage', '=', 3.0),
        ('discount_days', '=', 10),
        ('early_pay_discount_computation', '=', 'included'),
        ('hgr_second_early_discount', '=', True),
        ('hgr_second_discount_percentage', '=', 2.0),
        ('hgr_second_discount_days', '=', 30),
    ])
    return candidates.filtered(
        lambda candidate: len(candidate.line_ids) == 1
        and candidate.line_ids.value == 'percent'
        and candidate.line_ids.value_amount == 100.0
        and candidate.line_ids.nb_days == 45
    )


def _repair_existing_move_dates(env, terms):
    """Apply the upgraded 10/30/45-day definition to existing invoices.

    Updating an account.payment.term does not rewrite the maturity metadata on
    already-created moves. Only date metadata is changed here; posted journal
    amounts, reconciliations and discount balances remain untouched.
    """
    term_ids = tuple(terms.ids)
    if not term_ids:
        raise RuntimeError('No configured two-tier payment term was found')

    env.cr.execute(
        """
        UPDATE account_move AS move
           SET invoice_date_due = move.invoice_date + 45
         WHERE move.invoice_payment_term_id IN %s
           AND move.move_type IN %s
           AND move.invoice_date IS NOT NULL
           AND move.invoice_date_due IS DISTINCT FROM move.invoice_date + 45
        """,
        [term_ids, _INVOICE_MOVE_TYPES],
    )
    repaired_moves = env.cr.rowcount

    env.cr.execute(
        """
        UPDATE account_move_line AS line
           SET date_maturity = move.invoice_date + 45,
               discount_date = move.invoice_date + 10
          FROM account_move AS move
         WHERE line.move_id = move.id
           AND line.display_type = 'payment_term'
           AND move.invoice_payment_term_id IN %s
           AND move.move_type IN %s
           AND move.invoice_date IS NOT NULL
           AND (
               line.date_maturity IS DISTINCT FROM move.invoice_date + 45
               OR line.discount_date IS DISTINCT FROM move.invoice_date + 10
           )
        """,
        [term_ids, _INVOICE_MOVE_TYPES],
    )
    repaired_lines = env.cr.rowcount
    env['account.move'].invalidate_model(['invoice_date_due'])
    env['account.move.line'].invalidate_model(['date_maturity', 'discount_date'])

    env.cr.execute(
        """
        SELECT COUNT(*)
          FROM account_move AS move
         WHERE move.invoice_payment_term_id IN %s
           AND move.move_type IN %s
           AND move.invoice_date IS NOT NULL
           AND move.invoice_date_due IS DISTINCT FROM move.invoice_date + 45
        """,
        [term_ids, _INVOICE_MOVE_TYPES],
    )
    invalid_moves = env.cr.fetchone()[0]
    env.cr.execute(
        """
        SELECT COUNT(*)
          FROM account_move_line AS line
          JOIN account_move AS move ON move.id = line.move_id
         WHERE line.display_type = 'payment_term'
           AND move.invoice_payment_term_id IN %s
           AND move.move_type IN %s
           AND move.invoice_date IS NOT NULL
           AND (
               line.date_maturity IS DISTINCT FROM move.invoice_date + 45
               OR line.discount_date IS DISTINCT FROM move.invoice_date + 10
           )
        """,
        [term_ids, _INVOICE_MOVE_TYPES],
    )
    invalid_lines = env.cr.fetchone()[0]
    if invalid_moves or invalid_lines:
        raise RuntimeError(
            'Two-tier payment-term date repair failed: '
            f'{invalid_moves} move(s), {invalid_lines} payment line(s) remain inconsistent'
        )

    _logger.info(
        'Repaired two-tier dates on %s existing move(s) and %s payment line(s)',
        repaired_moves,
        repaired_lines,
    )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    term = env.ref('heiniger_addons.payment_term_two_tier_3_2_45')
    terms = _two_tier_terms(env) | term

    terms.with_context(lang='en_US').write({'note': _ENGLISH_NOTE})
    terms.with_context(lang='en_GB').write({'note': _ENGLISH_NOTE})
    terms.with_context(lang='de_CH').write({'note': _GERMAN_NOTE})
    _repair_existing_move_dates(env, terms)

    view = env.ref('heiniger_addons.hgr_account_payment_term_form_two_discounts')
    view.update_field_translations('arch_db', {'de_CH': _GERMAN_VIEW_TERMS})

    errors = []
    for configured_term in terms:
        if configured_term.with_context(lang='en_US').note != _ENGLISH_NOTE:
            errors.append(f'English invoice description was not updated on term {configured_term.id}')
        if configured_term.with_context(lang='de_CH').note != _GERMAN_NOTE:
            errors.append(
                f'Swiss-German invoice description was not updated on term {configured_term.id}'
            )
    german_arch = view.with_context(lang='de_CH').arch_db
    for translated in _GERMAN_VIEW_TERMS.values():
        if translated not in german_arch:
            errors.append(f'missing Swiss-German view translation: {translated}')
    if errors:
        raise RuntimeError('Payment-term presentation validation failed: ' + '; '.join(errors))

    _logger.info(
        'Two-tier payment-term dates, descriptions and Swiss-German labels validated for %s',
        terms.ids,
    )
