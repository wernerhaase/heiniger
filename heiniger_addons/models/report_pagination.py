"""Keep PDF line values together without changing the underlying report data."""
from copy import deepcopy
import math
import re

from lxml import etree, html as html_parser

# A4 body with DIN margins holds roughly 40 text lines. Rows estimated above
# this many lines are split into consecutive slices so the page can break
# between bullets instead of moving the whole row (leaving a half-empty page).
TALL_ROW_LINES = 6
# The first slice stays with the prices (and with a preceding section heading).
FIRST_SLICE_LINES = 3
LIST_TAGS = ('ul', 'ol')
HEADING_TAGS = ('h1', 'h2', 'h3', 'h4', 'h5', 'h6')
BLOCK_TAGS = ('p', 'div', 'li', 'blockquote', 'pre', 'table') + HEADING_TAGS
UNIT = 'data-hgr-unit'
HEAD = 'data-hgr-head'
# Only between words of 3+ letters: "Kehrichtsäcke/Behältnisse" may wrap, while
# measurements such as 3/4", W/m2 or KW/WW stay intact.
SLASH_BREAK = re.compile(r'(?<=[^\W\d_]{3})/(?=[^\W\d_]{3})')
ZWSP = '\u200b'
NOTE_CHARS_PER_LINE = 95


def _text(element):
    return ''.join(element.itertext())


def _text_lines(text, chars_per_line):
    text = ' '.join((text or '').split())
    return max(1, math.ceil(len(text) / max(chars_per_line, 10)))


def _own_text(element):
    """Text of an element excluding nested lists."""
    parts = [element.text or '']
    for child in element:
        if not isinstance(child.tag, str):
            parts.append(child.tail or '')
            continue
        if child.tag not in LIST_TAGS:
            parts.append(_text(child))
        parts.append(child.tail or '')
    return ''.join(parts)


def _allow_slash_breaks(cell):
    """Let long "a/b/c" words wrap at the slash instead of mid-word."""
    for element in cell.iter():
        if not isinstance(element.tag, str):
            continue
        if element.text:
            element.text = SLASH_BREAK.sub('/' + ZWSP, element.text)
        if element.tail and element is not cell:
            element.tail = SLASH_BREAK.sub('/' + ZWSP, element.tail)


def _is_heading_like(element):
    """A heading tag, or a short paragraph that is entirely bold/underlined
    (e.g. "<p><strong>Heizungs-Installationen:</strong></p>")."""
    if not isinstance(element.tag, str):
        return False
    text = ' '.join(_text(element).split())
    if not text:
        return False
    if element.tag in HEADING_TAGS:
        return True
    if element.tag not in ('p', 'div') or len(text) > 120 or element.xpath('.//ul|.//ol|.//li'):
        return False
    emphasised = ' '.join(''.join(
        _text(e) for e in element.xpath('.//strong|.//b|.//u')
        if not e.xpath('ancestor::strong|ancestor::b|ancestor::u')).split())
    return emphasised == text or (len(text) <= 80 and text.endswith(':'))


def _mark_units(cell, chars_per_line):
    """Tag the smallest printable pieces (bullets/paragraphs) in document order.

    A bullet with nested bullets is a "head": its own text is one unit and its
    nested bullets are units of their own. Returns (estimated lines, is_heading)
    per unit; a heading must never be the last unit of a slice.
    """
    heights = []

    def visit(element, depth):
        for child in element:
            if not isinstance(child.tag, str):
                continue
            if child.tag in LIST_TAGS:
                visit(child, depth + 1)
            elif child.tag == 'li' and child.xpath('./ul|./ol'):
                child.set(HEAD, str(len(heights)))
                heights.append((_text_lines(_own_text(child), chars_per_line - 3 * depth), True))
                for nested in child.xpath('./ul|./ol'):
                    visit(nested, depth + 1)
            elif child.tag == 'li' or child.tag in BLOCK_TAGS:
                if child.tag != 'li' and child.xpath('.//ul|.//ol'):
                    visit(child, depth)
                else:
                    child.set(UNIT, str(len(heights)))
                    heights.append((_text_lines(_text(child), chars_per_line - 3 * depth),
                                    _is_heading_like(child)))
            else:
                visit(child, depth)

    visit(cell, 0)
    return heights


