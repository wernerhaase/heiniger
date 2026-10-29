from odoo import api, fields, models, Command, _
from odoo.exceptions import AccessError, ValidationError


class HgrWorkCategory(models.Model):
    _name = 'hgr.work.category'
    _description = 'Work Category'
    _order = 'name'

    name = fields.Char(required=True, translate=True, index='trigram')
    active = fields.Boolean(default=True)
    color = fields.Integer()

class HgrSupervisorTimesheet(models.Model):
    _name = 'hgr.supervisor.timesheet'
    _description = 'Supervisor Timesheet Entry'
    _order = 'date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, ondelete='restrict')
    project_id = fields.Many2one(
        'project.project', required=True, ondelete='restrict',
        domain="[('partner_id', '=', partner_id), ('allow_timesheets', '=', True), ('is_template', '=', False)]",
    )
    supervisor_id = fields.Many2one('hr.employee', required=True, ondelete='restrict')
    date = fields.Date(required=True, default=fields.Date.context_today)
    description = fields.Text(string='Overall Description')
    line_ids = fields.One2many('hgr.supervisor.timesheet.line', 'sheet_id', string='Worker Lines')
    timesheet_ids = fields.One2many('account.analytic.line', 'hgr_supervisor_sheet_id', string='Timesheets')
    company_id = fields.Many2one(related='project_id.company_id', store=True)

    @api.depends('date', 'project_id')
    def _compute_name(self):
        for sheet in self:
            sheet.name = _('%(date)s - %(project)s',
                date=sheet.date or '', project=sheet.project_id.display_name or '')

    @api.model
    def _check_supervisor_access(self):
        if not self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver'):
            raise AccessError(_('Only timesheet approvers can enter time for other workers.'))

    @api.model
    def get_entry_defaults(self):
        self._check_supervisor_access()
        employee = self.env.user.employee_id
        return {
            'date': fields.Date.context_today(self),
            'supervisor_id': employee.id or False,
            'company_id': self.env.company.id,
        }

    @api.model
    def _get_project_service_sale_lines(self, project):
        orders = project.sudo()._hgr_profitability_sale_orders()
        return orders.order_line.filtered(
            lambda line: (
                not line.display_type
                and line.product_id.type == 'service'
                and line.order_id.state != 'cancel'
            )
        )

    @api.model
    def get_service_sale_lines(self, project_id):
        """Return service SO lines available to the supervisor entry screen."""
        self._check_supervisor_access()
        project = self.env['project.project'].browse(project_id).exists()
        if not project:
            return []
        project.check_access('read')
        if project.company_id and project.company_id != self.env.company:
            return []
        return [
            {
                'id': line.id,
                'name': line.display_name,
                'work_category_id': line.hgr_work_category_id.id or False,
            }
            for line in self._get_project_service_sale_lines(project)
        ]

    @api.model
    def create_from_ui(self, payload):
        self._check_supervisor_access()
        if not isinstance(payload, dict):
            raise ValidationError(_('Invalid timesheet data.'))

        partner = self.env['res.partner'].browse(payload.get('partner_id')).exists()
        project = self.env['project.project'].browse(payload.get('project_id')).exists()
        supervisor = self.env['hr.employee'].browse(payload.get('supervisor_id')).exists()
        date = fields.Date.to_date(payload.get('date'))
        raw_lines = payload.get('lines') or []
        if not partner or not project or not supervisor or not date:
            raise ValidationError(_('Customer, project, supervisor, and date are required.'))
        if not project.allow_timesheets or project.is_template:
            raise ValidationError(_('Please select a project that allows timesheets.'))
        if not project.partner_id or project.partner_id.commercial_partner_id != partner.commercial_partner_id:
            raise ValidationError(_('The selected project does not belong to this customer.'))
        if not raw_lines:
            raise ValidationError(_('Add at least one worker line.'))

        allowed_sale_lines = self._get_project_service_sale_lines(project)
        line_commands = []
        employee_service_pairs = set()
        for raw_line in raw_lines:
            employee = self.env['hr.employee'].browse(raw_line.get('employee_id')).exists()
            sale_line = self.env['sale.order.line'].sudo().browse(
                raw_line.get('sale_line_id')
            ).exists()
            work_category = self.env['hgr.work.category'].browse(
                raw_line.get('work_category_id')
            ).exists()
            manual_service_name = (raw_line.get('manual_service_name') or '').strip()
            try:
                hours = float(raw_line.get('unit_amount') or 0)
            except (TypeError, ValueError):
                hours = 0
            description = (raw_line.get('name') or '').strip()
            if (
                not employee
                or (not sale_line and not manual_service_name)
                or not work_category
                or hours <= 0
                or not description
            ):
                raise ValidationError(_(
                    'Every line needs a worker, service, work category, positive hours, and a work description.'
                ))
            if sale_line and sale_line not in allowed_sale_lines:
                raise ValidationError(_(
                    'The selected service must be a service item from a sales order linked to this project.'
                ))
            if sale_line:
                manual_service_name = ''
            if hours > 24:
                raise ValidationError(_('Hours cannot exceed 24 for one worker.'))
            service_key = sale_line.id or f'manual:{manual_service_name.casefold()}'
            employee_service = (employee.id, service_key)
            if employee_service in employee_service_pairs:
                raise ValidationError(_('Each worker and service combination can only appear once.'))
            if project.company_id and employee.company_id != project.company_id:
                raise ValidationError(_('The worker and project must belong to the same company.'))
            employee_service_pairs.add(employee_service)
            line_commands.append(Command.create({
                'employee_id': employee.id,
                'sale_line_id': sale_line.id,
                'manual_service_name': manual_service_name,
                'work_category_id': work_category.id,
                'unit_amount': hours,
                'name': description,
            }))

        sheet = self.create({
            'partner_id': partner.id,
            'project_id': project.id,
            'supervisor_id': supervisor.id,
            'date': date,
            'description': (payload.get('description') or '').strip(),
            'line_ids': line_commands,
        })
        for line in sheet.line_ids:
            line.timesheet_id = self.env['account.analytic.line'].create({
                'date': sheet.date,
                'project_id': sheet.project_id.id,
                'employee_id': line.employee_id.id,
                'so_line': line.sale_line_id.id or False,
                'is_so_line_edited': bool(line.sale_line_id),
                'hgr_manual_service_name': line.manual_service_name,
                'hgr_work_category_id': line.work_category_id.id,
                'unit_amount': line.unit_amount,
                'name': line.name,
                'hgr_supervisor_sheet_id': sheet.id,
            })
        return {'id': sheet.id, 'count': len(sheet.line_ids)}


