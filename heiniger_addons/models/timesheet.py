from odoo import models, fields, _

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    l10n_din5008_document_subject = fields.Char(compute='_compute_l10n_din5008_document_subject')
    l10n_din5008_addresses = fields.Binary(compute='_compute_l10n_din5008_addresses')
    l10n_din5008_template_data = fields.Binary(compute='_compute_l10n_din5008_template_data')
    l10n_din5008_document_title = fields.Char(compute='_compute_l10n_din5008_document_title')

    def _compute_l10n_din5008_document_subject(self):
        for record in self:
            sale_order = record.so_line.order_id[:1]
            record.l10n_din5008_document_subject = sale_order.hgr_subject or ''


    def _compute_l10n_din5008_addresses(self):
        for record in self:
            data = []
            sale_order = record.so_line.order_id[:1]
            if sale_order.partner_shipping_id:
                data.append((_("Objekt:"), sale_order.partner_shipping_id))
            record.l10n_din5008_addresses = data

    def _compute_l10n_din5008_template_data(self):
        for record in self:
            record.l10n_din5008_template_data = []

    def _compute_l10n_din5008_document_title(self):
        for record in self:
            record.l10n_din5008_document_title = _('Timesheet')
