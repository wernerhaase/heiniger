from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLineSequence(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Sequence test'})

    def make_order(self, section=False):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [Command.create({
                'name': name, 'display_type': 'line_section' if section and i == 1 else 'line_note', 'sequence': 10 + i,
            }) for i, name in enumerate('ABCD')],
        })

    def assert_order(self, order, expected):
        self.env.flush_all()
        order.invalidate_recordset(['order_line'])
        self.assertEqual(order.order_line.sorted(lambda l: (l.sequence, l.id)).ids, expected)

    def test_move_up_both_command_orders(self):
        for reverse in (False, True):
            order = self.make_order()
            a, b, c, d = order.order_line
            updates = [(d.id, 11), (b.id, 12), (c.id, 13)]
            if reverse:
                updates = [updates[1], updates[2], updates[0]]
            order.write({'order_line': [Command.update(i, {'sequence': s}) for i, s in updates]})
            self.assert_order(order, [a.id, d.id, b.id, c.id])

    def test_move_down_and_save_again(self):
        order = self.make_order()
        a, b, c, d = order.order_line
        order.write({'order_line': [
            Command.update(b.id, {'sequence': 10}),
            Command.update(c.id, {'sequence': 11}),
            Command.update(a.id, {'sequence': 12}),
        ]})
        expected = [b.id, c.id, a.id, d.id]
        self.assert_order(order, expected)
        order.write({'client_order_ref': 'Unrelated save'})
        self.assert_order(order, expected)
        order.reorder_sequence()
        self.assert_order(order, expected)

    def test_direct_resequence(self):
        order = self.make_order()
        a, b, c, d = order.order_line
        (d | b | c).web_resequence({'sequence': {}}, offset=11)
        self.assert_order(order, [a.id, d.id, b.id, c.id])

    def test_unrelated_line_edit_preserves_sequences(self):
        order = self.make_order()
        for i, line in enumerate(order.order_line):
            line.write({'sequence': (i + 1) * 10})
        before = order.order_line.mapped('sequence')
        order.order_line[0].write({'name': 'Changed text'})
        order.write({'client_order_ref': 'Changed reference'})
        self.assertEqual(order.order_line.mapped('sequence'), before)

    def test_mixed_lines_and_duplicate_sequences(self):
        order = self.make_order(section=True)
        a, b, c, d = order.order_line
        # Existing ties must keep their ID order during explicit normalization.
        c.sequence = b.sequence
        expected = order.order_line.sorted(lambda l: (l.sequence, l.id)).ids
        order.reorder_sequence()
        self.assert_order(order, expected)
        self.assertEqual(order.order_line.sorted('sequence').mapped('sequence'), [10, 11, 12, 13])
