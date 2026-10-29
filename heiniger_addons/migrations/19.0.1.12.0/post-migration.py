import json
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
_VIEW_TRANSLATIONS = {
    'Second early-payment option': 'Zweite Skontooption',
    '>if paid within<': '>bei Zahlung innerhalb von<',
    '>days<': '>Tagen<',
}


def _two_tier_terms(env):
    return env['account.payment.term'].search([
        ('early_discount', '=', True),
        ('discount_percentage', '=', 3.0),
        ('discount_days', '=', 10),
        ('early_pay_discount_computation', '=', 'included'),
        ('hgr_second_early_discount', '=', True),
        ('hgr_second_discount_percentage', '=', 2.0),
        ('hgr_second_discount_days', '=', 30),
        ('line_ids.nb_days', '=', 45),
    ])


def _repair_note_translations(env, terms):
    translations = {
        'en_US': f'<p>{_ENGLISH_NOTE}</p>',
        'en_GB': f'<p>{_ENGLISH_NOTE}</p>',
        'de_CH': f'<p>{_GERMAN_NOTE}</p>',
    }
    env.cr.execute(
        """
        UPDATE account_payment_term
           SET note = COALESCE(note, '{}'::jsonb) || %s::jsonb
         WHERE id = ANY(%s)
        """,
        [json.dumps(translations), terms.ids],
    )
    env.cr.execute(
        """
        SELECT id, note->>'en_US', note->>'en_GB', note->>'de_CH'
          FROM account_payment_term
         WHERE id = ANY(%s)
        """,
        [terms.ids],
    )
    invalid = [
        term_id
        for term_id, en_us, en_gb, de_ch in env.cr.fetchall()
        if en_us != translations['en_US']
        or en_gb != translations['en_GB']
        or de_ch != translations['de_CH']
    ]
    if invalid:
        raise RuntimeError(
            f'Payment-term note translation repair failed for term(s) {invalid}'
        )
    terms.invalidate_recordset(['note'])


def _repair_view_translations(env):
    view = env.ref('heiniger_addons.hgr_account_payment_term_form_two_discounts')
    english_arch = view.with_context(lang='en_US').arch_db
    german_arch = english_arch
    for source, translation in _VIEW_TRANSLATIONS.items():
        german_arch = german_arch.replace(source, translation)

    missing = [
        translation
        for translation in _VIEW_TRANSLATIONS.values()
        if translation.strip('><') not in german_arch
    ]
    if missing:
        raise RuntimeError(
            'Unable to build Swiss-German payment-term view translation: '
            + ', '.join(missing)
        )

    env.cr.execute(
        """
        UPDATE ir_ui_view
           SET arch_db = COALESCE(arch_db, '{}'::jsonb) || %s::jsonb
         WHERE id = %s
        """,
        [json.dumps({'de_CH': german_arch}), view.id],
    )
    view.invalidate_recordset(['arch_db'])

    env.cr.execute(
        "SELECT arch_db->>'de_CH' FROM ir_ui_view WHERE id = %s",
        [view.id],
    )
    stored_arch = env.cr.fetchone()[0] or ''
    missing = [
        translation
        for translation in _VIEW_TRANSLATIONS.values()
        if translation.strip('><') not in stored_arch
    ]
    if missing:
        raise RuntimeError(
            'Swiss-German payment-term view translation repair failed: '
            + ', '.join(missing)
        )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    terms = _two_tier_terms(env)
    if not terms:
        raise RuntimeError('No configured two-tier payment term was found')

    _repair_note_translations(env, terms)
    _repair_view_translations(env)
    _logger.info(
        'Validated English and Swiss-German payment-term translations for %s',
        terms.ids,
    )
