# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models


class Expense(models.Model):
    _inherit = 'hr.expense'

    def action_expense_cancel(self):
        for rec in self:
            rec.sudo().write({'state': 'refused'})

    def action_expense_cancel_draft(self):
        for rec in self:
            rec.sudo().write({'state': 'draft'})

    def action_expense_cancel_delete(self):
        for rec in self:
            rec.sudo().write({'state': 'refused'})
            rec.sudo().unlink()

    def sh_cancel(self):
        if self.company_id.expense_operation_type == 'cancel':
            self.sudo().write({'state': 'refused'})
        elif self.company_id.expense_operation_type == 'cancel_draft':
            self.sudo().write({'state': 'draft'})
        elif self.company_id.expense_operation_type == 'cancel_delete':
            self.sudo().write({'state': 'refused'})
            self.sudo().unlink()
            return {
                'name': 'Expense',
                'type': 'ir.actions.act_window',
                'res_model': 'hr.expense',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'target': 'current',
            }
