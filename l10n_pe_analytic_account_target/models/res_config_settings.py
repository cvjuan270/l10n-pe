from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    analytic_account_journal_target_id = fields.Many2one(
        "account.journal",
        related="company_id.analytic_account_journal_target_id",
        readonly=False,
        required=True,
        domain="[('type', '=', 'general')]",
        string="Diario de asientos de destino",
        help="Diario para la creación de asientos contables "
        "de cuentas analíticas destino",
    )