def _unmark(cell):
    for element in cell.xpath('.//*[@%s or @%s]' % (UNIT, HEAD)):
        element.attrib.pop(UNIT, None)
        element.attrib.pop(HEAD, None)


def _prune(cell, keep):
    """Keep only units whose index is in ``keep`` (structure is preserved)."""
    for element in list(cell.xpath('.//*[@%s]' % UNIT)):
        if int(element.get(UNIT)) not in keep:
            element.drop_tree()
        else:
            del element.attrib[UNIT]
    for element in list(cell.xpath('.//*[@%s]' % HEAD)):
        if int(element.get(HEAD)) in keep:
            del element.attrib[HEAD]
            continue
        # Continuation: drop the item's own text but keep its nested bullets.
        del element.attrib[HEAD]
        element.text = None
        for child in list(element):
            if isinstance(child.tag, str) and child.tag in LIST_TAGS:
                child.tail = None
            else:
                element.remove(child)
        element.set('class', (element.get('class', '') + ' hgr_list_continuation').strip())
    # Remove lists and continuation items left without any real bullet.
    while True:
        empty = [e for e in cell.xpath('.//ul|.//ol|.//li[contains(@class,"hgr_list_continuation")]')
                 if not e.xpath('.//li[not(contains(@class,"hgr_list_continuation"))]')]
        if not empty:
            break
        empty[0].drop_tree()


def _slice_groups(cell, chars_per_line):
    """Group the cell's units into slices, or return None to keep it whole."""
    units = _mark_units(cell, chars_per_line)
    heights = [height for height, _heading in units]
    if sum(heights) <= TALL_ROW_LINES or len(units) < 2:
        _unmark(cell)
        return None
    # Text outside bullets/paragraphs cannot be sliced safely; keep such cells whole.
    loose = deepcopy(cell)
    _prune(loose, set())
    if _text(loose).strip():
        _unmark(cell)
        return None

    groups, current, size = [], [], 0
    for index, (height, heading) in enumerate(units):
        current.append(index)
        size += height
        if heading and index < len(units) - 1:
            continue  # keep a heading/lead-in with the bullet that follows it
        if not groups and size < FIRST_SLICE_LINES:
            continue
        groups.append(current)
        current, size = [], 0
    if current:
        groups.append(current)
    # Avoid a lonely one-line slice at the end.
    if len(groups) > 1 and sum(heights[i] for i in groups[-1]) < 2:
        groups[-2].extend(groups.pop())
    if len(groups) < 2:
        _unmark(cell)
        return None
    return groups


def _slice_position(index, count):
    return ('hgr_slice_start' if index == 0 else
            'hgr_slice_end' if index == count - 1 else 'hgr_slice_middle')


def _split_tall_row(row, names, description_width):
    """Return the row as one or more row slices that may break between pages."""
    cells = [c for c in row if isinstance(c.tag, str)]
    if len(cells) != len(names) or 'th_description' not in names:
        return [row]
    position = names.index('th_description')
    cell = cells[position]
    _allow_slash_breaks(cell)
    groups = _slice_groups(cell, int(description_width * 0.95))
    if not groups:
        return [row]

    parts = []
    for number, group in enumerate(groups):
        part = deepcopy(row)
        part_cells = [c for c in part if isinstance(c.tag, str)]
        _prune(part_cells[position], set(group))
        if number:
            # Continuation slices only carry description text.
            for other, part_cell in enumerate(part_cells):
                if other != position:
                    for child in list(part_cell):
                        part_cell.remove(child)
                    part_cell.text = None
            part.set('class', (part.get('class', '') + ' hgr_row_continuation').strip())
        parts.append(part)
    return parts


def _note_block(row):
    note = html_parser.Element('div', dict(row.attrib))
    note.set('class', row.get('class', '') + ' hgr_note_content')
    cell = deepcopy(row[0])
    cell.tag = 'div'
    cell.attrib.pop('colspan', None)
    note.append(cell)
    _allow_slash_breaks(cell)
    return note


