from odoo import models, fields, _
from odoo.tools import format_date


class BaseDocumentLayout(models.TransientModel):
	_inherit = 'base.document.layout'

	l10n_din5008_document_subject = fields.Char(compute='_compute_l10n_din5008_document_subject')


	def _compute_l10n_din5008_document_subject(self):
		self.l10n_din5008_document_subject = _('Subject')