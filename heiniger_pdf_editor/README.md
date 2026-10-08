# Heiniger PDF Editor

Status: Odoo integration implemented; the external ONLYOFFICE service is not yet
provisioned. Do not describe full text editing or OCR as tested until a real editor
has been connected and the acceptance checks below pass.

Adds **Edit PDF** to the existing Odoo attachment preview for internal users with
write access to the attachment and its quotation/sales order. The button appears
only after the editor connection is configured. Invoices and customer portal
visitors are outside this feature's scope.

The editor opens in a separate tab. Users can use ONLYOFFICE's PDF text editing,
text insertion, comments, highlights and drawing tools. Click Save and wait for
**Saved to Odoo**. The edited PDF replaces the working attachment with the same
ID, so quotation links and appended report printing continue using it. Reopen the
attachment preview to see its current contents.

Each distinct save preserves the previous PDF as a private `ir.attachment`
attached to the working attachment (`hgr_pdf_backup_of_id`). Backups do not appear
as extra quotation files or get printed as supplements. An administrator can find
these in Technical > Attachments using that field; a user-facing restore action is
not included. Two independently opened sessions cannot overwrite a newer saved
version: the second save is rejected and the user can download their edits.

## Deployment

The confirmed live site is `https://heiniger.odoo.com` on Odoo.sh. The repository
root `requirements.txt` includes the editor's Python dependency for Odoo.sh builds.
Deploy and install first on an Odoo.sh staging branch. The ONLYOFFICE service must
be hosted separately (a managed ONLYOFFICE Docs Cloud instance or a separate server).
No hosted subscription has been created and no live-site changes have been made.
Use the staging site's own hostname for its callbacks, not the production hostname.

1. Deploy this addon alongside `heiniger_addons` and install the Python requirement
   from `requirements.txt` in Odoo's runtime.
2. Install **Heiniger PDF Editor** in Odoo.
3. Provision a current ONLYOFFICE Docs server with PDF editing support. Preserve
   its standard licensing/branding and verify the chosen edition covers the use.
   The service needs to be reachable by users' browsers and Odoo; it must also
   reach Odoo to retrieve source PDFs and deliver save callbacks.
4. Open Settings > PDF Editing > Manage connections and create a connection.
   Enter the Odoo address for the current environment (staging or production),
   ONLYOFFICE service address, and connection
   secret (JWT) from the ONLYOFFICE account. The trial signup link is in this form.
   Account email and trial end date are optional references; do not enter your
   ONLYOFFICE login password. All ONLYOFFICE JWT secrets must match. Keep JWT
   enabled; production must use HTTPS. Only administrators can access connection
   records; the secret is never delivered to the browser. One connection can be
   active per company.
5. Odoo's hostname/database filter must select exactly the intended database for
   requests with no browser session. A multi-database local development server
   needs an exact `--db-filter` and dedicated port; `?db=` is not sufficient for
   callbacks in Odoo 19.
6. Reload the Odoo browser, open a quotation PDF, and click Edit PDF.

To disable editing, save open edits, then open the connection and choose
**Actions > Archive**. This hides Edit PDF on refreshed previews and blocks new
sessions and further saves/downloads through existing editor sessions. Existing
PDF attachments and backups remain intact. Filter connections by **Archived**
and choose **Unarchive** to enable editing again. Archiving does not cancel an
ONLYOFFICE subscription; manage billing separately with ONLYOFFICE.

The `deploy/compose.yaml` is a local evaluation recipe, not an automatic installer.
It requires an existing Docker-compatible runtime. Put `ONLYOFFICE_JWT_SECRET`
in a private `.env`, then run `docker compose up -d` from `deploy/`. No secret is
included in the repository. By default the editor is at `http://localhost:18080`.
For host-based Odoo, its callback address can be `http://host.docker.internal:PORT`.
Use an isolated Odoo database and synthetic test files for evaluation. For
production use HTTPS, review private-network access needs and pin a tested image
digest. Hosting and editor service installation are separate from this addon.

## Security and behavior

- Only binary PDFs owned by quotations/orders or their lines are accepted.
- Line-owned source files resolve to the order's working chatter copy.
- Normal Odoo write permissions are rechecked on every download and save;
  portal tokens cannot authorize editing.
- Editing sessions are private, signed, expire after 24 hours, and close on the
  editor's completion callback. The session model deliberately has no general ACL.
- Callbacks require ONLYOFFICE's HS256 signature and the exact session key.
  Browser-config and download tokens do not authorize writes.
- Edited files are fetched only from the configured service origin, with redirects
  disabled, bounded timeouts and a 30 MB size limit. Encryption, empty documents,
  malformed PDFs and non-PDF callback formats are rejected.
- Errors roll back the backup and file write together. The original is retained.
- Editor sessions and backups are retained; retention/cleanup policy can be set
  later. No background deletion is enabled.
- Scanned-image text is not made editable by this addon. OCR needs a separately
  configured and tested ONLYOFFICE OCR capability/provider. It is not silently
  sent to an external AI/OCR service.

## Acceptance checks before rollout

Use synthetic copies first, then a representative customer PDF in the approved
hosting environment. Change existing text, add text, highlight, draw and comment;
save and reopen the downloaded PDF in a second viewer. Check font/layout fidelity,
comment preservation and page count. Confirm the quotation's link, chatter preview
and Print with attachments all use the updated file. Verify the backup, read-only
users, expired sessions, failed callbacks, cancelled edits and concurrent sessions.
Do not edit an already signed document as though its signature could be preserved.

## Validation performed

Automated Odoo tests in the isolated `hgr_pdf_editor_test_oct8` database cover valid
PDF saves, stable IDs, original backups, duplicate saves, conflicts, invalid PDFs,
non-sales and public-user rejection, signed configuration, signed save callbacks,
rejection of invalid callback credentials, unexpected download hosts/redirects,
escaping of filenames in the editor page, administrator-only connection access,
and archive/unarchive behavior with original PDFs and backups retained. Actual ONLYOFFICE editing and OCR
have not been exercised because no editor service is configured.

References:
- https://api.onlyoffice.com/docs/docs-api/usage-api/callback-handler
- https://helpcenter.onlyoffice.com/docs/userguides/pdf_editor/EditPDF.aspx
- https://helpcenter.onlyoffice.com/docs/installation/docs-community-install-docker-arm64.aspx
