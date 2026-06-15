from odoo import models


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _create_order_picking(self):
        """Defer the voucher of the inventory valuation entry.

        POS posts the valuation entry while validating the picking and only
        *afterwards* stamps ``pos_order_id``/``pos_session_id`` on that picking
        (see ``pos.order._create_order_picking`` in core). Resolving the voucher
        at ``_post`` would therefore land on the fallback ``account.move``
        voucher and burn a correlative. We skip it here; the session close
        assigns it once the links are in place.
        """
        return super(
            PosOrder, self.with_context(l10n_pe_skip_voucher_assign=True)
        )._create_order_picking()

    def _apply_invoice_payments(self, is_reverse=False):
        """Defer the voucher of the invoice-payment entry so it joins the
        voucher of the order it settles.

        The payment entry must share the order's voucher (invoice + valuation +
        payment). Its ``account_move`` is only guaranteed to be set by the time
        the session closes, so the close assigns it. When the order is invoiced
        *after* its session is already closed the close hook will not run again,
        so we assign the payment entries right away.
        """
        payment_moves = super(
            PosOrder, self.with_context(l10n_pe_skip_voucher_assign=True)
        )._apply_invoice_payments(is_reverse=is_reverse)
        closed = self.filtered(lambda order: order.session_id.state == "closed")
        if closed and payment_moves:
            payment_moves._l10n_pe_assign_vouchers()
        return payment_moves
