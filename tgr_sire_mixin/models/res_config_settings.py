from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sire_client_id = fields.Char(
        related="company_id.sire_client_id",
        readonly=False,
    )
    sire_client_secret = fields.Char(
        related="company_id.sire_client_secret",
        readonly=False,
        groups="account.group_account_manager",
    )
    sire_sol_username = fields.Char(
        related="company_id.sire_sol_username",
        readonly=False,
    )
    sire_sol_password = fields.Char(
        related="company_id.sire_sol_password",
        readonly=False,
        groups="account.group_account_manager",
    )
    sire_state = fields.Selection(related="company_id.sire_state")

    def action_sire_test_connection(self):
        self.ensure_one()
        return self.company_id.action_sire_test_connection()
