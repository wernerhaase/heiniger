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


class ExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    def action_expense_cancel(self):
        for rec in self:
            if rec.sudo().mapped('expense_line_ids'):
                rec.mapped('expense_line_ids').sudo().write(
                    {'state': 'refused'})

            if rec.sudo().mapped('account_move_id'):
                line_ids = rec.sudo().mapped('account_move_id').mapped('line_ids')
                reconcile_ids = line_ids.sudo().mapped('id')
                reconcile_lines = self.env['account.partial.reconcile'].sudo().search(
                    ['|', ('credit_move_id', 'in', reconcile_ids), ('debit_move_id', 'in', reconcile_ids)])
                if reconcile_lines:
                    debit_account_move_list = reconcile_lines.mapped(
                        'debit_move_id').mapped('move_id')
                    credit_account_move_list = reconcile_lines.mapped(
                        'credit_move_id').mapped('move_id')
                    reconcile_lines.sudo().unlink()

                    for debit_move in debit_account_move_list:
                        debit_move.write({'state': 'draft', 'name': '/'})
                        debit_move.mapped('line_ids').sudo().write(
                            {'parent_state': 'draft'})
                        debit_move.mapped('line_ids').sudo().unlink()

                    for credit_move in credit_account_move_list:
                        credit_move.write({'state': 'draft', 'name': '/'})
                        credit_move.mapped('line_ids').sudo().write(
                            {'parent_state': 'draft'})
                        credit_move.mapped('line_ids').sudo().unlink()

                else:
                    rec.sudo().mapped('account_move_id').write(
                        {'state': 'draft', 'name': '/'})
                    rec.sudo().mapped('account_move_id').mapped(
                        'line_ids').sudo().write({'parent_state': 'draft'})
                    rec.sudo().mapped('account_move_id').mapped('line_ids').sudo().unlink()

            rec.sudo().write({'state': 'cancel'})

    def action_expense_cancel_draft(self):
        for rec in self:
            if rec.sudo().mapped('expense_line_ids'):
                rec.mapped('expense_line_ids').sudo().write({'state': 'draft'})

            if rec.sudo().mapped('account_move_id'):
                line_ids = rec.sudo().mapped('account_move_id').mapped('line_ids')
                reconcile_ids = line_ids.sudo().mapped('id')
                reconcile_lines = self.env['account.partial.reconcile'].sudo().search(
                    ['|', ('credit_move_id', 'in', reconcile_ids), ('debit_move_id', 'in', reconcile_ids)])
                if reconcile_lines:
                    debit_account_move_list = reconcile_lines.mapped(
                        'debit_move_id').mapped('move_id')
                    credit_account_move_list = reconcile_lines.mapped(
                        'credit_move_id').mapped('move_id')
                    reconcile_lines.sudo().unlink()

                    for debit_move in debit_account_move_list:
                        debit_move.write({'state': 'draft', 'name': '/'})
                        debit_move.mapped('line_ids').sudo().write(
                            {'parent_state': 'draft'})
                        debit_move.mapped('line_ids').sudo().unlink()

                    for credit_move in credit_account_move_list:
                        credit_move.write({'state': 'draft', 'name': '/'})
                        credit_move.mapped('line_ids').sudo().write(
                            {'parent_state': 'draft'})
                        credit_move.mapped('line_ids').sudo().unlink()

                else:
                    rec.sudo().mapped('account_move_id').write(
                        {'state': 'draft', 'name': '/'})
                    rec.sudo().mapped('account_move_id').mapped(
                        'line_ids').sudo().write({'parent_state': 'draft'})
                    rec.sudo().mapped('account_move_id').mapped('line_ids').sudo().unlink()

            rec.sudo().write({'state': 'draft'})

    def action_expense_cancel_delete(self):
        for rec in self:
            if rec.sudo().mapped('expense_line_ids'):
                rec.mapped('expense_line_ids').sudo().write(
                    {'state': 'refused'})
                rec.mapped('expense_line_ids').sudo().unlink()

            if rec.sudo().mapped('account_move_id'):
                line_ids = rec.sudo().mapped('account_move_id').mapped('line_ids')
                reconcile_ids = line_ids.sudo().mapped('id')
                reconcile_lines = self.env['account.partial.reconcile'].sudo().search(
                    ['|', ('credit_move_id', 'in', reconcile_ids), ('debit_move_id', 'in', reconcile_ids)])
                if reconcile_lines:
                    debit_account_move_list = reconcile_lines.mapped(
                        'debit_move_id').mapped('move_id')
                    credit_account_move_list = reconcile_lines.mapped(
                        'credit_move_id').mapped('move_id')
                    reconcile_lines.sudo().unlink()

                    for debit_move in debit_account_move_list:
                        debit_move.write({'state': 'draft', 'name': '/'})
                        debit_move.mapped('line_ids').sudo().write(
                            {'parent_state': 'draft'})
                        debit_move.mapped('line_ids').sudo().unlink()

                    for credit_move in credit_account_move_list:
                        credit_move.write({'state': 'draft', 'name': '/'})
                        credit_move.mapped('line_ids').sudo().write(
                            {'parent_state': 'draft'})
                        credit_move.mapped('line_ids').sudo().unlink()
                else:
                    rec.sudo().mapped('account_move_id').write(
                        {'state': 'draft', 'name': '/'})
                    rec.sudo().mapped('account_move_id').mapped(
                        'line_ids').sudo().write({'parent_state': 'draft'})
                    rec.sudo().mapped('account_move_id').mapped('line_ids').sudo().unlink()

            rec.sudo().write({'state': 'cancel'})
            rec.sudo().unlink()

    def sh_cancel(self):

        if self.sudo().mapped('expense_line_ids'):
            if self.company_id.expense_operation_type == 'cancel':
                self.mapped('expense_line_ids').sudo().write(
                    {'state': 'refused'})
            elif self.company_id.expense_operation_type == 'cancel_draft':
                self.mapped('expense_line_ids').sudo().write(
                    {'state': 'draft'})
            elif self.company_id.expense_operation_type == 'cancel_delete':
                self.mapped('expense_line_ids').sudo().write(
                    {'state': 'refused'})
                self.mapped('expense_line_ids').sudo().unlink()

        if self.sudo().mapped('account_move_id'):

            line_ids = self.sudo().mapped('account_move_id').mapped('line_ids')
            reconcile_ids = line_ids.sudo().mapped('id')
            reconcile_lines = self.env['account.partial.reconcile'].sudo().search(
                ['|', ('credit_move_id', 'in', reconcile_ids), ('debit_move_id', 'in', reconcile_ids)])
            if reconcile_lines:
                debit_account_move_list = reconcile_lines.mapped(
                    'debit_move_id').mapped('move_id')
                credit_account_move_list = reconcile_lines.mapped(
                    'credit_move_id').mapped('move_id')
                reconcile_lines.sudo().unlink()

                for debit_move in debit_account_move_list:
                    debit_move.write({'state': 'draft', 'name': '/'})
                    debit_move.mapped('line_ids').sudo().write(
                        {'parent_state': 'draft'})
                    debit_move.mapped('line_ids').sudo().unlink()
    #                 debit_move.sudo().with_context({'force_delete':True}).unlink()

                for credit_move in credit_account_move_list:
                    credit_move.write({'state': 'draft', 'name': '/'})
                    credit_move.mapped('line_ids').sudo().write(
                        {'parent_state': 'draft'})
                    credit_move.mapped('line_ids').sudo().unlink()
    #                 credit_move.sudo().with_context({'force_delete':True}).unlink()

            else:
                self.sudo().mapped('account_move_id').write(
                    {'state': 'draft', 'name': '/'})
                self.sudo().mapped('account_move_id').mapped(
                    'line_ids').sudo().write({'parent_state': 'draft'})
                self.sudo().mapped('account_move_id').mapped('line_ids').sudo().unlink()

        if self.company_id.expense_operation_type == 'cancel':
            self.sudo().write({'state': 'cancel'})
        elif self.company_id.expense_operation_type == 'cancel_draft':
            self.sudo().write({'state': 'draft'})
        elif self.company_id.expense_operation_type == 'cancel_delete':
            self.sudo().write({'state': 'cancel'})
            self.sudo().unlink()
            return {
                'name': 'Expense Report',
                'type': 'ir.actions.act_window',
                'res_model': 'hr.expense.sheet',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'target': 'current',
            }
