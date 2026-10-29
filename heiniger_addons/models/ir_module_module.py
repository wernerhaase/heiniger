"""Repair untranslated custom-field metadata during normal translation loading."""
import re

import polib

from odoo import models
from odoo.tools import file_path


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def _update_translations(self, filter_lang=None, overwrite=False):
        result = super()._update_translations(filter_lang=filter_lang, overwrite=overwrite)
        self._hgr_fill_field_translations(filter_lang)
        return result

    def _hgr_fill_field_translations(self, filter_lang=None):
        """Use shipped PO labels/help only for missing or English fallback values.

        A different existing translation may be customer wording; leave it alone.
        Restrict both the catalog and its XML IDs to our two custom modules.
        """
        languages = self.env['res.lang'].get_installed()
        requested = [filter_lang] if isinstance(filter_lang, str) else filter_lang
        languages = [code for code, _ in languages if code != 'en_US' and (not requested or code in requested)]
        for module in self.filtered(lambda m: m.name in ('heiniger_addons', 'sale_order_html_description')
                                    and m.state in ('installed', 'to install', 'to upgrade')):
            for lang in languages:
                try:
                    path = file_path('%s/i18n/%s.po' % (module.name, lang))
                except FileNotFoundError:
                    continue
                for entry in polib.pofile(path):
                    if entry.obsolete or 'fuzzy' in entry.flags or not entry.msgstr:
                        continue
                    for occurrence, _line in entry.occurrences:
                        match = re.fullmatch(r'model:ir\.model\.fields,(field_description|help):([^ ]+)', occurrence)
                        if not match:
                            continue
                        column, xmlid = match.groups()
                        if not xmlid.startswith(module.name + '.'):
                            continue
                        field = self.env.ref(xmlid, raise_if_not_found=False)
                        if not field or field._name != 'ir.model.fields':
                            continue
                        field.flush_recordset([column])
                        # Raw JSON distinguishes a missing locale from Odoo's
                        # automatic fallback to its English source text.
                        self.env.cr.execute('SELECT ' + column + ' FROM ir_model_fields WHERE id=%s', [field.id])
                        values = self.env.cr.fetchone()[0] or {}
                        if values.get('en_US') != entry.msgid:
                            continue  # catalog source is stale
                        if values.get(lang) in (None, '', entry.msgid):
                            field.with_context(lang=lang).write({column: entry.msgstr})
