from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


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
            [
                ("l10n_pe_origin_model", "=", "account.move"),
                ("l10n_pe_origin_res_id", "=", move.id),
            ]
        )

    def _standalone_payment(self, amount):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": amount,
                "journal_id": self.bank_journal.id,
            }
        )
        payment.action_post()
        return payment

    def _statement_line(self, amount):
        return self.env["account.bank.statement.line"].create(
            {
                "journal_id": self.bank_journal.id,
                "amount": amount,
                "date": fields.Date.context_today(
                    self.env["account.bank.statement.line"]
                ),
                "payment_ref": "bank feed line",
                "partner_id": self.partner_a.id,
            }
        )

    def _reconcile_statement_with_payment(self, st_line, payment):
        """Reconcile a bank statement line against a payment, the way the bank
        reconciliation widget does it: the statement counterpart line is moved
        from the journal suspense account to the payment outstanding account,
        and both lines are then reconciled.
        """
        outstanding_line = payment.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type
            not in ("asset_receivable", "liability_payable")
        )
        self.assertEqual(len(outstanding_line), 1, "payment has one outstanding line")

        _liquidity, suspense, _other = st_line._seek_for_lines()
        self.assertEqual(len(suspense), 1, "statement entry has one suspense line")
        suspense.with_context(skip_readonly_check=True).write(
            {
                "account_id": outstanding_line.account_id.id,
            }
        )
        (suspense + outstanding_line).reconcile()
        return suspense, outstanding_line

    def _receivable_line(self, move):
        return move.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
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
            name_c,
            name_b + 1,
            "the payment between B and C did not skip a correlative",
        )

    def test_payment_anchors_on_reconciled_line_not_whole_invoice(self):
        """When the settled document spans several vouchers (e.g. a consolidated
        bill across purchase orders), the payment must adopt the voucher of the
        line it actually reconciles (receivable/payable), not fall into the
        ambiguous branch because of the document's other vouchers."""
        invoice = self._invoice()
        receivable = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
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
            pay_voucher,
            receivable_voucher,
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
        st_line = self.env["account.bank.statement.line"].create(
            {
                "journal_id": self.bank_journal.id,
                "amount": 100.0,
                "date": fields.Date.context_today(
                    self.env["account.bank.statement.line"]
                ),
                "payment_ref": "voucher test",
                "partner_id": self.partner_a.id,
            }
        )
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
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": 150.0,
                "journal_id": self.bank_journal.id,
            }
        )
        payment.action_post()
        move = payment.move_id
        self.assertTrue(move._l10n_pe_voucher_deferred())
        self.assertFalse(move.line_ids.l10n_pe_voucher_id, "deferred: no voucher yet")

        processed = self.env["account.move"]._l10n_pe_backfill_deferred_vouchers()
        self.assertGreaterEqual(processed, 1)

        own = self._own_vouchers_of(move)
        self.assertEqual(len(own), 1, "backfill assigns an own voucher")
        self.assertEqual(move.line_ids.l10n_pe_voucher_id, own)

    # -- reconciliation ordering ----------------------------------------------
    # The same economic facts (one invoice, one payment settling it, one bank
    # statement line matching that payment) are reconciled in two different
    # orders. The voucher of the payment must not depend on the order in which
    # the accountant happens to reconcile.

    def test_ordering_invoice_first_shares_voucher(self):
        """Order A (invoice first): invoice -> payment (reconciled with the
        invoice) -> statement matched against the payment.

        The payment adopts the invoice voucher and the statement entry, joining
        the component afterwards, adopts it as well: the whole chain shares the
        invoice voucher and no own voucher is created.
        """
        invoice = self._invoice()
        invoice_voucher = self._receivable_line(invoice).l10n_pe_voucher_id
        self.assertEqual(len(invoice_voucher), 1)

        # 1) payment reconciled with the invoice -> single anchor, adopts it.
        payment = self._register_payment(invoice)
        pay_voucher = payment.move_id.line_ids.l10n_pe_voucher_id
        self.assertEqual(pay_voucher, invoice_voucher, "payment shares invoice voucher")

        # 2) the bank statement line is matched against that payment.
        st_line = self._statement_line(invoice.amount_total)
        self._reconcile_statement_with_payment(st_line, payment)

        st_voucher = st_line.move_id.line_ids.l10n_pe_voucher_id
        self.assertEqual(
            st_voucher, invoice_voucher, "statement entry shares the invoice voucher"
        )
        self.assertEqual(
            payment.move_id.line_ids.l10n_pe_voucher_id,
            invoice_voucher,
            "payment still on the invoice voucher after the statement reconciliation",
        )
        self.assertFalse(self._own_vouchers_of(payment.move_id))
        self.assertFalse(self._own_vouchers_of(st_line.move_id))

    def test_ordering_statement_first_shares_voucher(self):
        """Order B (statement first): a standalone payment is matched with the
        bank statement line BEFORE being reconciled with the invoice.

        At the first reconciliation nothing anchors the component (payment +
        statement), so no voucher is minted: the chain is left pending precisely
        so it can still adopt the invoice voucher. Once the payment is reconciled
        with the invoice, the whole chain adopts it.

        Same facts and same result as `test_ordering_invoice_first_shares_voucher`
        -> the outcome does not depend on the reconciliation order.
        """
        invoice = self._invoice()
        invoice_voucher = self._receivable_line(invoice).l10n_pe_voucher_id
        self.assertEqual(len(invoice_voucher), 1)

        payment = self._standalone_payment(invoice.amount_total)
        self.assertFalse(
            payment.move_id.line_ids.l10n_pe_voucher_id, "deferred: no voucher yet"
        )

        # 1) statement matched against the payment: no invoice in the component,
        #    so the chain stays pending instead of minting a premature voucher.
        st_line = self._statement_line(invoice.amount_total)
        self._reconcile_statement_with_payment(st_line, payment)

        self.assertFalse(
            payment.move_id.line_ids.l10n_pe_voucher_id,
            "no voucher minted while the chain is unanchored",
        )
        self.assertFalse(
            st_line.move_id.line_ids.l10n_pe_voucher_id,
            "statement stays pending too",
        )

        # 2) the payment is now reconciled with the invoice it actually settles.
        pay_receivable = self._receivable_line(payment.move_id)
        inv_receivable = self._receivable_line(invoice)
        (pay_receivable + inv_receivable).reconcile()
        # The reconciliation is real: the invoice is fully paid by this payment.
        self.assertEqual(
            invoice.payment_state, "paid", "the payment settles the invoice"
        )
        self.assertEqual(
            inv_receivable.matched_credit_ids.credit_move_id,
            pay_receivable,
            "invoice and payment are really matched together",
        )

        self.assertEqual(
            payment.move_id.line_ids.l10n_pe_voucher_id,
            invoice_voucher,
            "payment adopts the invoice voucher whatever the reconciliation order",
        )
        self.assertEqual(
            st_line.move_id.line_ids.l10n_pe_voucher_id,
            invoice_voucher,
            "the statement entry, already in the chain, adopts it as well",
        )
        # No correlative was burnt: order A does not burn one either.
        self.assertFalse(self._own_vouchers_of(payment.move_id))
        self.assertFalse(self._own_vouchers_of(st_line.move_id))

    # -- foreign currency -------------------------------------------------------
    def test_unanchored_advance_shares_one_voucher_at_backfill(self):
        """A genuine advance -- a payment matched only with its bank statement,
        never settling any document -- must still end up on a SINGLE shared
        voucher, granted by the period-close backfill.

        This is the counterpart of the ordering fix: the chain is not numbered
        eagerly at reconciliation, but it must not end up split across two
        vouchers either.
        """
        payment = self._standalone_payment(500.0)
        st_line = self._statement_line(500.0)
        self._reconcile_statement_with_payment(st_line, payment)

        self.assertFalse(
            (payment.move_id | st_line.move_id).line_ids.l10n_pe_voucher_id,
            "unanchored chain is pending until the backfill",
        )

        self.env["account.move"]._l10n_pe_backfill_deferred_vouchers()

        pay_voucher = payment.move_id.line_ids.l10n_pe_voucher_id
        st_voucher = st_line.move_id.line_ids.l10n_pe_voucher_id
        self.assertEqual(len(pay_voucher), 1, "payment on a single voucher")
        self.assertEqual(
            pay_voucher, st_voucher, "payment and statement share ONE voucher"
        )