def _keep_text_headings(root):
    """Keep headings in free text (e.g. the terms below the lines) with the
    first bullets of the list that follows them."""
    changed = False
    path = ("//div[contains(concat(' ', normalize-space(@class), ' '), ' din_page ')]"
            "//*[self::h1 or self::h2 or self::h3 or self::h4 or self::h5 or self::h6 or self::p or self::div]")
    for heading in root.xpath(path):
        if heading.xpath('ancestor::table|ancestor::*[@data-hgr-paginated]'
                         '|ancestor-or-self::div[contains(@class,"hgr_heading_group")]'):
            continue
        following = heading.getnext()
        if (following is None or not isinstance(following.tag, str)
                or following.tag not in LIST_TAGS or not _is_heading_like(heading)):
            continue
        items = following.xpath('./li')
        if not items:
            continue
        group = etree.Element('div', {'class': 'hgr_heading_group'})
        heading.addprevious(group)
        group.append(heading)
        if len(items) <= 3:
            group.append(following)
        else:
            first = etree.SubElement(group, following.tag, dict(following.attrib))
            first.set('class', (following.get('class', '') + ' hgr_list_start').strip())
            for item in items[:2]:
                first.append(item)
            following.set('class', (following.get('class', '') + ' hgr_list_rest').strip())
            if following.tag == 'ol':
                following.set('start', str(int(following.get('start', '1')) + 2))
        changed = True
    return changed


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
        heading.set('class', heading.get('class', '') + ' hgr_line_heading')
        heading.append(deepcopy(table.find('thead')))
        pending.append(heading)
        for row in rows:
            if pending is None:
                pending = etree.SubElement(block, 'div', {'class': 'hgr_keep'})
            classes = row.get('class', '').split()
            if 'o_line_note' in classes and len(row) == 1:
                note = _note_block(row)
                # A short note without bullets acts as a heading for the lines
                # below it (e.g. "Material f. Heizungs-Installationen"): keep it
                # with the next line so it is never left alone at a page bottom.
                if not row.xpath('.//li') and _text_lines(_text(row), NOTE_CHARS_PER_LINE) <= 2:
                    pending.append(note)
                    continue
                groups = _slice_groups(note, NOTE_CHARS_PER_LINE)
                if groups:
                    # Long notes are sliced between bullets like tall rows; the
                    # first slice stays with a preceding section heading.
                    for number, group in enumerate(groups):
                        if pending is None:
                            pending = etree.SubElement(block, 'div', {'class': 'hgr_keep'})
                        piece = deepcopy(note)
                        _prune(piece, set(group))
                        piece.set('class', piece.get('class') + ' ' + _slice_position(number, len(groups)))
                        pending.append(piece)
                        pending = None
                    continue
                if _text_lines(_text(row), NOTE_CHARS_PER_LINE) <= TALL_ROW_LINES or row.xpath('.//li'):
                    pending.append(note)
                    pending = None
                    continue
                # Qt may move a single table cell intact even when break-inside
                # is auto. Long free text that cannot be sliced may flow.
                pending.set('class', 'hgr_keep hgr_flow_note')
                pending.append(note)
                for item in note.xpath('.//li[not(.//ul or .//ol)]'):
                    item.set('class', item.get('class', '') + ' hgr_note_leaf')
                pending = None
                continue
            is_heading = bool({'o_line_section', 'o_line_subsection'}.intersection(classes))
            parts = [row] if is_heading else _split_tall_row(row, names, widths['th_description'])
            for index, part in enumerate(parts):
                if pending is None:
                    pending = etree.SubElement(block, 'div', {'class': 'hgr_keep'})
                line = line_table()
                if len(parts) > 1:
                    line.set('class', line.get('class', '') + ' ' + _slice_position(index, len(parts)))
                body = etree.SubElement(line, 'tbody', dict(row.getparent().attrib))
                body.append(part if part is not row else deepcopy(row))
                pending.append(line)
                if is_heading:
                    line.set('class', line.get('class', '') + ' hgr_line_heading')
                # Keep section/subsection headings with the next content row.
                # Oversized notes may span pages; their paragraphs/bullets can flow.
                else:
                    pending = None
        block.tail = table.tail
        table.getparent().replace(table, block)
        changed = True
    changed = _keep_text_headings(root) or changed
    if changed:
        for footer in root.xpath("//div[contains(concat(' ', normalize-space(@class), ' '), ' din_page ')][contains(concat(' ', normalize-space(@class), ' '), ' footer ')]"):
            footer.set('class', footer.get('class') + ' hgr_pagination_footer')
        return html_parser.tostring(root, encoding='utf-8')
    return content
