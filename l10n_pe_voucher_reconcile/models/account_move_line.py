from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def reconcile(self):
        res = super().reconcile()
        self._l10n_pe_assign_reconcile_vouchers()
        return res

    def _l10n_pe_reconciled_counterpart_moves(self):
        """Journal entries reconciled with these lines (excluding their own)."""
        counterpart_lines = (
            self.matched_debit_ids.debit_move_id
            | self.matched_credit_ids.credit_move_id
        ) - self
        return counterpart_lines.move_id

    def _l10n_pe_assign_reconcile_vouchers(self):
        """Give every deferred move (payment / statement) touched by this
        reconciliation the voucher of the operation it settles.

        The invoice <-> payment <-> statement entries form a graph linked by
        reconciliations. We walk the connected component of deferred moves and:

        * if the component is anchored to a single real voucher (the invoice's),
          every deferred move in it adopts that voucher;
        * if it is anchored to several vouchers (a payment settling invoices of
          different operations) the resolution is ambiguous, so each deferred
          move keeps its own voucher;
        * if there is no anchor yet (e.g. a payment matched only with a bank
          statement, no invoice) the component is left pending -- see below.

        Vouchers are only ever created, never deleted, so the gap-less
        correlative is preserved.
        """
        Voucher = self.env["l10n.pe.voucher"]

        seeds = self.move_id.filtered(lambda m: m._l10n_pe_voucher_deferred())
        seeds |= self._l10n_pe_reconciled_counterpart_moves().filtered(
            lambda m: m._l10n_pe_voucher_deferred()
        )
        if not seeds:
            return

        component = seeds._l10n_pe_deferred_component()

        pending = component.filtered(
            lambda m: any(not line.l10n_pe_voucher_id for line in m.line_ids)
        )
        if not pending:
            return

        # Anchor vouchers come from the lines actually reconciled with the
        # component -- the specific receivable/payable line of a document, not
        # every line of that document. This keeps a payment on the voucher of the
        # line it settles even when the invoice/bill spans several vouchers
        # (e.g. a consolidated bill across several purchase orders). Vouchers
        # already present on the component itself also anchor it.
        component_lines = component.line_ids
        counterpart_lines = (
            component_lines.matched_debit_ids.debit_move_id
            | component_lines.matched_credit_ids.credit_move_id
        ) - component_lines
        anchors = (
            counterpart_lines.filtered(
                lambda line: not line.move_id._l10n_pe_voucher_deferred()
            ).l10n_pe_voucher_id
            | component_lines.l10n_pe_voucher_id
        )

        if len(anchors) == 1:
            target = anchors
        elif not anchors:
            # Nothing anchors this component yet (e.g. a payment matched only
            # with its bank statement line, before the invoice is matched).
            #
            # Minting a voucher here would freeze the grouping: assignment only
            # fills empty lines and vouchers are never deleted, so the component
            # could no longer adopt the invoice voucher once the document is
            # reconciled later. The outcome would depend on the order the
            # accountant happens to reconcile in, and the "statement first" order
            # would burn a correlative that the "invoice first" order does not.
            #
            # Leave the component pending instead. The period-close backfill
            # (``_l10n_pe_assign_own_component_vouchers``) gives it a single
            # shared voucher once we know no document will ever anchor it, so a
            # genuine advance still ends up on one CUO.
            return
        else:
            # Ambiguous: several operations share this payment; keep each move
            # on its own voucher rather than merging unrelated operations.
            for move in pending:
                own = Voucher._l10n_pe_get_or_create(
                    move.company_id, "account.move", move.id
                )
                lines = move.line_ids.filtered(lambda line: not line.l10n_pe_voucher_id)
                lines.write({"l10n_pe_voucher_id": own.id})
            return

        lines = pending.line_ids.filtered(lambda line: not line.l10n_pe_voucher_id)
        lines.write({"l10n_pe_voucher_id": target.id})
