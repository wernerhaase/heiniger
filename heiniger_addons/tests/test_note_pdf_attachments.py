from odoo.tests import BaseCase, TransactionCase, tagged
from odoo.addons.mail.tools.discuss import Store
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


@tagged('post_install', '-at_install')
class TestQuotationAttachmentOrder(TransactionCase):
    def test_chatter_order_follows_lines_and_note_links(self):
        order = self.env['sale.order'].create({'partner_id': self.env.user.partner_id.id})
        # URL attachments need no filestore and are excluded from PDF syncing.
        first, second, extra = self.env['ir.attachment'].create([
            {'name': name, 'type': 'url', 'url': 'https://example.test/' + name,
             'res_model': 'sale.order', 'res_id': order.id}
            for name in ['first.txt', 'second.txt', 'extra.txt']
        ])
        def link(attachment):
            return '<a href="/web/content/%s">File</a>' % attachment.id
        line = self.env['sale.order.line'].create({
            'order_id': order.id, 'display_type': 'line_note',
            'sequence': 10, 'name': link(second),
        })
        other_line = self.env['sale.order.line'].create({
            'order_id': order.id, 'display_type': 'line_note',
            'sequence': 20, 'name': link(first),
        })
        order.note = link(second)
        self.assertEqual(order._hgr_chatter_attachment_order(), [second.id, first.id])
        other_line.sequence = 5
        self.assertEqual(order._hgr_chatter_attachment_order(), [first.id, second.id])
        line.unlink()
        order.note = False
        self.assertEqual(order._hgr_chatter_attachment_order(), [first.id])
        # Legacy note links may still point to the source of a chatter copy.
        source = self.env['ir.attachment'].create({
            'name': 'source.txt', 'type': 'url', 'url': 'https://example.test/source',
        })
        second.hgr_note_source_id = source
        order.note = link(source) + link(second)
        self.assertEqual(order._hgr_chatter_attachment_order(), [first.id, second.id])
        store = Store()
        order._thread_to_store(store, [], request_list=['attachments'])
        payload = store.get_result()['mail.thread'][0]
        self.assertEqual(payload['hgrQuotationAttachmentOrder'], [first.id, second.id])

    def test_generated_reports_last_without_moving_linked_or_manual_files(self):
        from odoo.tools.safe_eval import safe_eval, time
        order = self.env['sale.order'].create({'partner_id': self.env.user.partner_id.id})
        report = self.env.ref('sale.action_report_saleorder')
        expected = self.env['ir.attachment']
        for lang, _label in self.env['res.lang'].get_installed():
            for state in ('draft', 'sale'):
                document = order.with_context(lang=lang).new({'state': state}, origin=order)
                name = safe_eval(report.with_context(lang=lang).print_report_name,
                                 {'object': document, 'time': time}) + '.pdf'
                expected |= self.env['ir.attachment'].create({
                    'name': name, 'type': 'url', 'url': 'https://example.test/report.pdf',
                    'mimetype': 'application/pdf', 'res_model': 'sale.order', 'res_id': order.id,
                })
        manual = self.env['ir.attachment'].create({
            'name': 'Manual supporting PDF.pdf', 'type': 'url',
            'url': 'https://example.test/manual.pdf', 'mimetype': 'application/pdf',
            'res_model': 'sale.order', 'res_id': order.id,
        })
        self.assertEqual(set(order._hgr_chatter_report_attachment_ids()), set(expected.ids))
        # Explicit quotation-line order takes precedence even for a report filename.
        order.note = '<a href="/web/content/%s">Linked PDF</a>' % expected[0].id
        self.assertNotIn(expected[0].id, order._hgr_chatter_report_attachment_ids())
        self.assertNotIn(manual.id, order._hgr_chatter_report_attachment_ids())
        order.write({'state': 'sale'})
        self.assertEqual(set(order._hgr_chatter_report_attachment_ids()), set(expected[1:].ids))
        store = Store()
        order._thread_to_store(store, [], request_list=['attachments'])
        self.assertEqual(set(store.get_result()['mail.thread'][0]['hgrQuotationReportAttachments']),
                         set(expected[1:].ids))
