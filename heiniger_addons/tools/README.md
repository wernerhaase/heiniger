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
