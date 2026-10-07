"""PDFs explicitly embedded in document notes, in their authored order."""
import re
from urllib.parse import urlsplit, urlencode
from markupsafe import Markup, escape

from lxml import html

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html_sanitize


def note_attachment_ids(values, base_url):
    ids = []
    host = urlsplit(base_url or '').netloc
    for value in values:
        if not value:
            continue
        root = html.fragment_fromstring(str(value), create_parent='div')
        for node in root.iter():
            # Native editor file boxes also contain a link. Use the link so an
            # external URL cannot accidentally resolve to a local numeric ID.
            url = node.get('href') or node.get('src') or ''
            parsed = urlsplit(url)
            if parsed.netloc and parsed.netloc != host:
                continue
            if parsed.scheme and parsed.scheme not in ('http', 'https'):
                continue
            match = re.match(r'^/web/content/(?:ir\.attachment/)?(\d+)(?:[-/?]|$)', parsed.path)
            if match and int(match[1]) not in ids:
                ids.append(int(match[1]))
    return ids


class Attachment(models.Model):
    _inherit = 'ir.attachment'

    hgr_note_source_id = fields.Many2one('ir.attachment', copy=False, index=True, ondelete='set null')
    hgr_note_original_name = fields.Char(copy=True)


class NotePdfMixin(models.AbstractModel):
    _name = 'hgr.note.pdf.mixin'
    _description = 'PDF attachments embedded in notes'

    hgr_print_with_attachments = fields.Boolean(
        string='Print with attachments', default=False,
        help='Append PDFs inserted in the document notes after the formal report, in note order.')

    def _hgr_note_html_values(self):
        self.ensure_one()
        if self._name == 'sale.order':
            return [line.name for line in self.order_line.sorted('sequence')] + [self.note]
        return [getattr(line, 'hgr_html_description', False) or line.name
                for line in self.invoice_line_ids.sorted('sequence')] + [self.narration]

    def _hgr_note_pdfs(self, strict=False):
        self.ensure_one()
        self.check_access('read')
        ids = note_attachment_ids(self._hgr_note_html_values(), self.get_base_url())
        result = self.env['ir.attachment']
        for aid in ids:
            attachment = self.env['ir.attachment'].browse(aid).exists()
            if not attachment:
                if strict:
                    raise UserError(_('An attachment referenced in the notes is missing (ID %s). Remove or replace its link before printing with attachments.', aid))
                continue
            attachment.check_access('read')
            if attachment.mimetype == 'application/pdf' or attachment.name.lower().endswith('.pdf'):
                if attachment.type != 'binary':
                    if strict:
                        raise UserError(_('Upload "%s" as a PDF file before printing with attachments.', attachment.name))
                    continue
                # Once a document owns a chatter copy, that is its working
                # attachment (including any later replacement of its PDF).
                local_copy = self.env['ir.attachment'].search([
                    ('res_model', '=', self._name), ('res_id', '=', self.id),
                    ('hgr_note_source_id', '=', attachment.id)], limit=1)
                result |= local_copy or attachment
        return result

    def _hgr_sync_note_pdfs(self):
        if self.env.user.share or self.env.context.get('hgr_syncing_note_pdfs'):
            return
        for record in self:
            for attachment in record._hgr_note_pdfs():
                if attachment.res_model == record._name and attachment.res_id == record.id:
                    continue
                existing = self.env['ir.attachment'].search([
                    ('res_model', '=', record._name), ('res_id', '=', record.id),
                    ('hgr_note_source_id', '=', attachment.id)], limit=1)
                if not existing:
                    if not attachment.raw:
                        # Restored databases may lack filestore binaries. Keep
                        # the original link; printing reports the missing file.
                        continue
                    # Copy instead of moving: the line/source keeps its access
                    # rules and link; the parent gets a normal chatter file.
                    attachment.copy({'res_model': record._name, 'res_id': record.id,
                                     'hgr_note_source_id': attachment.id,
                                     'hgr_note_original_name': attachment.hgr_note_original_name or attachment.name,
                                     'public': False, 'access_token': False})
            if record._name == 'sale.order':
                record._hgr_name_note_pdfs()

    def _hgr_name_note_pdfs(self):
        """Name this quotation's copies and point its notes at those copies.

        Shared originals stay untouched. Rewriting the link also ensures that
        opening a note and printing it use the same editable chatter attachment.
        """
        self.ensure_one()
        if not self.name or self.name == '/':
            return
        attachments = self._hgr_note_pdfs()
        by_source = {}
        for attachment in attachments:
            if attachment.res_model == self._name and attachment.res_id == self.id:
                by_source[attachment.id] = attachment
                if attachment.hgr_note_source_id:
                    by_source[attachment.hgr_note_source_id.id] = attachment
        named = set()
        used_names = set()
        for owner, field in [(line, 'name') for line in self.order_line.sorted('sequence')] + [(self, 'note')]:
            value = owner[field]
            if not value or not note_attachment_ids([value], self.get_base_url()):
                continue
            root = html.fragment_fromstring(str(value), create_parent='div')
            heading = ' '.join((root.text or '').split())
            changed = False
            for node in root.iter():
                # The nearest preceding text block in this note is its title.
                # A file box or another file link is never a title.
                if node.tag in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div') and node is not root:
                    if not node.xpath('.//a | .//*[@data-attachment-id]'):
                        text = ' '.join(node.text_content().split())
                        if text:
                            heading = text
                if node.tag != 'a':
                    continue
                ids = note_attachment_ids([html.tostring(node, encoding='unicode')], self.get_base_url())
                attachment = by_source.get(ids[0]) if ids else None
                if attachment is None:
                    continue
                if attachment.id not in named:
                    original = attachment.hgr_note_original_name or attachment.name
                    title = heading or re.sub(r'\.pdf$', '', original, flags=re.I)
                    prefix = self.name + ' – '
                    if title.startswith(prefix):
                        title = title[len(prefix):]
                    # Keep filenames portable and leave space for the extension.
                    stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '-', prefix + title).strip()[:180]
                    filename = stem + '.pdf'
                    suffix = 2
                    while filename in used_names:
                        filename = '%s (%s).pdf' % (stem, suffix)
                        suffix += 1
                    used_names.add(filename)
                    vals = {}
                    if not attachment.hgr_note_original_name:
                        vals['hgr_note_original_name'] = original
                    if attachment.name != filename:
                        vals['name'] = filename
                    if vals:
                        attachment.write(vals)
                    named.add(attachment.id)
                url = '/web/content/%s?download=true' % attachment.id
                if node.get('href') != url or node.text_content().strip() != attachment.name:
                    node.set('href', url)
                    labels = node.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " o_file_name ")]')
                    label = labels[0] if labels else node
                    # File icons are siblings of the filename link in Odoo.
                    for child in list(label):
                        label.remove(child)
                    label.text = attachment.name
                    changed = True
                for parent in node.iterancestors():
                    if parent.get('data-attachment-id') is not None:
                        if parent.get('data-attachment-id') != str(attachment.id):
                            parent.set('data-attachment-id', str(attachment.id))
                            changed = True
            if changed:
                markup = (root.text or '') + ''.join(html.tostring(child, encoding='unicode') for child in root)
                owner.with_context(hgr_syncing_note_pdfs=True).write({field: markup})


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'hgr.note.pdf.mixin']

    def _hgr_portal_pdf_links(self, value, access_token=None):
        """Render portal-only preview links without changing stored note HTML."""
        self.ensure_one()
        safe = html_sanitize(value or '')
        if not note_attachment_ids([safe], self.get_base_url()):
            return Markup(safe)
        mapping = {}
        for attachment in self._hgr_note_pdfs():
            mapping[attachment.id] = attachment.id
            if attachment.hgr_note_source_id:
                mapping[attachment.hgr_note_source_id.id] = attachment.id
        root = html.fragment_fromstring(safe, create_parent='div')
        for node in root.iter('a'):
            ids = note_attachment_ids([html.tostring(node, encoding='unicode')], self.get_base_url())
            target = mapping.get(ids[0]) if ids else None
            if target:
                url = '/my/orders/%s/note-pdf/%s' % (self.id, target)
                if access_token:
                    url += '?' + urlencode({'access_token': access_token})
                node.set('href', url)
                node.set('target', '_blank')
                node.set('rel', 'noopener')
                node.attrib.pop('download', None)
        return Markup(str(escape(root.text or '')) + ''.join(html.tostring(child, encoding='unicode') for child in root))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._hgr_sync_note_pdfs()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'name', 'note', 'order_line', 'hgr_print_with_attachments'} & vals.keys():
            self._hgr_sync_note_pdfs()
        return result

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        vals['hgr_print_with_attachments'] = self.hgr_print_with_attachments
        return vals


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'hgr.note.pdf.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._hgr_sync_note_pdfs()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'narration', 'invoice_line_ids', 'hgr_print_with_attachments'} & vals.keys():
            self._hgr_sync_note_pdfs()
        return result


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.order_id._hgr_sync_note_pdfs()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'name' in vals:
            self.order_id._hgr_sync_note_pdfs()
        return result


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.move_id._hgr_sync_note_pdfs()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'name', 'hgr_html_description'} & vals.keys():
            self.move_id._hgr_sync_note_pdfs()
        return result