class HgrSupervisorTimesheetLine(models.Model):
    _name = 'hgr.supervisor.timesheet.line'
    _description = 'Supervisor Timesheet Worker Line'
    _order = 'id'

    sheet_id = fields.Many2one('hgr.supervisor.timesheet', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Worker', required=True, ondelete='restrict')
    sale_line_id = fields.Many2one(
        'sale.order.line', string='Service', ondelete='restrict'
    )
    manual_service_name = fields.Char(string='Manual Service')
    work_category_id = fields.Many2one(
        'hgr.work.category', string='Work Category',
        ondelete='restrict', index=True,
    )
    unit_amount = fields.Float(string='Time (Hours)', required=True)
    name = fields.Char(string='Work Description', required=True)
    timesheet_id = fields.Many2one('account.analytic.line', readonly=True, ondelete='set null')

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    hgr_profitability_manual_type = fields.Selection(
        [('labour', 'Labour')],
        string='Manual Profitability Type', readonly=True, index=True,
    )
    hgr_profitability_manual_user_id = fields.Many2one(
        'res.users', string='Manual Entry By', readonly=True,
    )
    hgr_manual_service_name = fields.Char(
        string='Manual Service', readonly=True, index=True,
    )
    hgr_work_category_id = fields.Many2one(
        'hgr.work.category', string='Work Category', ondelete='restrict', index=True,
    )

    hgr_supervisor_sheet_id = fields.Many2one(
        'hgr.supervisor.timesheet', string='Supervisor Entry', readonly=True,
        ondelete='set null', index=True,
    )

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
