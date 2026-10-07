from urllib.parse import urlencode

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.sale.controllers.portal import CustomerPortal


class NotePdfPortal(CustomerPortal):
    @http.route('/my/orders/<int:order_id>/note-pdf/<int:attachment_id>',
                type='http', auth='public', website=True, methods=['GET'])
    def note_pdf(self, order_id, attachment_id, access_token=None, mode='preview', **kwargs):
        try:
            order = self._document_check_access('sale.order', order_id, access_token)
            # The order check grants access only to PDFs actually referenced in
            # this document's notes, never to arbitrary attachment IDs.
            attachment = order._hgr_note_pdfs().filtered(lambda a: a.id == attachment_id)
            if not attachment or mode not in ('preview', 'inline', 'download'):
                return request.not_found()
            if not attachment.raw:
                return request.not_found()
        except (AccessError, MissingError):
            return request.not_found()
        base = '/my/orders/%s/note-pdf/%s' % (order.id, attachment.id)
        def url(mode):
            return base + '?' + urlencode({'mode': mode, 'access_token': access_token or ''})
        if mode != 'preview':
            stream = request.env['ir.binary']._get_stream_from(attachment, 'raw', mimetype='application/pdf')
            response = stream.get_response(as_attachment=mode == 'download')
            response.headers['Cache-Control'] = 'private, no-store'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            return response
        response = request.render('heiniger_addons.portal_note_pdf_preview', {
            'attachment': attachment,
            'inline_url': '/web/static/lib/pdfjs/web/viewer.html?' + urlencode({'file': url('inline')}),
            'download_url': url('download'),
        })
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['Referrer-Policy'] = 'same-origin'
        return response
