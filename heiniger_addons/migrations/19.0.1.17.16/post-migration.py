from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """File work reports that were attached before this version into the
    Documents folder of their project (tagged Timesheet + year)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    sheets = env['hgr.supervisor.timesheet'].search([('attachment_ids', '!=', False)])
    sheets._hgr_sync_work_report_documents()
