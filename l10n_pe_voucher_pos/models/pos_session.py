from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"

    def _validate_session(
        self,
        balancing_account=False,
        amount_to_balance=0,
        bank_payment_method_diffs=None,
    ):
        """Resolve every voucher of the session in a single pass at close.

        During the session each POS entry (inventory valuation, invoice,
        invoice payment) is posted with its voucher deferred, and the closing
        entry plus the cash/bank statement entries are created here. Only now
        are all the links (picking <-> order/session, order.account_move,
        statement_line.pos_session_id, ...) in place, so this is the single
        point where the whole operation can be grouped correctly -- without ever
        burning a fallback correlative.
        """
        res = super(
            self.with_context(l10n_pe_skip_voucher_assign=True)
        )._validate_session(
            balancing_account=balancing_account,
            amount_to_balance=amount_to_balance,
            bank_payment_method_diffs=bank_payment_method_diffs,
        )
        self._l10n_pe_assign_session_vouchers()
        return res

    def _l10n_pe_assign_session_vouchers(self):
        for session in self:
            session._l10n_pe_session_moves()._l10n_pe_assign_vouchers()

    def _l10n_pe_session_moves(self):
        """Every posted journal entry produced by this session: the closing
        entry, the order invoices and their invoice-payment entries, the
        cash/bank statement entries and the inventory valuation entries of the
        session's pickings."""
        self.ensure_one()
        Move = self.env["account.move"]
        moves = self.move_id
        moves |= self.order_ids.account_move
        moves |= self.order_ids.payment_ids.account_move_id
        moves |= self.statement_line_ids.move_id
        stock_moves = (self.picking_ids | self.order_ids.picking_ids).move_ids
        if stock_moves:
            moves |= Move.search(
                [("stock_move_id", "in", stock_moves.ids), ("state", "=", "posted")]
            )
        return moves.filtered(lambda move: move.state == "posted")
