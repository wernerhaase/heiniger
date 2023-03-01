
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class Task(models.Model):
	_inherit = 'project.task'

	employee_ids = fields.Many2many('hr.employee', relation='project_task_employee_rel', column1='task_id', column2='employee_id', string='Employees', context={'active_test': False}, tracking=True)