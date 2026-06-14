from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestL10nPeVoucher(AccountTestInvoicingCommon):
    """Unit tests for the voucher (CUO) assignment of l10n_pe_voucher."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.misc_journal = cls.company_data["default_journal_misc"]
        cls.account_a = cls.company_data["default_account_revenue"]
        cls.account_b = cls.company_data["default_account_expense"]

    # -- helpers --------------------------------------------------------------
    def _new_misc_move(self, amount=100.0):
        """A balanced miscellaneous journal entry (no source document)."""
        return self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "line_ids": [
                    Command.create(
                        {"account_id": self.account_a.id, "debit": amount, "credit": 0.0, "name": "t"}
                    ),
                    Command.create(
                        {"account_id": self.account_b.id, "debit": 0.0, "credit": amount, "name": "t"}
                    ),
                ],
            }
        )

    # -- tests ----------------------------------------------------------------
    def test_fallback_single_voucher_per_move(self):
        """A move with no source document: every line shares one voucher whose
        origin is the move itself."""
        move = self._new_misc_move()
        self.assertFalse(move.line_ids.l10n_pe_voucher_id, "no voucher before posting")

        move.action_post()

        vouchers = move.line_ids.l10n_pe_voucher_id
        self.assertEqual(len(vouchers), 1, "all lines on a single voucher")
        self.assertEqual(vouchers.l10n_pe_origin_model, "account.move")
        self.assertEqual(vouchers.l10n_pe_origin_res_id, move.id)
        self.assertEqual(vouchers.company_id, move.company_id)

    def test_sequence_is_gapless_per_company(self):
        """Consecutive vouchers get a continuous, zero-padded correlative."""
        first = self._new_misc_move()
        first.action_post()
        second = self._new_misc_move()
        second.action_post()

        name_1 = first.line_ids.l10n_pe_voucher_id.name
        name_2 = second.line_ids.l10n_pe_voucher_id.name
        self.assertEqual(len(name_1), 8, "padding of 8 digits")
        self.assertEqual(int(name_2), int(name_1) + 1, "gap-less correlative")

    def test_origin_dedup_reuses_voucher(self):
        """The same origin must always resolve to the same voucher record."""
        Voucher = self.env["l10n.pe.voucher"]
        company = self.env.company
        v1 = Voucher._l10n_pe_get_or_create(company, "purchase.order", 999999)
        v2 = Voucher._l10n_pe_get_or_create(company, "purchase.order", 999999)
        v3 = Voucher._l10n_pe_get_or_create(company, "purchase.order", 888888)
        self.assertEqual(v1, v2, "same origin reuses the voucher")
        self.assertNotEqual(v1, v3, "different origin creates a new voucher")

    def test_invoice_without_order_single_voucher(self):
        """A plain customer invoice (no sale order) groups all of its lines
        -- product, tax and receivable -- under one voucher."""
        invoice = self.init_invoice(
            "out_invoice", products=self.product_a, taxes=self.tax_sale_a, post=True
        )
        vouchers = invoice.line_ids.l10n_pe_voucher_id
        self.assertEqual(len(vouchers), 1)
        self.assertEqual(vouchers.l10n_pe_origin_res_id, invoice.id)
        # Receivable and tax lines (no own origin) follow the same voucher.
        self.assertTrue(all(invoice.line_ids.mapped("l10n_pe_voucher_id")))

    def test_payment_inherits_invoice_voucher(self):
        """Registering a payment moves the payment entry onto the invoice's
        voucher and drops the provisional fallback voucher."""
        invoice = self.init_invoice(
            "out_invoice", products=self.product_a, taxes=self.tax_sale_a, post=True
        )
        invoice_voucher = invoice.line_ids.l10n_pe_voucher_id

        payment = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({})
            ._create_payments()
        )

        pay_vouchers = payment.move_id.line_ids.l10n_pe_voucher_id
        self.assertEqual(pay_vouchers, invoice_voucher, "payment shares the invoice voucher")
        self.assertEqual(len(pay_vouchers), 1)
        # The provisional fallback voucher of the payment must be gone.
        stale = self.env["l10n.pe.voucher"].search(
            [("l10n_pe_origin_model", "=", "account.move"),
             ("l10n_pe_origin_res_id", "=", payment.move_id.id)]
        )
        self.assertFalse(stale, "fallback voucher cleaned up")

    def test_payment_of_several_vouchers_keeps_own(self):
        """A single payment settling invoices that belong to different vouchers
        keeps its own voucher (ambiguous grouping is not merged)."""
        inv1 = self.init_invoice("out_invoice", products=self.product_a, post=True)
        inv2 = self.init_invoice("out_invoice", products=self.product_a, post=True)
        self.assertNotEqual(
            inv1.line_ids.l10n_pe_voucher_id, inv2.line_ids.l10n_pe_voucher_id
        )

        payment = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=(inv1 + inv2).ids)
            .create({"group_payment": True})
            ._create_payments()
        )

        pay_vouchers = payment.move_id.line_ids.l10n_pe_voucher_id
        self.assertEqual(len(pay_vouchers), 1, "payment stays on a single voucher")
        self.assertEqual(
            pay_vouchers.l10n_pe_origin_model, "account.move",
            "payment keeps its own fallback voucher",
        )
        self.assertEqual(pay_vouchers.l10n_pe_origin_res_id, payment.move_id.id)
