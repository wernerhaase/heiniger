"""Restricted ONLYOFFICE sessions for quotation-owned PDFs."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import secrets
from urllib.parse import urlsplit

import jwt

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools.pdf import PdfReader

MAX_PDF_BYTES = 30 * 1024 * 1024


def validate_pdf(data):
    if not data or len(data) > MAX_PDF_BYTES or not data.startswith(b'%PDF-'):
        raise UserError(_('Upload a valid PDF smaller than 30 MB.'))
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted or not len(reader.pages):
            raise ValueError('encrypted or empty')
    except Exception as exc:
        raise UserError(_('The editor did not return a readable, unencrypted PDF. The original is unchanged.')) from exc


def service_url(value):
    value = (value or '').strip().rstrip('/')
    parts = urlsplit(value)
    if (parts.scheme not in ('https', 'http') or not parts.hostname
            or parts.username or parts.password or parts.query or parts.fragment):
        raise UserError(_('Enter a valid HTTP or HTTPS service address without a password or query string.'))
    return value


class PdfEditorConnection(models.Model):
    _name = 'hgr.pdf.editor.connection'
    _description = 'PDF editor connection'

    name = fields.Char(required=True, default='ONLYOFFICE')
    active = fields.Boolean(default=True, help='Archive to disable PDF editing. Save open documents before archiving.')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    editor_url = fields.Char(string='ONLYOFFICE service address', required=True)
    jwt_secret = fields.Char(string='Connection secret (JWT)', required=True, copy=False, groups='base.group_system')
    odoo_url = fields.Char(string='Odoo address', required=True,
                          help='The address of this Odoo database, reachable by ONLYOFFICE. Use the staging address on staging and the production address on production.')
    account_email = fields.Char(string='Trial/account email')
    trial_end_date = fields.Date(string='Trial end date')

    _active_company_unique = models.UniqueIndex('(company_id) WHERE active IS TRUE',
        'Only one PDF editor connection can be active per company. Archive the existing connection first.')

    @api.constrains('editor_url', 'odoo_url')
    def _check_urls(self):
        for record in self:
            service_url(record.editor_url)
            service_url(record.odoo_url)

    def _configuration(self):
        self.ensure_one()
        if not self.active:
            raise UserError(_('PDF editing is disabled because its connection is archived.'))
        return service_url(self.editor_url), self.jwt_secret, service_url(self.odoo_url)

    @api.model
    def _for_company(self, company):
        connection = self.sudo().search([('company_id', '=', company.id), ('active', '=', True)], limit=1)
        if not connection:
            raise UserError(_('PDF editing is disabled. An administrator can configure it under Settings → PDF Editing → Manage connections.'))
        return connection


class Attachment(models.Model):
    _inherit = 'ir.attachment'

    hgr_pdf_backup_of_id = fields.Many2one('ir.attachment', copy=False, index=True, ondelete='cascade')

    def _hgr_pdf_order(self):
        self.ensure_one()
        if self.env.user.share or not self.env.user.active:
            raise AccessError(_('Only internal users may edit quotation attachments.'))
        self.check_access('write')
        if self.res_model == 'sale.order':
            order = self.env['sale.order'].browse(self.res_id).exists()
        elif self.res_model == 'sale.order.line':
            line = self.env['sale.order.line'].browse(self.res_id).exists()
            line.check_access('write')
            order = line.order_id
        else:
            order = self.env['sale.order']
        if not order or self.hgr_pdf_backup_of_id or self.res_field:
            raise AccessError(_('Only PDF attachments belonging to a quotation or sales order can be edited here.'))
        order.check_access('write')
        if self.type != 'binary' or self.mimetype != 'application/pdf':
            raise UserError(_('Select a PDF attachment.'))
        return order

    def hgr_pdf_edit_available(self):
        try:
            order = self._hgr_pdf_order()
            self.env['hgr.pdf.editor.connection']._for_company(order.company_id)._configuration()
            return True
        except (AccessError, UserError):
            return False

    def action_hgr_edit_pdf(self):
        order = self._hgr_pdf_order()
        session_model = self.env['hgr.pdf.editor.session']
        connection = self.env['hgr.pdf.editor.connection']._for_company(order.company_id)
        connection._configuration()
        target = self
        if self.res_model == 'sale.order.line':
            order._hgr_sync_note_pdfs()
            target = self.search([
                ('res_model', '=', 'sale.order'), ('res_id', '=', order.id),
                ('hgr_note_source_id', '=', self.id),
            ], limit=1)
            if not target:
                raise UserError(_('Save the PDF link in the quotation first, then open it again.'))
        target._hgr_pdf_order()
        validate_pdf(target.raw)
        # No user-facing ACL on sessions: only this checked factory may create them.
        session = session_model.sudo().create({
            'attachment_id': target.id,
            'connection_id': connection.id,
            'user_id': self.env.user.id,
            'company_id': order.company_id.id,
            'checksum': target.checksum,
        })
        return {'type': 'ir.actions.act_url', 'target': 'new',
                'url': '/heiniger/pdf/edit/' + session.key}


class PdfEditorSession(models.Model):
    _name = 'hgr.pdf.editor.session'
    _description = 'PDF editing session'

    key = fields.Char(required=True, default=lambda self: secrets.token_urlsafe(32), index=True, copy=False)
    connection_id = fields.Many2one('hgr.pdf.editor.connection', ondelete='restrict')
    attachment_id = fields.Many2one('ir.attachment', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True)
    checksum = fields.Char(required=True)
    expires = fields.Datetime(required=True, default=lambda self: fields.Datetime.now() + timedelta(hours=24))
    closed = fields.Boolean()
    saved_at = fields.Datetime()

    _key_unique = models.Constraint('UNIQUE(key)', 'Editing session identifiers must be unique.')

    def _configuration(self):
        self.ensure_one()
        if not self.connection_id or self.connection_id.company_id != self.company_id:
            raise UserError(_('This editing session has no valid connection. Reopen the PDF from the quotation.'))
        return self.connection_id._configuration()

    def _attachment_as_user(self):
        self.ensure_one()
        if self.closed or self.expires <= fields.Datetime.now():
            raise AccessError(_('This editing session has ended. Reopen the PDF from the quotation.'))
        self._configuration()
        user = self.user_id
        if not user.active or user.share or self.company_id not in user.company_ids:
            raise AccessError(_('You no longer have access to edit this PDF.'))
        attachment = self.attachment_id.with_user(user).with_context(allowed_company_ids=[self.company_id.id])
        attachment._hgr_pdf_order()
        return attachment

    def _editor_config(self):
        attachment = self._attachment_as_user()
        url, secret, base = self._configuration()
        expiry = int(self.expires.replace(tzinfo=timezone.utc).timestamp())
        download_token = jwt.encode({'session': self.key, 'purpose': 'download', 'exp': expiry}, secret, algorithm='HS256')
        config = {
            'documentType': 'pdf', 'type': 'desktop', 'width': '100%', 'height': '100%',
            'document': {
                'fileType': 'pdf', 'key': self.key, 'title': attachment.name,
                'url': base + '/heiniger/pdf/content/' + self.key + '?token=' + download_token,
                'permissions': {'edit': True, 'comment': True, 'download': True, 'print': True},
            },
            'editorConfig': {
                'mode': 'edit', 'lang': (self.user_id.lang or 'en_US').replace('_', '-'),
                'callbackUrl': base + '/heiniger/pdf/callback/' + self.key,
                'user': {'id': str(self.user_id.id), 'name': self.user_id.name},
                'customization': {'forcesave': True},
            },
        }
        config['token'] = jwt.encode(config, secret, algorithm='HS256')
        return url, config

    def _save_pdf(self, data):
        """Keep the attachment ID stable so note links and report printing agree."""
        validate_pdf(data)
        self.env.cr.execute('SELECT id FROM hgr_pdf_editor_session WHERE id = %s FOR UPDATE', [self.id])
        self.invalidate_recordset()
        attachment = self._attachment_as_user()
        self.env.cr.execute('SELECT id FROM ir_attachment WHERE id = %s FOR UPDATE', [attachment.id])
        attachment.invalidate_recordset()
        if attachment.checksum != self.checksum:
            raise UserError(_('This PDF changed while you were editing. Download your edited copy before reopening the current attachment.'))
        if attachment.raw == data:
            return
        stamp = fields.Datetime.now().strftime('%Y%m%d-%H%M%S')
        attachment.copy({
            'name': '%s - backup %s.pdf' % (attachment.name.rsplit('.', 1)[0], stamp),
            'res_model': 'ir.attachment', 'res_id': attachment.id,
            'hgr_pdf_backup_of_id': attachment.id,
            'hgr_note_source_id': False, 'hgr_note_original_name': False,
            'public': False, 'access_token': False,
        })
        attachment.write({'raw': data, 'mimetype': 'application/pdf'})
        self.write({'checksum': attachment.checksum, 'saved_at': datetime.utcnow()})
