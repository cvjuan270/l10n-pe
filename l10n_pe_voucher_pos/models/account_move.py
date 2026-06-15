from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_pe_voucher_move_key(self):
        """Resolve the operation of a Point of Sale journal entry.

        Grouping rule:
        * an invoiced order maps to its ``pos.order`` (so the invoice and the
          inventory valuation of that order share one voucher);
        * everything that is not invoiced maps to its ``pos.session`` -- the
          session closing entry summarises many orders and is a single
          accounting operation, and the valuations of its non-invoiced orders
          join it.
        """
        self.ensure_one()

        # POS order invoice.
        if self.pos_order_ids:
            return ("pos.order", self.pos_order_ids[:1].id)
        # POS session closing entry.
        if self.pos_session_ids:
            return ("pos.session", self.pos_session_ids[:1].id)
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
