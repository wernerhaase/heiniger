"""Keep PDF line values together without changing the underlying report data."""
from copy import deepcopy
from lxml import etree, html as html_parser


def paginate_line_tables(content):
    root = html_parser.fromstring(content)
    changed = False
    for table in root.xpath("//div[contains(concat(' ', normalize-space(@class), ' '), ' din_page ')]//table[contains(concat(' ', normalize-space(@class), ' '), ' o_main_table ')]"):
        if table.xpath("ancestor::div[@data-hgr-paginated]"):
            continue
        headers = table.xpath('./thead/tr/th')
        rows = table.xpath('./tbody/tr')
        # Leave unfamiliar third-party table structures intact.
        if not rows or len(table.xpath('./thead/tr')) != 1 or table.xpath('./tfoot|./caption'):
            continue
        names = [h.get('name') for h in headers]
        widths = {'th_position': 5, 'th_quantity': 13, 'th_priceunit': 13,
                  'th_discount': 7, 'th_taxes': 12, 'th_subtotal': 18}
        if names.count('th_description') != 1 or any(n not in widths and n != 'th_description' for n in names):
            continue
        widths['th_description'] = 100 - sum(widths[n] for n in names if n != 'th_description')
        if widths['th_description'] < 25:
            continue

        def line_table():
            result = etree.Element('table', dict(table.attrib))
            result.attrib.pop('id', None)
            cols = etree.SubElement(result, 'colgroup')
            for name in names:
                etree.SubElement(cols, 'col', style='width: %s%%' % widths[name])
            return result

        # Qt does not reliably honor break-inside on table rows. Separate line
        # tables share explicit column widths; the surrounding block is honored.
        block = etree.Element('div', {'class': 'hgr_paginated_lines', 'data-hgr-paginated': '1'})
        if table.get('id'):
            block.set('id', table.get('id'))
        pending = etree.SubElement(block, 'div', {'class': 'hgr_keep'})
        heading = line_table()
        heading.append(deepcopy(table.find('thead')))
        pending.append(heading)
        for row in rows:
            if pending is None:
                pending = etree.SubElement(block, 'div', {'class': 'hgr_keep'})
            line = line_table()
            body = etree.SubElement(line, 'tbody', dict(row.getparent().attrib))
            body.append(deepcopy(row))
            pending.append(line)
            classes = row.get('class', '').split()
            # Keep section/subsection headings with the next content row.
            # Oversized notes may span pages; their paragraphs/bullets can flow.
            if not {'o_line_section', 'o_line_subsection'}.intersection(classes):
                pending = None
        block.tail = table.tail
        table.getparent().replace(table, block)
        changed = True
    if changed:
        for footer in root.xpath("//div[contains(concat(' ', normalize-space(@class), ' '), ' din_page ')][contains(concat(' ', normalize-space(@class), ' '), ' footer ')]"):
            footer.set('class', footer.get('class') + ' hgr_pagination_footer')
        return html_parser.tostring(root, encoding='utf-8')
    return content
