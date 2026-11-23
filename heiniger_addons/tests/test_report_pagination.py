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
        # A short note stays in one unbreakable block with its section heading.
        self.assertNotIn('hgr_flow_note', groups[0].get('class'))
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
        slices = updated.xpath('//table[contains(@class,"hgr_slice_")]')
        self.assertGreater(len(slices), 2)
        # Prices only on the first slice, which stays with the section heading.
        self.assertEqual(len(updated.xpath('//td[contains(text(),"6\'755.05")]')), 1)
        first_group = updated.xpath('//div[contains(concat(" ", @class, " "), " hgr_keep ")]')[0]
        self.assertTrue(first_group.xpath('.//table[contains(@class,"hgr_slice_start")]'))
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

    def test_short_note_heading_stays_with_next_line(self):
        source = self.report('''<tr><td>Vorher</td><td>1</td><td>CHF 1</td></tr>
            <tr class="o_line_note"><td colspan="3"><p><em>Material f. Heizungs-Installationen</em></p></td></tr>
            <tr><td>Klemmringverschraubung</td><td>18</td><td>CHF 153.00</td></tr>''')
        updated = html.fromstring(paginate_line_tables(source))
        groups = updated.xpath('//div[contains(concat(" ", @class, " "), " hgr_keep ")]')
        heading_group = [g for g in groups if g.xpath('.//em')][0]
        self.assertNotIn('hgr_flow_note', heading_group.get('class'))
        self.assertTrue(heading_group.xpath('.//td[text()="Klemmringverschraubung"]'))

    def test_long_note_after_section_is_sliced_with_heading_kept(self):
        bullets = ''.join('<li>Neu liefern und verlegen, Schritt %d mit ausfuehrlicher Beschreibung der Arbeiten '
                          'inklusive Material und Zubehoer gemaess Vorbestand</li>' % i for i in range(12))
        source = self.report('''<tr class="o_line_section"><td colspan="2">Pos. 4 / Sanitaer</td><td>CHF 5</td></tr>
            <tr class="o_line_note"><td colspan="3"><span><p><strong>Arbeitsbeschrieb Sanitaer</strong></p>
            <ul>''' + bullets + '''</ul></span></td></tr>
            <tr><td>Rohr</td><td>1</td><td>CHF 1</td></tr>''')
        result = paginate_line_tables(source)
        updated = html.fromstring(result)
        pieces = updated.xpath('//div[contains(@class,"hgr_note_content")]')
        self.assertGreater(len(pieces), 2)
        first_group = updated.xpath('//div[contains(concat(" ", @class, " "), " hgr_keep ")]')[0]
        # Section heading, note heading and its first bullet stay together and unbreakable.
        self.assertTrue(first_group.xpath('.//tr[contains(@class,"o_line_section")]'))
        self.assertTrue(first_group.xpath('.//strong[text()="Arbeitsbeschrieb Sanitaer"]'))
        self.assertTrue(first_group.xpath('.//li'))
        self.assertFalse(updated.xpath('//*[contains(@class,"hgr_flow_note")]'))
        texts = [t for t in updated.xpath('//li/text()') if t.startswith('Neu liefern')]
        self.assertEqual(len(texts), 12)
        self.assertEqual(paginate_line_tables(result), result)

    def test_bold_lead_in_never_ends_a_slice(self):
        bullets = ''.join('<li>Position %d mit einer laengeren Beschreibung der Leistung</li>' % i for i in range(6))
        source = self.report('''<tr><td name="td_product_name"><span><ul>''' + bullets + '''</ul>
            <p><strong>Sanitaere Installationen:</strong></p><ul>''' + bullets + '''</ul></span></td>
            <td>1</td><td>CHF 1</td></tr>''')
        updated = html.fromstring(paginate_line_tables(source))
        lead = updated.xpath('//strong[text()="Sanitaere Installationen:"]')[0]
        self.assertTrue(lead.xpath('ancestor::table[1]//li'), 'lead-in must share its slice with a bullet')

    def test_terms_heading_stays_with_first_bullets(self):
        source = self.report('<tr><td>A</td><td>1</td><td>CHF 1</td></tr>').replace(
            b'</div></div>', b'''<span name="order_note"><h6><u><strong>Bauseitige Leistungen</strong></u></h6>
            <ul><li>Elektro</li><li>Strom 240V</li><li>Wasser 3/4"</li><li>Zufahrt</li></ul></span></div></div>''')
        result = paginate_line_tables(source)
        updated = html.fromstring(result)
        group = updated.xpath('//div[contains(@class,"hgr_heading_group")]')[0]
        self.assertTrue(group.xpath('./h6'))
        self.assertEqual(group.xpath('.//li/text()'), ['Elektro', 'Strom 240V'])
        self.assertEqual(updated.xpath('//ul[contains(@class,"hgr_list_rest")]/li/text()'), ['Wasser 3/4"', 'Zufahrt'])
        self.assertEqual(paginate_line_tables(result), result)

    def test_slash_breaks_only_between_words(self):
        source = self.report('''<tr><td name="td_product_name">Kehrichtsaecke/Behaeltnisse 3/4" W/m2 KW/WW</td>
            <td>1</td><td>CHF 1</td></tr>''')
        text = paginate_line_tables(source).decode()
        self.assertIn('Kehrichtsaecke/\u200bBehaeltnisse', text)
        for kept in ('3/4"', 'W/m2', 'KW/WW'):
            self.assertIn(kept, text)

    def test_unknown_and_non_din_layouts_remain_unchanged(self):
        source = self.report('<tr><td>A</td></tr>', '<th name="custom">Custom</th>')
        self.assertEqual(paginate_line_tables(source), source)
        source = self.report('<tr><td>A</td></tr>').replace(b'din_page', b'other_layout')
        self.assertEqual(paginate_line_tables(source), source)
