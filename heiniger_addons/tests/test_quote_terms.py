from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestQuoteTerms(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(su=True)
        cls.env['ir.config_parameter'].set_param('account.use_invoice_terms', True)
        cls.env.company.write({
            'terms_type': 'plain',
            'invoice_terms': '<h6>Bauseitige Leistungen</h6><ul><li>Elektroanschluss</li></ul>',
        })

    def test_duplicate_gets_standard_terms(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [Command.create({'product_id': self.product_a.id})],
        })
        self.assertIn('Bauseitige Leistungen', order.note)
        order.note = '<p>Besten Dank für den geschätzten Auftrag.</p>'

        copy = order.copy()
        self.assertIn('Bauseitige Leistungen', copy.note)
        self.assertNotIn('geschätzten Auftrag', copy.note)
        self.assertIn('geschätzten Auftrag', order.note)
