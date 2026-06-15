from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_pe_voucher_move_key(self):
        """Resolve the operation of a Point of Sale journal entry.

        Grouping rule:
        * an invoiced order maps to its ``pos.order`` (so the invoice, its
          inventory valuation and its invoice-payment entry share one voucher);
        * everything that is not invoiced maps to its ``pos.session`` -- the
          session closing entry summarises many orders and is a single
          accounting operation, and the valuations of its non-invoiced orders
          and the session's cash/bank statement entries join it.
        """
        self.ensure_one()

        # POS order invoice.
        if self.pos_order_ids:
            return ("pos.order", self.pos_order_ids[:1].id)
        # POS session closing entry.
        if self.pos_session_ids:
            return ("pos.session", self.pos_session_ids[:1].id)
        # POS cash/bank statement entry -> its session.
        statement_line = self.statement_line_id
        if (
            statement_line
            and "pos_session_id" in statement_line._fields
            and statement_line.pos_session_id
        ):
            return ("pos.session", statement_line.pos_session_id.id)
        # POS invoice-payment entry -> the order it settles (invoiced) or its
        # session. POS links it through ``pos.payment`` (the inverse field is
        # ``pos_payment_ids`` on the move).
        if self.pos_payment_ids:
            order = self.pos_payment_ids[:1].pos_order_id
            if order:
                if order.account_move:
                    return ("pos.order", order.id)
                if order.session_id:
                    return ("pos.session", order.session_id.id)
                return ("pos.order", order.id)
        # POS inventory valuation move -> the order (if invoiced) or the session.
        if self._fields.get("stock_move_id") and self.stock_move_id:
            picking = self.stock_move_id.picking_id
            order = picking.pos_order_id if "pos_order_id" in picking._fields else False
            if order and order.account_move:
                return ("pos.order", order.id)
            session = (
                picking.pos_session_id if "pos_session_id" in picking._fields else False
            )
            if session:
                return ("pos.session", session.id)
            if order:
                return ("pos.order", order.id)

        return super()._l10n_pe_voucher_move_key()
