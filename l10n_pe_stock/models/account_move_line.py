from odoo import models, fields

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    kardex_account_date = fields.Date(
        related='move_id.kardex_account_date',
        store=True,
        string='Fecha Kardex'
    )
