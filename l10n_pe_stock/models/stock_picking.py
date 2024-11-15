from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    account_date = fields.Dete("Fecha Contable")
    # invoice_id = fields.Many2one(
    #     comodel_name="account.move",
    #     string="Factura",
    #     domain="[('move_type','in',['out_invoice','out_refund','in_invoice','in_refund'])]",
    # )
