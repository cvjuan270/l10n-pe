from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _l10n_pe_voucher_line_key(self):
        """Resolve the operation of a vendor bill / customer invoice line.

        The line is tied to its purchase or sale order line, which lets a
        consolidated move spanning several orders split into one voucher per
        order while a regular bill/invoice keeps a single voucher.
        """
        self.ensure_one()
        if self.purchase_line_id:
            return ("purchase.order", self.purchase_line_id.order_id.id)
        if self.sale_line_ids:
            orders = self.sale_line_ids.order_id
            if len(orders) == 1:
                return ("sale.order", orders.id)
        return super()._l10n_pe_voucher_line_key()
