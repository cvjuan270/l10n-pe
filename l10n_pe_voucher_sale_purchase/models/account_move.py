from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_pe_voucher_move_key(self):
        """Resolve the operation of an inventory valuation move.

        A stock valuation entry carries ``stock_move_id``; through it we reach
        the purchase/sale order that originated the movement, so the valuation
        move and the bill/invoice of that order end up under the same voucher.
        """
        self.ensure_one()
        stock_move = self.stock_move_id
        if stock_move:
            if stock_move.purchase_line_id:
                return ("purchase.order", stock_move.purchase_line_id.order_id.id)
            if stock_move.sale_line_id:
                return ("sale.order", stock_move.sale_line_id.order_id.id)
        return super()._l10n_pe_voucher_move_key()
