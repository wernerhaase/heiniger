from io import BytesIO
import json
from odoo.http import Response
from unittest.mock import patch, Mock
from types import SimpleNamespace

import jwt

from odoo.tests import TransactionCase, tagged, new_test_user
from odoo.exceptions import AccessError, UserError
from odoo.tools.pdf import PdfWriter
from ..controllers.editor import PdfEditor, fetch_edited_pdf


def pdf(width=100):
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=100)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@tagged('post_install', '-at_install')
class TestPdfEditor(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('ir_attachment.location', 'db')
        cls.connection = cls.env['hgr.pdf.editor.connection'].sudo().create({
            'name': 'Test connection', 'company_id': cls.env.company.id,
            'editor_url': 'https://office.example.test',
            'jwt_secret': 'unit-test-secret-not-for-deployment',
            'odoo_url': 'https://odoo.example.test',
        })
        cls.editor_user = new_test_user(cls.env, login='hgr_pdf_editor_test', groups='base.group_user,sales_team.group_sale_manager')
        cls.order = cls.env['sale.order'].with_user(cls.editor_user).create({'partner_id': cls.env.user.partner_id.id})
        cls.original = pdf()
        cls.attachment = cls.env['ir.attachment'].with_user(cls.editor_user).create({
            'name': 'Attachment.pdf', 'raw': cls.original, 'mimetype': 'application/pdf',
            'res_model': 'sale.order', 'res_id': cls.order.id,
        })

    def session(self):
        action = self.attachment.action_hgr_edit_pdf()
        return self.env['hgr.pdf.editor.session'].sudo().search([('key', '=', action['url'].split('/')[-1])])

    def test_save_preserves_identity_and_backup(self):
        session = self.session()
        old_id = self.attachment.id
        session._save_pdf(pdf(200))
        self.assertEqual(self.attachment.id, old_id)
        self.assertEqual(self.attachment.raw, pdf(200))
        backups = self.env['ir.attachment'].search([('hgr_pdf_backup_of_id', '=', old_id)])
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups.raw, self.original)
        self.assertEqual(backups.res_model, 'ir.attachment')
        self.assertNotIn(backups, self.order._get_mail_thread_data_attachments())
        self.assertFalse(backups.public)
        session._save_pdf(pdf(200))
        self.assertEqual(self.env['ir.attachment'].search_count([('hgr_pdf_backup_of_id', '=', old_id)]), 1)

    def test_invalid_pdf_and_concurrent_save_rejected(self):
        first, second = self.session(), self.session()
        with self.assertRaises(UserError):
            first._save_pdf(b'not a PDF')
        self.assertEqual(self.attachment.raw, self.original)
        first._save_pdf(pdf(200))
        with self.assertRaises(UserError):
            second._save_pdf(pdf(300))
        self.assertEqual(self.attachment.raw, pdf(200))

    def test_configuration_signed_and_scoped(self):
        session = self.session()
        server, config = session._editor_config()
        self.assertEqual(server, 'https://office.example.test')
        self.assertEqual(config['documentType'], 'pdf')
        payload = jwt.decode(config['token'], 'unit-test-secret-not-for-deployment', algorithms=['HS256'])
        self.assertEqual(payload['document']['key'], session.key)
        self.assertTrue(payload['editorConfig']['customization']['forcesave'])
        session.closed = True
        with self.assertRaises(AccessError):
            session._attachment_as_user()

    def test_non_sales_and_portal_cannot_edit(self):
        self.attachment.sudo().write({'res_model': 'res.partner', 'res_id': self.env.user.partner_id.id})
        with self.assertRaises(AccessError):
            self.attachment.action_hgr_edit_pdf()
        self.attachment.sudo().write({'res_model': 'sale.order', 'res_id': self.order.id})
        public = self.env.ref('base.public_user')
        with self.assertRaises(AccessError):
            self.attachment.with_user(public).action_hgr_edit_pdf()

    def test_fetch_rejects_other_hosts_and_redirects(self):
        with patch('requests.get') as get:
            with self.assertRaises(UserError):
                fetch_edited_pdf('https://other.test/document.pdf', 'https://office.example.test')
            get.assert_not_called()
            response = Mock(status_code=302)
            get.return_value.__enter__.return_value = response
            with self.assertRaises(UserError):
                fetch_edited_pdf('https://office.example.test/document.pdf', 'https://office.example.test')
            self.assertFalse(get.call_args.kwargs['allow_redirects'])

    def test_callback_requires_signed_save_and_pdf_result(self):
        session = self.session()
        payload = {'key': session.key, 'status': 6, 'filetype': 'pdf',
                   'url': 'https://office.example.test/cache/edited.pdf'}
        request = SimpleNamespace(
            env=self.env,
            get_json_data=lambda: {'token': jwt.encode(payload, 'unit-test-secret-not-for-deployment', algorithm='HS256')},
            httprequest=SimpleNamespace(headers={}),
            make_json_response=lambda data, **kwargs: Response(json.dumps(data), status=kwargs.get('status', 200), mimetype='application/json'),
        )
        module = 'odoo.addons.heiniger_pdf_editor.controllers.editor'
        with patch(module + '.request', request), patch(module + '.fetch_edited_pdf', return_value=pdf(200)):
            self.assertEqual(json.loads(PdfEditor().callback(session.key).data), {'error': 0})
        self.assertEqual(self.attachment.raw, pdf(200))
        # The signed browser configuration must never authorize a callback.
        _, config = session._editor_config()
        request.get_json_data = lambda: {'token': config['token']}
        with patch(module + '.request', request), patch(module + '.fetch_edited_pdf') as fetch:
            with self.assertLogs(module, level='WARNING'):
                self.assertEqual(json.loads(PdfEditor().callback(session.key).data), {'error': 1})
            fetch.assert_not_called()
        request.get_json_data = lambda: payload
        with patch(module + '.request', request), patch(module + '.fetch_edited_pdf') as fetch:
            with self.assertLogs(module, level='WARNING'):
                self.assertEqual(json.loads(PdfEditor().callback(session.key).data), {'error': 1})
            fetch.assert_not_called()
        self.assertEqual(self.attachment.raw, pdf(200))

    def test_editor_template_escapes_filename(self):
        session = self.session()
        self.attachment.name = '</script><script>alert(1)</script>.pdf'
        server, config = session._editor_config()
        import json
        page = self.env['ir.qweb']._render('heiniger_pdf_editor.editor', {
            'title': self.attachment.name, 'session_key': session.key,
            'editor_script': server + '/web-apps/apps/api/documents/api.js',
            'editor_config': json.dumps(config),
        })
        self.assertNotIn('<script>alert(1)</script>', str(page))
        self.assertIn('pdf-editor', str(page))

    def test_archive_disables_edit_and_preserves_files(self):
        session = self.session()
        session._save_pdf(pdf(200))
        self.assertTrue(self.attachment.hgr_pdf_edit_available())
        self.connection.action_archive()
        self.assertFalse(self.attachment.hgr_pdf_edit_available())
        with self.assertRaises(UserError):
            self.attachment.action_hgr_edit_pdf()
        with self.assertRaises(UserError):
            session._save_pdf(pdf(300))
        self.assertEqual(self.attachment.raw, pdf(200))
        backups = self.env['ir.attachment'].search([('hgr_pdf_backup_of_id', '=', self.attachment.id)])
        self.assertEqual(backups.raw, self.original)
        self.connection.action_unarchive()
        self.assertTrue(self.attachment.hgr_pdf_edit_available())

    def test_sales_user_cannot_read_connection_secret(self):
        with self.assertRaises(AccessError):
            self.connection.with_user(self.editor_user).read(['jwt_secret'])
