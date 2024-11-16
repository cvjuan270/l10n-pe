from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    kardex_account_date = fields.Date(
        string='Fecha Kardex',
        copy=False
    )
