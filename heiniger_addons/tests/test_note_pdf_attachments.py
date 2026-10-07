from odoo.tests import BaseCase, tagged
from ..models.note_pdf_attachments import note_attachment_ids


@tagged('post_install', '-at_install')
class TestNotePdfLinks(BaseCase):
    def test_order_and_duplicates(self):
        values = ['<span data-attachment-id="4"><a href="/web/content/4?download=true">A</a></span>'
                  '<a href="/web/content/ir.attachment/7/datas">B</a>',
                  '<a href="/web/content/4">again</a><a href="/web/content/9-checksum/file.pdf">C</a>']
        self.assertEqual(note_attachment_ids(values, 'https://example.test'), [4, 7, 9])

    def test_external_and_non_attachment_links_are_ignored(self):
        values = ['<a href="https://other.test/web/content/4">External</a>'
                  '<a href="//other.test/web/content/5">External</a>'
                  '<a href="javascript:alert(1)">bad</a>'
                  '<a href="https://example.test/web/content/6">Local</a>'
                  '<a href="/web/image/7">Image</a>']
        self.assertEqual(note_attachment_ids(values, 'https://example.test'), [6])

    def test_plain_empty_notes(self):
        self.assertEqual(note_attachment_ids([False, '', 'Just a plain note'], 'https://example.test'), [])
