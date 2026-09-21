from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    analytic_account_journal_target_id = fields.Many2one(
        "account.journal",
        string="Diario de cuentas destino",
        help="Diario para la creación de asientos contables de "
        "cuentas analíticas objetivo",
    )
