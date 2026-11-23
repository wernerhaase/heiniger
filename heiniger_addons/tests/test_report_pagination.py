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

    def test_tall_rows_are_sliced_between_bullets(self):
        bullets = ''.join('<li>Arbeitsschritt %d mit einer ausfuehrlichen Beschreibung der Leistung</li>' % i
                          for i in range(14))
        source = self.report('''<tr class="o_line_section"><td colspan="2">Pos. 4.2</td><td>CHF 9</td></tr>
            <tr><td name="td_product_name"><span><ul><li><div><strong>Nasszelle:</strong> Arbeiten</div>
            <ul>''' + bullets + '''</ul></li></ul></span></td><td>1.00</td><td>CHF 6'755.05</td></tr>
            <tr><td name="td_product_name"><span><ul><li>Kehrichtsaecke/Behaeltnisse</li></ul></span></td>
            <td>1</td><td>CHF 2</td></tr>''')
        result = paginate_line_tables(source)
        updated = html.fromstring(result)
        slices = updated.xpath('//table[contains(@class,"hgr_row_start") or contains(@class,"hgr_row_middle")'
                               ' or contains(@class,"hgr_row_end")]')
        self.assertGreater(len(slices), 2)
        # Prices only on the first slice, which stays with the section heading.
        self.assertEqual(len(updated.xpath('//td[contains(text(),"6\'755.05")]')), 1)
        first_group = updated.xpath('//div[contains(concat(" ", @class, " "), " hgr_keep ")]')[0]
        self.assertTrue(first_group.xpath('.//table[contains(@class,"hgr_row_start")]'))
        self.assertTrue(first_group.xpath('.//tr[contains(@class,"o_line_section")]'))
        # Every bullet is printed exactly once, in order, without the head being repeated.
        texts = [t for t in updated.xpath('//li/text()') if t.startswith('Arbeitsschritt')]
        self.assertEqual(texts, ['Arbeitsschritt %d mit einer ausfuehrlichen Beschreibung der Leistung' % i
                                 for i in range(14)])
        self.assertEqual(len(updated.xpath('//strong[text()="Nasszelle:"]')), 1)
        self.assertFalse(updated.xpath('//*[@data-hgr-unit or @data-hgr-head]'))
        # Short rows stay whole; long slash words get a break opportunity.
        self.assertIn('Kehrichtsaecke/\u200bBehaeltnisse', result.decode())
        self.assertEqual(paginate_line_tables(result), result)

    def test_unknown_and_non_din_layouts_remain_unchanged(self):
        source = self.report('<tr><td>A</td></tr>', '<th name="custom">Custom</th>')
        self.assertEqual(paginate_line_tables(source), source)
        source = self.report('<tr><td>A</td></tr>').replace(b'din_page', b'other_layout')
        self.assertEqual(paginate_line_tables(source), source)
