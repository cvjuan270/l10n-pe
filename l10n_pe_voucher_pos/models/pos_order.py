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

        We loop order by order instead of calling ``super()`` once for the whole
        recordset because the moves returned by
        ``pos.order._apply_invoice_payments`` carry no back-link to the order
        that produced them, and only the orders of an *already closed* session
        may be assigned here (the ones still open must keep deferring to the
        session close). Iterating is the correlation: it is also what core does
        anyway -- ``_generate_pos_order_invoice`` calls this method one order at
        a time, and the core implementation is single-record by construction
        (it reads ``self.partner_id`` / ``self.account_move``).

        The assignment must reset ``l10n_pe_skip_voucher_assign``: the moves
        inherit the environment of the ``super()`` call above, whose context
        carries the flag that makes ``_l10n_pe_assign_vouchers`` a no-op. Same
        pattern as ``pos.session._l10n_pe_assign_session_vouchers``.
        """
        payment_moves = self.env["account.move"]
        for order in self:
            order_moves = super(
                PosOrder, order.with_context(l10n_pe_skip_voucher_assign=True)
            )._apply_invoice_payments(is_reverse=is_reverse)
            if order_moves and order.session_id.state == "closed":
                order_moves.with_context(
                    l10n_pe_skip_voucher_assign=False
                )._l10n_pe_assign_vouchers()
            payment_moves |= order_moves
        # Returned in the caller's own environment, so the skip flag does not
        # leak into what core does next with these moves (reversal entry).
        return payment_moves
