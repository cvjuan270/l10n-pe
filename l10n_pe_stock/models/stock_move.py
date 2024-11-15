from odoo import models


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _prepare_account_move_vals(self, credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost):
        # Heredamos el método que prepara los valores del asiento contable
        vals = super(StockMove, self)._prepare_account_move_vals(credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost)
        # Agregamos el kardex_account_date desde el picking relacionado
        if self.picking_id and self.picking_id.kardex_account_date:
            vals['kardex_account_date'] = self.picking_id.kardex_account_date

        return vals

