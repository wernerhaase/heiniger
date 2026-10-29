from datetime import datetime
import json
import logging
from urllib.parse import urlsplit

import jwt
import requests

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from ..models.editor import MAX_PDF_BYTES

_logger = logging.getLogger(__name__)


def fetch_edited_pdf(url, server_url):
    """Download only from the configured document service, without redirects."""
    target, trusted = urlsplit(url or ''), urlsplit(server_url)
    if (target.scheme, target.netloc) != (trusted.scheme, trusted.netloc) or target.username or target.password:
        raise UserError('The editor returned a file from an unexpected server.')
    with requests.get(url, timeout=(10, 60), stream=True, allow_redirects=False) as response:
        if response.status_code != 200:
            raise UserError('The edited PDF could not be downloaded. Please try saving again.')
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_PDF_BYTES:
                raise UserError('The edited PDF exceeds the 30 MB limit.')
            chunks.append(chunk)
        return b''.join(chunks)


class PdfEditor(http.Controller):
    def _session(self, key):
        session = request.env['hgr.pdf.editor.session'].sudo().search([('key', '=', key)], limit=1)
        if not session:
            raise AccessError('Unknown editing session.')
        return session

    @http.route('/heiniger/pdf/edit/<string:key>', type='http', auth='user', methods=['GET'])
    def editor(self, key, **kwargs):
        session = self._session(key)
        if session.user_id != request.env.user:
            raise AccessError('This editing session belongs to another user.')
        server, config = session._editor_config()
        response = request.render('heiniger_pdf_editor.editor', {
            'editor_script': server + '/web-apps/apps/api/documents/api.js',
            'editor_config': json.dumps(config),
            'title': session.attachment_id.name,
            'session_key': key,
        })
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    @http.route('/heiniger/pdf/status/<string:key>', type='http', auth='user', methods=['GET'])
    def status(self, key, **kwargs):
        session = self._session(key)
        if session.user_id != request.env.user:
            raise AccessError('This editing session belongs to another user.')
        return request.make_json_response({
            'saved_at': str(session.saved_at) if session.saved_at else None,
            'save_age_ms': (datetime.utcnow() - session.saved_at).total_seconds() * 1000 if session.saved_at else None,
        },
                                          headers={'Cache-Control': 'no-store'})

    @http.route('/heiniger/pdf/content/<string:key>', type='http', auth='public', methods=['GET'])
    def content(self, key, token=None, **kwargs):
        try:
            session = self._session(key)
            _, secret, _ = session._configuration()
            payload = jwt.decode(token or '', secret, algorithms=['HS256'], options={'require': ['exp']})
            if payload.get('session') != key or payload.get('purpose') != 'download':
                return request.not_found()
            attachment = session._attachment_as_user()
            if attachment.checksum != session.checksum:
                return request.not_found()
            return request.make_response(attachment.raw, headers=[
                ('Content-Type', 'application/pdf'), ('Cache-Control', 'private, no-store'),
                ('X-Content-Type-Options', 'nosniff'),
            ])
        except (AccessError, UserError, jwt.InvalidTokenError):
            return request.not_found()

    @http.route('/heiniger/pdf/callback/<string:key>', type='http', auth='public', methods=['POST'], csrf=False)
    def callback(self, key, **kwargs):
        try:
            # On any failure, roll back both backup creation and file writes.
            with request.env.cr.savepoint():
                session = self._session(key)
                server, secret, _ = session._configuration()
                body = request.get_json_data()
                token = body.get('token') or request.httprequest.headers.get('Authorization', '').removeprefix('Bearer ')
                signed = jwt.decode(token, secret, algorithms=['HS256'])
                payload = signed.get('payload', signed)
                if payload.get('key') != key or payload.get('status') not in (1, 2, 3, 4, 6, 7):
                    raise AccessError('Invalid editor callback.')
                status = payload['status']
                # A browser config JWT or download token cannot authorize a save.
                if session.closed and status in (2, 4):
                    return request.make_json_response({'error': 0})
                session._attachment_as_user()
                if status in (3, 7):
                    raise UserError('The editor reported a save error; the current PDF is unchanged.')
                if status in (2, 6):
                    if payload.get('filetype') != 'pdf':
                        raise UserError('The editor must return PDF format.')
                    data = fetch_edited_pdf(payload.get('url'), server)
                    session._save_pdf(data)
                if status in (2, 4):
                    session.write({'closed': True})
        except Exception:
            _logger.warning('PDF editor callback failed for a session; no file changes committed.', exc_info=True)
            return request.make_json_response({'error': 1}, status=400)
        return request.make_json_response({'error': 0})
