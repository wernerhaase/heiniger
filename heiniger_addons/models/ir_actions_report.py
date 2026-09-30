from odoo import models

from .report_pagination import paginate_line_tables


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _prepare_html(self, html, report_model=False):
        # PDF-only: portal/HTML previews and stored line descriptions stay intact.
        paginated = False
        if report_model in ('sale.order', 'account.move'):
            original = html
            html = paginate_line_tables(html)
            paginated = html != original
        result = super()._prepare_html(html, report_model=report_model)
        if paginated:
            # Reserve breathing room above DIN's page number, including when
            # Qt places a final bullet just beyond a table's nominal boundary.
            arguments = result[4]
            bottom = arguments.get('data-report-margin-bottom', self.get_paperformat().margin_bottom)
            arguments['data-report-margin-bottom'] = float(bottom) + 4
        return result
