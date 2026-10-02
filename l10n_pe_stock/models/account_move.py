from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    kardex_account_date = fields.Date(
        string="Fecha Kardex",
        copy=False,
        readonly=True,
        help="Editar desde la entrega (stock.picking) ",
    )
