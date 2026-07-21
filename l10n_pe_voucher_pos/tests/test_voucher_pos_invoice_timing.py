"""Regression tests for the voucher (CUO) of the POS invoice-payment entry.

``pos.order._apply_invoice_payments`` used to wrap ``super()`` in a
``l10n_pe_skip_voucher_assign=True`` context and then assign the vouchers on the
returned moves *within that very context*, so the assignment was a no-op: an
order invoiced AFTER its session had been closed -- the case where the session
close hook will never run again -- kept its payment entry without any voucher.

The two tests below pin the corrected timing:

* session still open  -> the payment entry is deferred (no voucher yet) and gets
  the order voucher at session close;
* session already closed -> the payment entry gets the order voucher right away.
"""

from odoo import tests

from odoo.addons.l10n_pe_voucher.tests.common import L10nPeVoucherTestMixin
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tests.tagged("post_install", "-at_install")
class TestVoucherPosInvoiceTiming(L10nPeVoucherTestMixin, TestPoSCommon):
    def setUp(self):
        super().setUp()
        self.config = self.basic_config
        self.product = self.create_product(
            "Voucher Timing Product", self.categ_basic, 100.0, 50.0
        )
        # The client database requires every contact to hold an identification
        # document; give the POS customer a coherent Peruvian one.
        self.customer.write(self._l10n_pe_partner_vals(self.customer.name))

    # -- helpers --------------------------------------------------------------
    def _close_session(self, session):
        cash_pm = session.payment_method_ids.filtered("is_cash_count")[:1]
        total_cash = sum(
            session.mapped("order_ids.payment_ids")
            .filtered(lambda p: p.payment_method_id == cash_pm)
            .mapped("amount")
        )
        session.post_closing_cash_details(total_cash)
        session.close_session_from_ui()

    def _payment_moves(self, order):
        """The invoice-payment entries of an order (F-POS journal)."""
        return order.payment_ids.account_move_id.filtered(
            lambda move: move.state == "posted"
        )

    def _order_voucher(self, order):
        return self.env["l10n.pe.voucher"].search(
            [
                ("company_id", "=", order.company_id.id),
                ("l10n_pe_origin_model", "=", "pos.order"),
                ("l10n_pe_origin_res_id", "=", order.id),
            ]
        )

    # -- tests ----------------------------------------------------------------
    def test_invoice_after_session_close_assigns_payment_voucher(self):
        """THE fix: an order invoiced once its session is already closed must
        end up with its invoice-payment entry stamped with the order voucher.

        Before the fix these lines stayed at ``l10n_pe_voucher_id = False``
        forever: the session close hook does not run a second time.
        """
        session = self._start_pos_session(self.cash_pm1, 0)
        orders = self._create_orders(
            [
                {
                    "pos_order_lines_ui_args": [(self.product, 1)],
                    "payments": [(self.cash_pm1, 100)],
                    "customer": self.customer,
                    "is_invoiced": False,
                    "uuid": "00100-020-0001",
                }
            ]
        )
        order = orders["00100-020-0001"]
        self.assertFalse(order.account_move, "not invoiced during the session")

        self._close_session(session)
        self.assertEqual(session.state, "closed")

        # Now the customer asks for the invoice, session already closed.
        order.action_pos_order_invoice()
        self.assertTrue(order.account_move, "the order is invoiced now")

        payment_moves = self._payment_moves(order)
        self.assertTrue(payment_moves, "the invoice-payment entry exists")

        order_voucher = self._order_voucher(order)
        self.assertEqual(len(order_voucher), 1, "the order owns a single voucher")

        payment_lines = payment_moves.line_ids
        self.assertTrue(payment_lines, "the payment entry has journal items")
        # ``mapped`` on a many2one returns the *union* recordset, so
        # ``all(...)`` would be vacuously true when nothing is assigned: count
        # the lines left without a voucher instead.
        self.assertFalse(
            payment_lines.filtered(lambda line: not line.l10n_pe_voucher_id),
            "every journal item of the invoice-payment entry carries a voucher",
        )
        self.assertEqual(
            payment_lines.l10n_pe_voucher_id,
            order_voucher,
            "the invoice-payment entry shares the pos.order voucher",
        )
        # The invoice itself is on the same CUO.
        self.assertEqual(
            order.account_move.line_ids.l10n_pe_voucher_id,
            order_voucher,
            "invoice and its payment entry share one CUO",
        )

    def test_invoice_with_open_session_defers_payment_voucher(self):
        """Complementary case: while the session is open the payment entry must
        NOT be numbered at once (it is deferred to the session close, which is
        the single authoritative pass)."""
        session = self._start_pos_session(self.cash_pm1, 0)
        orders = self._create_orders(
            [
                {
                    "pos_order_lines_ui_args": [(self.product, 1)],
                    "payments": [(self.cash_pm1, 100)],
                    "customer": self.customer,
                    "is_invoiced": True,
                    "uuid": "00100-020-0002",
                }
            ]
        )
        order = orders["00100-020-0002"]
        self.assertEqual(session.state, "opened")
        self.assertTrue(order.account_move, "invoiced while the session is open")

        payment_moves = self._payment_moves(order)
        self.assertTrue(payment_moves, "the invoice-payment entry exists")
        self.assertFalse(
            payment_moves.line_ids.l10n_pe_voucher_id,
            "the invoice-payment entry is deferred while the session is open",
        )

        self._close_session(session)

        order_voucher = self._order_voucher(order)
        self.assertEqual(len(order_voucher), 1)
        self.assertEqual(
            payment_moves.line_ids.l10n_pe_voucher_id,
            order_voucher,
            "the session close assigns the order voucher to the payment entry",
        )
        self.assertFalse(
            self.env["account.move"]._l10n_pe_moves_to_backfill(),
            "no posted entry of the session is left without a voucher",
        )
