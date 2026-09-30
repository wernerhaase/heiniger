"""Explicit, repeatable Odoo-shell cleanup after upgrading heiniger_addons.

Call repair(env, expected_db, backup_dir). The caller owns commit/rollback.
Only UI metadata, tax/unit translations and legacy print bindings are changed.
Original rows are saved before writes. Customer descriptions are never changed.
"""
import gzip
import json
from pathlib import Path
from datetime import datetime, timezone
from lxml import etree

LABELS = {
 'Versicherung':'Insurance Company', 'Versicherungen/Aufträge':'Insurance / Orders',
 'Versicherung Policen Nr':'Policy No', 'Schadenexperte':'Claims Expert',
 'Schadenfall Nr':'Claim No', 'Schadenaufnahme Datum':'Claim Record Date',
 'Versicherungsfall/-& oder mehrere Aufträge (JA)':'Insurance Case / Multiple Orders',
 'Annahme-Datum':'Acceptance Date', 'Schadenmeldung':'Damage Notification',
 'Mit wem spreche ich?:':'Contact Person:', 'Wann passierte das Ereignis?:':'When Did the Incident Occur?',
 'Kurze Schadenbeschreibung:':'Brief Damage Description:',
 'Bereits Aufgeführet Arbeiten Dritter':'Work Already Performed by Third Parties',
 'Wer machte WAS?:':'Who Did What?', 'Schadenaufnahme':'Damage Assessment',
 'Aufnahme Protokoll:':'Assessment Record:', 'Auszuführende Arbeiten:':'Work to Be Performed:',
 'Benötigtes Material/Mitarbeiter':'Required Materials / Employees',
 'Anzahl Mitarbeiter':'Number of Employees', 'Voraussichtliche Std.':'Estimated Hours',
 '(zu bestellendes) Material:':'Materials to Order:', 'Betreff/Chance':'Subject / Opportunity',
 'Sachbearbeiter':'Case Officer', 'Objekt':'Object', 'Betreff':'Subject',
 'Schaden Fall Nr.':'Claim No', 'Schaden Experte':'Claims Expert', 'Marge':'Margin', 'Marge (%)':'Margin (%)',
 'Beschreibung':'Description', 'Anrufer:':'Caller:', 'Art des Schadens:':'Type of Damage:',
 'Aufnehmeprotokoll':'Assessment Record', 'Datum':'Date',
 'Erste Angabe bei Schadenmeldung:':'Initial Damage Notification:',
 'Erste Angaben bei Schadenmeldung:':'Initial Damage Notification:',
 'Erste Angaben bei Schadenmeldung':'Initial Damage Notification',
 'Produkt':'Product', 'Neue Zeilen':'New Lines', 'Sequenz':'Sequence',
 'New Mehrzeiliger Text':'New Multiline Text', 'Wann passiert':'When Did It Happen?',
 'War machte was?:':'Who Did What?',
 'Kunde:':'Customer:', 'Arbeitsauftrag/Stundenabrechnung':'Work Report / Hourly Billing',
 'Objekt:':'Object:', 'Arbeitsbeschreibung:':'Task Description:', 'Mitarbeiter:':'Employees:',
 'Restzahlung Netto':'Remaining Untaxed Amount', 'Restzahlung On':'Remaining Untaxed Amount',
 'Restzahlung inkl. MwSt 7,7% Gesamt':'Total Including Tax',
 'auf Rechnungsbetrag Netto':'on Untaxed Invoice Amount',
}

