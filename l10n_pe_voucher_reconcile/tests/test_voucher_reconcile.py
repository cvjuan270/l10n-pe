from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestVoucherReconcile(AccountTestInvoicingCommon):
    """Voucher (CUO) resolution for payment and bank/cash statement entries."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data["default_journal_bank"]

    # -- helpers --------------------------------------------------------------
    def _invoice(self):
        return self.init_invoice(
            "out_invoice", products=self.product_a, taxes=self.tax_sale_a, post=True
        )

    def _register_payment(self, invoices, **ctx_vals):
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoices.ids)
            .create(ctx_vals)
        )
        return wizard._create_payments()

    def _own_vouchers_of(self, move):
        return self.env["l10n.pe.voucher"].search(
            [("l10n_pe_origin_model", "=", "account.move"),
             ("l10n_pe_origin_res_id", "=", move.id)]
        )

    # -- tests ----------------------------------------------------------------
    def test_payment_shares_invoice_voucher_no_orphan(self):
        """Registering a payment makes the payment entry share the invoice
        voucher and creates no orphan voucher for the payment move."""
        invoice = self._invoice()
        invoice_voucher = invoice.line_ids.l10n_pe_voucher_id
        self.assertEqual(len(invoice_voucher), 1)

        payment = self._register_payment(invoice)

        pay_voucher = payment.move_id.line_ids.l10n_pe_voucher_id
        self.assertEqual(pay_voucher, invoice_voucher, "payment shares invoice voucher")
        self.assertEqual(len(pay_voucher), 1)
        self.assertFalse(
            self._own_vouchers_of(payment.move_id),
            "no orphan voucher created for the payment move",
        )

    def test_reconciliation_does_not_skip_correlatives(self):
        """Posting/reconciling a payment must not burn a voucher number: the
        gap-less correlative stays continuous across payments."""
        inv_a = self._invoice()
        inv_b = self._invoice()
        name_a = int(inv_a.line_ids.l10n_pe_voucher_id.name)
        name_b = int(inv_b.line_ids.l10n_pe_voucher_id.name)
        self.assertEqual(name_b, name_a + 1, "invoices get consecutive vouchers")

        # Pay invoice A: this must NOT consume a correlative.
        self._register_payment(inv_a)

        inv_c = self._invoice()
        name_c = int(inv_c.line_ids.l10n_pe_voucher_id.name)
        self.assertEqual(
            name_c, name_b + 1,
            "the payment between B and C did not skip a correlative",
        )

    def test_payment_anchors_on_reconciled_line_not_whole_invoice(self):
        """When the settled document spans several vouchers (e.g. a consolidated
        bill across purchase orders), the payment must adopt the voucher of the
        line it actually reconciles (receivable/payable), not fall into the
        ambiguous branch because of the document's other vouchers."""
        invoice = self._invoice()
        receivable = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        receivable_voucher = receivable.l10n_pe_voucher_id
        self.assertEqual(len(receivable_voucher), 1)

        # Simulate a multi-operation document: put a non-reconciled line on a
        # different voucher so the invoice carries more than one voucher.
        extra = self.env["l10n.pe.voucher"]._l10n_pe_get_or_create(
            invoice.company_id, "account.move", invoice.id + 10_000_000
        )
        (invoice.line_ids - receivable)[:1].l10n_pe_voucher_id = extra
        self.assertGreater(
            len(invoice.line_ids.l10n_pe_voucher_id), 1, "invoice spans >1 voucher"
        )

        payment = self._register_payment(invoice)

        pay_voucher = payment.move_id.line_ids.l10n_pe_voucher_id
        self.assertEqual(
            pay_voucher, receivable_voucher,
            "payment shares the reconciled line's voucher, not an own one",
        )
        self.assertFalse(self._own_vouchers_of(payment.move_id))

    def test_grouped_payment_of_several_vouchers_keeps_own(self):
        """A single payment settling invoices of different vouchers keeps its
        own voucher (ambiguous grouping is not merged)."""
        inv_a = self._invoice()
        inv_b = self._invoice()
        self.assertNotEqual(
            inv_a.line_ids.l10n_pe_voucher_id, inv_b.line_ids.l10n_pe_voucher_id
        )

        payment = self._register_payment(inv_a + inv_b, group_payment=True)

        pay_voucher = payment.move_id.line_ids.l10n_pe_voucher_id
        self.assertEqual(len(pay_voucher), 1, "payment stays on a single voucher")
        self.assertEqual(pay_voucher.l10n_pe_origin_model, "account.move")
        self.assertEqual(pay_voucher.l10n_pe_origin_res_id, payment.move_id.id)
        self.assertNotIn(
            pay_voucher,
            inv_a.line_ids.l10n_pe_voucher_id | inv_b.line_ids.l10n_pe_voucher_id,
        )

    def test_statement_entry_is_deferred_no_voucher_on_post(self):
        """A bank/cash statement entry must NOT receive a voucher at posting
        (it is deferred to reconciliation) -- this is the orphan root cause."""
        st_line = self.env["account.bank.statement.line"].create({
            "journal_id": self.bank_journal.id,
            "amount": 100.0,
            "date": fields.Date.context_today(self.env["account.bank.statement.line"]),
            "payment_ref": "voucher test",
            "partner_id": self.partner_a.id,
        })
        move = st_line.move_id
        self.assertTrue(move._l10n_pe_voucher_deferred(), "statement move is deferred")
        self.assertEqual(move.state, "posted")
        self.assertFalse(
            move.line_ids.l10n_pe_voucher_id,
            "no voucher assigned to the statement entry at posting",
        )

    def test_payment_is_deferred_no_voucher_until_reconcile(self):
        """A standalone payment is deferred at posting and gets its own voucher
        only via the backfill safety net."""
        payment = self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner_a.id,
            "amount": 150.0,
            "journal_id": self.bank_journal.id,
        })
        payment.action_post()
        move = payment.move_id
        self.assertTrue(move._l10n_pe_voucher_deferred())
        self.assertFalse(move.line_ids.l10n_pe_voucher_id, "deferred: no voucher yet")

        processed = self.env["account.move"]._l10n_pe_backfill_deferred_vouchers()
        self.assertGreaterEqual(processed, 1)

        own = self._own_vouchers_of(move)
        self.assertEqual(len(own), 1, "backfill assigns an own voucher")
        self.assertEqual(move.line_ids.l10n_pe_voucher_id, own)
