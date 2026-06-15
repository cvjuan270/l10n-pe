from odoo import tests

from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tests.tagged("post_install", "-at_install")
class TestVoucherPos(TestPoSCommon):
    """Voucher (CUO) resolution for Point of Sale entries."""

    def setUp(self):
        super().setUp()
        self.config = self.basic_config
        self.product = self.create_product(
            "Voucher Product", self.categ_basic, 100.0, 50.0
        )

    def _close_session(self, session):
        cash_pm = session.payment_method_ids.filtered("is_cash_count")[:1]
        total_cash = sum(
            session.mapped("order_ids.payment_ids")
            .filtered(lambda p: p.payment_method_id == cash_pm)
            .mapped("amount")
        )
        session.post_closing_cash_details(total_cash)
        session.close_session_from_ui()

    def test_pos_invoice_and_session_vouchers(self):
        """An invoiced order is grouped under its pos.order voucher; the session
        closing entry is grouped under its pos.session voucher. No entry is left
        without a voucher."""
        session = self._start_pos_session(self.cash_pm1, 0)
        orders = self._create_orders(
            [
                {
                    "pos_order_lines_ui_args": [(self.product, 1)],
                    "payments": [(self.cash_pm1, 100)],
                    "customer": self.customer,
                    "is_invoiced": True,
                    "uuid": "00100-010-0001",
                },
                {
                    "pos_order_lines_ui_args": [(self.product, 2)],
                    "payments": [(self.cash_pm1, 200)],
                    "customer": self.customer,
                    "is_invoiced": False,
                    "uuid": "00100-010-0002",
                },
            ]
        )

        # Invoiced order -> its invoice is grouped under the pos.order voucher.
        invoiced = orders["00100-010-0001"]
        self.assertTrue(invoiced.account_move, "invoiced order has an invoice")
        inv_voucher = invoiced.account_move.line_ids.l10n_pe_voucher_id
        self.assertEqual(len(inv_voucher), 1)
        self.assertEqual(inv_voucher.l10n_pe_origin_model, "pos.order")
        self.assertEqual(inv_voucher.l10n_pe_origin_res_id, invoiced.id)

        self._close_session(session)

        # Session closing entry -> grouped under the pos.session voucher.
        self.assertTrue(session.move_id, "session has a closing entry")
        sess_voucher = session.move_id.line_ids.l10n_pe_voucher_id
        self.assertEqual(len(sess_voucher), 1, "single voucher on the session entry")
        self.assertEqual(sess_voucher.l10n_pe_origin_model, "pos.session")
        self.assertEqual(sess_voucher.l10n_pe_origin_res_id, session.id)

        # No posted entry of this session is left without a voucher.
        self.assertFalse(
            self.env["account.move"]._l10n_pe_moves_to_backfill(),
            "no posted entry without a voucher",
        )
