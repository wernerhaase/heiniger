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

    # Write each installed language through the normal translated-field ORM.
    # This is deliberately kept separate from the accounting validation below:
    # cosmetic translation metadata must never roll back corrected maturity
    # dates.  The XML labels themselves are translated by i18n/de_CH.po when
    # the module is loaded.
    installed_languages = {
        code for code, _name in env['res.lang'].get_installed()
    }
    note_translations = {
        'en_US': _ENGLISH_NOTE,
        'en_GB': _ENGLISH_NOTE,
        'de_CH': _GERMAN_NOTE,
    }
    for configured_term in terms:
        for language, note in note_translations.items():
            if language == 'en_US' or language in installed_languages:
                configured_term.with_context(lang=language).write({'note': note})

    _repair_existing_move_dates(env, terms)

    _logger.info(
        'Two-tier payment-term dates repaired and descriptions updated for %s',
        terms.ids,
    )
