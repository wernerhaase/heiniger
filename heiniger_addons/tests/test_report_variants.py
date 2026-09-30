from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReportVariants(TransactionCase):
    def test_price_free_template_has_no_financial_columns(self):
        root = self.env.ref('heiniger_addons.saleorder_without_prices_document')._get_combined_arch()
        forbidden = ['th_priceunit', 'th_discount', 'th_taxes', 'th_subtotal',
                     'td_product_priceunit', 'td_product_discount', 'td_product_taxes',
                     'td_product_subtotal', 'td_section_price', 'td_combo_price',
                     'td_section_group_priceunit', 'td_section_group_discount',
                     'td_section_group_taxes', 'td_section_group_total', 'so_total_summary']
        for name in forbidden:
            self.assertFalse(root.xpath('//*[@name="%s"]' % name), name)
        self.assertTrue(root.xpath('//*[@name="td_product_name"]'))
        self.assertTrue(root.xpath('//*[@name="td_product_quantity"]'))

