from odoo import models, fields

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    l10n_din5008_document_subject = fields.Char(compute='_compute_l10n_din5008_document_subject')
    l10n_din5008_addresses = fields.Binary(compute='_compute_l10n_din5008_addresses')

    def _compute_l10n_din5008_document_subject(self):
        for record in self:
            record.l10n_din5008_document_subject = record.so_line.order_id.hgr_subject


    def _compute_l10n_din5008_addresses(self):
        for record in self:
            record.l10n_din5008_addresses = data = []
            data.append((_("Objekt:"), record.so_line.order_id.partner_shipping_id))
            # data.append((_("Invoicing Address:"), record.partner_id))

    def _compute_l10n_din5008_template_data(self):
        for record in self:
            record.l10n_din5008_template_data = []

    def _compute_l10n_din5008_document_title(self):
        for record in self:
            record.l10n_din5008_document_title = 'Shaffaf'        