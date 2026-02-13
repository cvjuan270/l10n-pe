from odoo import fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    account_entry_target = fields.Boolean(
        "Tiene Asiento Contable de Destino", default=False
    )
    acccount_debit_target = fields.Many2one(
        "account.account", string="Cuenta de destino Débito"
    )
    acccount_credit_target = fields.Many2one(
        "account.account", string="Cuenta de destino Crédito"
    )
