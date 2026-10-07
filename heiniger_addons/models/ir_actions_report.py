from io import BytesIO

from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools.pdf import PdfReader, PdfWriter

from .report_pagination import paginate_line_tables


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)
        allowed = {
            'sale.report_saleorder', 'sale.report_saleorder_raw',
            'heiniger_addons.saleorder_without_prices',
            'account.report_invoice', 'account.report_invoice_with_payments',
        }
        ids = [res_ids] if isinstance(res_ids, int) else res_ids
        if report.model not in ('sale.order', 'account.move') or report.report_name not in allowed or not ids:
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        records = self.env[report.model].browse(ids)
        records.check_access('read')
        if not any(records.mapped('hgr_print_with_attachments')):
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        attachments = {record.id: record._hgr_note_pdfs(strict=True)
                       for record in records if record.hgr_print_with_attachments}
        if not any(attachments.values()):
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        writer = PdfWriter()
        # Append only after core rendering/caching: cached invoice originals
        # never contain supplements, and batch prints keep each file with its document.
        for record in records:
            pdf, kind = super()._render_qweb_pdf(report_ref, res_ids=record.ids, data=dict(data or {}))
            if kind != 'pdf':
                return pdf, kind
            for page in PdfReader(BytesIO(pdf)).pages:
                writer.add_page(page)
            if record.hgr_print_with_attachments:
                for attachment in attachments[record.id]:
                    try:
                        reader = PdfReader(BytesIO(attachment.raw or b''))
                        if reader.is_encrypted or not reader.pages:
                            raise ValueError('Encrypted or empty PDF')
                        for page in reader.pages:
                            writer.add_page(page)
                    except Exception as error:
                        raise UserError(_(
                            'Cannot append PDF "%s". Upload a readable, unencrypted PDF or uncheck Print with attachments.',
                            attachment.name)) from error
        output = BytesIO()
        writer.write(output)
        return output.getvalue(), 'pdf'

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
