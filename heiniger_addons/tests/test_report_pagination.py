from lxml import html
from odoo.tests import BaseCase, tagged
from ..models.report_pagination import paginate_line_tables


@tagged('post_install', '-at_install')
class TestReportPagination(BaseCase):
    def report(self, rows, extra_header=''):
        return ('''<div class="din_page"><div class="page">
            <table class="o_main_table" id="lines"><thead><tr>
            <th name="th_description">Beschreibung</th>
            <th name="th_quantity">Menge</th>''' + extra_header + '''
            <th name="th_subtotal">Betrag</th></tr></thead>
            <tbody class="sale_tbody">''' + rows + '</tbody></table></div></div>').encode()

    def test_preserves_rich_rows_and_groups_heading_with_content(self):
        source = self.report('''<tr class="o_line_section"><td colspan="3">Abschnitt</td></tr>
            <tr class="o_line_note"><td colspan="3"><p><strong>Arbeiten</strong></p>
            <ul><li>Erster Schritt</li><li>Zweiter Schritt</li></ul></td></tr>
            <tr><td>Glas</td><td>1</td><td>CHF 1'234.50</td></tr>''')
        result = paginate_line_tables(source)
        original, updated = html.fromstring(source), html.fromstring(result)
        self.assertEqual([html.tostring(r) for r in original.xpath('//tbody/tr[not(contains(@class,"o_line_note"))]')],
                         [html.tostring(r) for r in updated.xpath('//tbody/tr')])
        self.assertEqual(original.xpath('//tr[@class="o_line_note"]//strong/text()'),
                         updated.xpath('//div[contains(@class,"hgr_note_content")]//strong/text()'))
        self.assertEqual(original.xpath('//li/text()'), updated.xpath('//li/text()'))
        groups = updated.xpath('//div[contains(concat(" ", @class, " "), " hgr_keep ")]')
        self.assertEqual(len(groups), 2)
        self.assertEqual(len(groups[0].xpath('.//tbody/tr')), 1)
        self.assertEqual(len(groups[0].xpath('.//div[contains(@class,"hgr_note_content")]')), 1)
        self.assertIn('hgr_flow_note', groups[0].get('class'))
        self.assertNotIn('hgr_flow_note', groups[1].get('class'))
        self.assertEqual(len(updated.xpath('//*[@id="lines"]')), 1)
        self.assertEqual(paginate_line_tables(result), result)

    def test_optional_columns_share_the_same_widths(self):
        result = html.fromstring(paginate_line_tables(self.report(
            '<tr><td>A</td><td>1</td><td>5%</td><td>10</td></tr>',
            '<th name="th_discount">Rabatt</th>')))
        widths = [t.xpath('./colgroup/col/@style') for t in result.xpath('//table')]
        self.assertEqual(widths[0], widths[1])
        self.assertEqual(sum(float(w.split(':')[1].strip(' %')) for w in widths[0]), 100)

    def test_unknown_and_non_din_layouts_remain_unchanged(self):
        source = self.report('<tr><td>A</td></tr>', '<th name="custom">Custom</th>')
        self.assertEqual(paginate_line_tables(source), source)
        source = self.report('<tr><td>A</td></tr>').replace(b'din_page', b'other_layout')
        self.assertEqual(paginate_line_tables(source), source)
