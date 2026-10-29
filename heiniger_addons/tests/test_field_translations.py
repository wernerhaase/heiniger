import json

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFieldTranslations(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env['res.lang']._activate_lang('de_CH')
        self.modules = self.env['ir.module.module'].search([
            ('name', 'in', ['heiniger_addons', 'sale_order_html_description'])])
        self.field = self.env.ref('heiniger_addons.field_sale_order__hgr_print_with_attachments')

    def set_values(self, field, values, column='field_description'):
        field.flush_recordset([column])
        self.env.cr.execute('UPDATE ir_model_fields SET ' + column + '=%s::jsonb WHERE id=%s',
                            [json.dumps(values), field.id])
        field.invalidate_recordset([column])

    def test_missing_fallback_and_idempotence(self):
        for value in (None, '', 'Print with attachments'):
            values = {'en_US': 'Print with attachments'}
            if value is not None:
                values['de_CH'] = value
            self.set_values(self.field, values)
            self.modules._hgr_fill_field_translations('de_CH')
            self.assertEqual(self.field.with_context(lang='de_CH').field_description, 'Mit Anhängen drucken')
            self.modules._hgr_fill_field_translations(['de_CH'])
            self.assertEqual(self.field.with_context(lang='de_CH').field_description, 'Mit Anhängen drucken')

    def test_custom_wording_and_stale_source_preserved(self):
        self.set_values(self.field, {'en_US': 'Print with attachments', 'de_CH': 'Kundenspezifische Bezeichnung'})
        self.modules._update_translations(filter_lang=['de_CH'])
        self.assertEqual(self.field.with_context(lang='de_CH').field_description, 'Kundenspezifische Bezeichnung')
        self.set_values(self.field, {'en_US': 'Changed source'})
        self.modules._hgr_fill_field_translations('de_CH')
        self.assertEqual(self.field.with_context(lang='de_CH').field_description, 'Changed source')

    def test_help_and_other_module(self):
        self.set_values(self.field, {'en_US': 'Append PDFs inserted in the document notes after the formal report, in note order.'}, 'help')
        other = self.env.ref('sale_order_html_description.field_sale_order_line__name')
        self.set_values(other, {'en_US': 'Description'})
        self.modules._hgr_fill_field_translations('de_CH')
        self.assertEqual(other.with_context(lang='de_CH').field_description, 'Beschreibung')
        self.assertIn('PDF', self.field.with_context(lang='de_CH').help)
        self.assertNotIn('Append', self.field.with_context(lang='de_CH').help)

    def test_language_filter(self):
        self.set_values(self.field, {'en_US': 'Print with attachments'})
        self.modules._hgr_fill_field_translations('fr_FR')
        self.assertEqual(self.field.with_context(lang='de_CH').field_description, 'Print with attachments')
