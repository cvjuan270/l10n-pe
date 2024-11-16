from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    kardex_account_date = fields.Date("Fecha Contable")
    # invoice_id = fields.Many2one(
    #     comodel_name="account.move",
    #     string="Factura",
    #     domain="[('move_type','in',['out_invoice','out_refund','in_invoice','in_refund'])]",
    # )
    l10n_pe_table_12_id = fields.Many2one(
        comodel_name="l10n_pe.table.12",
        string="Tipo de operacion",
        help="TABLA 12: TIPO DE OPERACIÓN - (sunat)",
    )

    def write(self, vals):
        # uptade kardex_account_date with date_done on write
        res = super().write(vals)
        if "date_done" in vals:
            for record in self:
                record.kardex_account_date = record.date_done
        return res
