# Local-tested language and legacy-report repair

Upgrade `heiniger_addons` to 19.0.1.3.0 before this cleanup. This deliberately does
not run automatically during deployment. Run it in an Odoo shell for the intended
database only, after verifying the deployed revision and retaining a database backup.

```python
from odoo.addons.heiniger_addons.tools.repair_languages import repair
result = repair(env, expected_db='THE_VERIFIED_DATABASE_NAME',
                backup_dir='/home/odoo/data/hgr-migration-backups/languages')
print(result)
env.cr.commit()
```

The expected database name is mandatory. On failure, roll back the transaction.
The tool backs up original metadata rows before writes and is idempotent. It changes
Studio view labels and custom-field labels, preserving Swiss German translations;
it corrects tax/unit display names without changing tax rates, unit factors or
business records. Unit English names follow existing Swiss German meanings.

The two existing print-menu actions are rebound to the current module/standard reports:
- Quotation / Order without price: current sale layout, quantities and rich text,
  without generated financial columns, section amounts or totals. Free-text notes
  are preserved, even if an author has typed a price into them.
- Invoices with Advance: current standard invoice with payment information,
  computed taxes and residual amounts. No hardcoded tax rate or obsolete totals API.

Old copied templates are retained for recovery but these actions no longer use them.
The German website company description and customer-entered text are not translated.

Verify CRM/Sales form, list and search views in English and Swiss German; render
standard, pro-forma, price-free, invoice/payment and work reports for customers in
both languages. Confirm original totals, payment balances and formatted descriptions.
Local evidence is stored outside the repository under upgrade-diagnostics/2026-09-30.
The local restored filestore has missing logo files; check branding on UAT.

## PDF attachments from notes (19.0.1.4.0)

Upgrade `heiniger_addons` to add **Print with attachments** to sale orders and
customer invoices. The default is off; invoice creation inherits the sale order's
selection. Standard sale, price-free sale and invoice PDF reports honor it.
Uploaded PDFs linked in line descriptions or document Notes/Terms are appended
in their authored order, once per attachment, after the complete formal report
(including Swiss payment pages). Mixed batch printing keeps each document's
attachments directly behind that document. Core cached invoice PDFs remain
unmodified. Downloading an already-generated legal invoice through other routes
is not the same action as printing the report.

Local `/web/content/<id>` links from Odoo's Notes editor are supported. External
website PDFs must first be uploaded. Invalid or encrypted PDFs produce a named
error when included. Existing attachment read permissions are enforced.

Saving notes exposes line/source PDFs as private parent-document chatter copies,
without moving the original attachment. The document's chatter copy is used for
printing once present. Removing a link removes it from subsequent appended
printouts; chatter files remain as document history. Chatter-only files that are
not linked in Notes are not automatically included.

For existing notes, run `records._hgr_sync_note_pdfs()` as an authorized internal
user. Restored databases must have their original filestore: missing source
binaries cannot be recovered by this feature.

Quotation and sales-order Notes PDFs are automatically named `Order number – Title.pdf`.
The title comes from the nearest preceding text block within the same note, falling
back to the original filename. Repeated titles receive numbered suffixes. Saving
notes or changing the order number refreshes names. Original filenames are retained
in `hgr_note_original_name` to prevent repeated prefixes. Notes point to the order's
own chatter copy, so opening and printing use the same file; shared source files
are not renamed. Existing notes are updated on their next save. Missing filestore
binaries are skipped. This naming rule does not rename invoice or unrelated uploads.

Portal quotation/order PDF links open a separate preview tab using Odoo's bundled
PDF.js viewer, with an explicit Download button. No automatic download is triggered.
The preview and binary routes validate normal order access or the order's portal
token and restrict files to PDFs currently referenced in that order's notes. They
serve the working chatter copy and use private/no-store responses. Unrelated IDs,
invalid tokens, and missing binaries return 404. This does not install or launch a
desktop PDF editor, and does not change invoice portal pages.