def repair(env, expected_db, backup_dir):
    assert env.cr.dbname == expected_db, 'Wrong target database'
    assert env.ref('heiniger_addons.saleorder_without_prices', raise_if_not_found=False), 'Upgrade module first'
    backup = Path(backup_dir) / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup.mkdir(parents=True, mode=0o700)
    tables = ['ir_ui_view', 'ir_model_fields', 'account_tax_group', 'uom_uom', 'ir_act_report_xml']
    for table in tables:
        env.cr.execute('SELECT row_to_json(t) FROM '+table+' t ORDER BY id')
        with gzip.open(backup/(table+'.json.gz'), 'wt', encoding='utf-8') as f:
            json.dump([r[0] for r in env.cr.fetchall()], f, ensure_ascii=False, default=str)
    german = {english: original for original, english in LABELS.items()}
    german.update({'Claims Expert':'Schadenexperte', 'Claim No':'Schadenfall Nr', 'Who Did What?':'Wer machte was?', 'Assessment Record:':'Aufnahmeprotokoll:', 'Work Already Performed by Third Parties':'Bereits ausgeführte Arbeiten Dritter'})
    counts = {'views':0, 'fields':0, 'tax_groups':0, 'units':0, 'reports':0}
    # Translate only literal labels, never XPath selectors or business values.
    views = env['ir.ui.view'].with_context(lang='en_US').search([('active','=',True)])
    for view in views:
        xid = view.get_external_id().get(view.id, '')
        if not (xid.startswith('studio_customization.') or view.key == 'sale.sale_order_portal_template'):
            continue
        root = etree.fromstring(view.arch_db.encode())
        changed = False
        for node in root.iter():
            if not isinstance(node.tag, str): continue
            for attr in ['string','help','placeholder','title']:
                if node.get(attr) in LABELS:
                    node.set(attr, LABELS[node.get(attr)]); changed = True
            if node.text and node.text.strip() in LABELS and (node.tag == 'attribute' and node.get('name') in ['string','help','placeholder','title'] or view.type == 'qweb'):
                node.text = LABELS[node.text.strip()]; changed = True
        if changed:
            view.write({'arch_db':etree.tostring(root, encoding='unicode')})
        # Architecture writes change structure in every language. Use Odoo's
        # translation API for translated terms instead of writing another arch.
        english_arch = etree.tostring(root, encoding='unicode')
        translations = {}
        for term in view._fields['arch_db'].get_trans_terms(english_arch):
            translated = german.get(term, term)
            if '<' in term:
                for en, de in german.items():
                    translated = translated.replace('>' + en + '<', '>' + de + '<')
            if translated != term:
                translations[term] = translated
        before = view.with_context(lang='de_CH').arch_db
        before_en = view.with_context(lang='en_GB').arch_db
        if translations:
            view.update_field_translations('arch_db', {'de_CH':translations, 'en_GB':{en:en for en in translations}})
        if changed or before != view.with_context(lang='de_CH').arch_db or before_en != view.with_context(lang='en_GB').arch_db:
            counts['views'] += 1
    for field in env['ir.model.fields'].with_context(lang='en_US').search([('state','=','manual')]):
        if field.field_description not in LABELS: continue
        de = field.with_context(lang='de_CH').field_description
        english = LABELS[field.field_description]
        field.write({'field_description':english})
        field.with_context(lang='en_GB').write({'field_description':english})
        field.with_context(lang='de_CH').write({'field_description':de})
        counts['fields'] += 1
    for group in env['account.tax.group'].with_context(lang='en_US').search([]):
        name = group.name
        if not name.startswith(('MwSt.', 'MWST', 'TVA')): continue
        english = name.replace('MwSt.', 'VAT').replace('MWST', 'VAT').replace('TVA', 'VAT').replace(',', '.')
        de = group.with_context(lang='de_CH').name
        group.write({'name':english})
        group.with_context(lang='en_GB').write({'name':english})
        group.with_context(lang='de_CH').write({'name':de.replace('TVA','MwSt.')})
        counts['tax_groups'] += 1
    # Standard Units must never display the unrelated lump-sum abbreviation.
    units = env.ref('uom.product_uom_unit')
    if units.with_context(lang='de_CH').name != 'Stk.':
        units.with_context(lang='de_CH').write({'name':'Stk.'}); counts['units'] += 1
    for unit in env['uom.uom'].with_context(lang='en_US').search([('name','in',['Std','Kartusche','Psch','PL'])]):
        de = unit.with_context(lang='de_CH').name
        english = {'Std':'Hours', 'Kartusche':'Cartridge', 'PL':'Lump sum', 'Psch':'Pieces' if de == 'Stk.' else 'Lump sum'}[unit.name]
        unit.write({'name':english})
        unit.with_context(lang='en_GB').write({'name':english})
        unit.with_context(lang='de_CH').write({'name':de})
        counts['units'] += 1
    replacements = {
        'sale.report_saleorder_copy_2':'heiniger_addons.saleorder_without_prices',
        'account.report_invoice_with_payments_copy_1':'account.report_invoice_with_payments',
        'heiniger_addons.invoice_with_payments':'account.report_invoice_with_payments',
    }
    for report in env['ir.actions.report'].search([('report_name','in',list(replacements))]):
        name = replacements[report.report_name]
        report.write({'report_name':name, 'report_file':name})
        counts['reports'] += 1
    (backup/'result.json').write_text(json.dumps(counts, indent=2))
    return {'backup':str(backup), 'changes':counts}
