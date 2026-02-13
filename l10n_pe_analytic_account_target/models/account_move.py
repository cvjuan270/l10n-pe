from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    origin_move_id = fields.Many2one(
        "account.move", string="Asiento contable origen", copy=False
    )
    origin_move_line_id = fields.Many2one(
        "account.move.line", string="Linea de asiento contable origen", copy=False
    )
    origin_analytic_line_id = fields.Many2one(
        "account.analytic.line", string="Linea de cuenta analítica origen", copy=False
    )

    target_move_count = fields.Integer(
        "Target move count", compute="_compute_count_target_move"
    )
    target_move_ids = fields.One2many(
        "account.move", "origin_move_id", string="Asiento contable destino", copy=False
    )

    def _compute_count_target_move(self):
        for record in self:
            record.target_move_count = self.env["account.move"].search_count(
                [("origin_move_id", "=", record.id)]
            )

    def open_analytic_line_form(self):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "analytic.account_analytic_line_action_entries"
        )
        action["view_mode"] = "form"
        action["res_id"] = self.origin_analytic_line_id.id
        action["views"] = [[False, "form"]]
        return action

    def open_account_move_form_origin(self):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "account.action_move_journal_line"
        )
        action["view_mode"] = "form"
        action["res_id"] = self.origin_move_id.id
        action["views"] = [[False, "form"]]
        return action

    def open_destination_move_view(self):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "account.action_move_line_form"
        )
        action["domain"] = [("id", "in", self.target_move_ids.ids)]
        action["name"] = "Asientos contables destino"
        return action


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    origin_move_id = fields.Many2one(
        "account.move", string="Asiento contable origen", copy=False
    )
    origin_move_line_id = fields.Many2one(
        "account.move.line", string="Apunte contable origen", copy=False
    )
