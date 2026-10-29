import logging
from pathlib import Path

from odoo import Command, SUPERUSER_ID, api

from odoo.addons.heiniger_addons.tools.repair_languages import repair


_logger = logging.getLogger(__name__)

_XML_ID = 'payment_term_two_tier_3_2_45'
_LEGACY_NAMES = {
    '3/30 Netto',
    '3% 10 Tage / 2% 30 Tage / 45 Tage Netto',
    '3% 10 days / 2% 30 days / net 45 days',
}


def _matching_terms(env):
    terms = env['account.payment.term']
    for language in (False, 'en_US', 'en_GB', 'de_CH'):
        records = env['account.payment.term'].with_context(lang=language).search([])
        terms |= records.filtered(lambda term: (term.name or '').strip() in _LEGACY_NAMES)
    return terms


def _configure_two_tier_payment_term(env):
    term = env.ref(f'heiniger_addons.{_XML_ID}', raise_if_not_found=False)
    terms = _matching_terms(env)
    if term:
        terms |= term

    values = {
        'early_discount': True,
        'discount_percentage': 3.0,
        'discount_days': 10,
        # Included discounts proportionally reduce the tax, including cash-basis VAT.
        'early_pay_discount_computation': 'included',
        'hgr_second_early_discount': True,
        'hgr_second_discount_percentage': 2.0,
        'hgr_second_discount_days': 30,
        'line_ids': [
            Command.clear(),
            Command.create({
                'value': 'percent',
                'value_amount': 100.0,
                'nb_days': 45,
            }),
        ],
    }

    if not terms:
        terms = env['account.payment.term'].create({
            'name': '3% 10 days / 2% 30 days / net 45 days',
            'company_id': env.company.id,
            **values,
        })
    else:
        terms.write(values)

    terms.with_context(lang='en_US').write({
        'name': '3% 10 days / 2% 30 days / net 45 days',
    })
    terms.with_context(lang='en_GB').write({
        'name': '3% 10 days / 2% 30 days / net 45 days',
    })
    terms.with_context(lang='de_CH').write({
        'name': '3% 10 Tage / 2% 30 Tage / 45 Tage Netto',
    })

    if not term:
        env['ir.model.data'].create({
            'module': 'heiniger_addons',
            'name': _XML_ID,
            'model': 'account.payment.term',
            'res_id': terms[0].id,
            'noupdate': True,
        })

    _logger.info('Configured two-tier payment terms: %s', terms.ids)
    return terms


def _validate_post_upgrade(env, terms):
    errors = []

    for term in terms:
        line = term.line_ids
        if not (
            term.early_discount
            and term.discount_percentage == 3.0
            and term.discount_days == 10
            and term.early_pay_discount_computation == 'included'
            and term.hgr_second_early_discount
            and term.hgr_second_discount_percentage == 2.0
            and term.hgr_second_discount_days == 30
            and len(line) == 1
            and line.value == 'percent'
            and line.value_amount == 100.0
            and line.nb_days == 45
        ):
            errors.append(f'payment term {term.id} is not configured as 3/10, 2/30, net 45')

    unit = env.ref('uom.product_uom_unit')
    if unit.with_context(lang='de_CH').name != 'Stk.':
        errors.append('the standard unit is not Stk. in Swiss German')

    legacy_reports = env['ir.actions.report'].search_count([
        ('report_name', 'in', [
            'sale.report_saleorder_copy_2',
            'account.report_invoice_with_payments_copy_1',
            'heiniger_addons.invoice_with_payments',
        ]),
    ])
    if legacy_reports:
        errors.append(f'{legacy_reports} legacy report binding(s) remain')

    if errors:
        raise RuntimeError('Heiniger post-upgrade validation failed: ' + '; '.join(errors))

    _logger.info(
        'Heiniger post-upgrade validation passed for payment terms %s, UoM and reports',
        terms.ids,
    )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    persistent_root = Path('/home/odoo/data')
    backup_root = (
        persistent_root / 'hgr-migration-backups' / 'languages'
        if persistent_root.is_dir()
        else Path('/tmp/hgr-migration-backups/languages')
    )
    result = repair(
        env,
        expected_db=cr.dbname,
        backup_dir=str(backup_root),
    )
    terms = _configure_two_tier_payment_term(env)
    _validate_post_upgrade(env, terms)
    _logger.info('Heiniger post-upgrade repair completed: %s', result)
