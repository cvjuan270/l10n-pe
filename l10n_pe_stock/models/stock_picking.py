from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    kardex_account_date = fields.Date(
        "Fecha Contable kardex",
        help="Fecha de la operación contable en el kardex para fistrar en las liblos contables de sunat",
    )
    l10n_pe_table_12_id = fields.Many2one(
        comodel_name="l10n_pe.table.12",
        string="Tipo de operacion",
        help="TABLA 12: TIPO DE OPERACIÓN - (sunat)",
    )

    def write(self, vals):
        res = super().write(vals)
        # Update kardex_account_date on  account.move
        if "kardex_account_date" in vals:
            account_moves = self.env["account.move"].search(
                [("stock_move_id", "in", self.move_ids.ids)]
            )
            for move in account_moves:
                move.kardex_account_date = vals["kardex_account_date"]
        # Update kardex_account_date on  stock.picking
        for record in self:
            if not record.kardex_account_date:
                record.kardex_account_date = fields.Date.context_today(self)
        return res
