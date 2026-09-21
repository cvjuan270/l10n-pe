from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_pe_voucher_deferred(self):
        """Payment and bank/cash statement entries get their voucher at
        reconciliation, not at posting.

        Posting them with a throwaway voucher would burn a correlative (the
        sequence is gap-less) and leave an orphan voucher when they later share
        the voucher of the document they settle.
        """
        self.ensure_one()
        return bool(self.origin_payment_id) or bool(self.statement_line_id)

    def _l10n_pe_deferred_component(self):
        """Connected component of deferred moves reachable from ``self`` through
        reconciliations (the payment <-> statement chain).

        Shared by the reconciliation-time resolution and by the backfill, so both
        group a chain of deferred entries exactly the same way.
        """
        Move = self.env["account.move"]
        component = Move
        seen = Move
        todo = list(self.filtered(lambda m: m._l10n_pe_voucher_deferred()))
        while todo:
            move = todo.pop()
            if move in seen:
                continue
            seen |= move
            component |= move
            for neighbour in move.line_ids._l10n_pe_reconciled_counterpart_moves():
                if neighbour._l10n_pe_voucher_deferred() and neighbour not in seen:
                    todo.append(neighbour)
        return component

    def _l10n_pe_assign_own_component_vouchers(self):
        """Give a single shared voucher to each connected component of deferred
        moves that no document anchors.

        Sharing per *component* rather than per move keeps a genuine advance --
        a payment matched only with its bank statement line -- on a single CUO.
        The reconciliation-time resolution deliberately leaves those components
        pending (minting a voucher eagerly would freeze the grouping and make the
        result depend on the reconciliation order), so this is where they finally
        get their number, once no document can anchor them any more.
        """
        Voucher = self.env["l10n.pe.voucher"]
        done = self.env["account.move"]
        for move in self:
            if move in done:
                continue
            component = move._l10n_pe_deferred_component()
            done |= component
            pending = component.line_ids.filtered(
                lambda line: not line.l10n_pe_voucher_id
            )
            if not pending:
                continue
            # The lowest id of the component names the voucher, so the same chain
            # always resolves to the same origin whatever move we start from.
            main = component.sorted("id")[:1]
            voucher = Voucher._l10n_pe_get_or_create(
                main.company_id, "account.move", main.id
            )
            pending.write({"l10n_pe_voucher_id": voucher.id})

    def _l10n_pe_assign_backfill_batch(self):
        """Extend the historical backfill batch to resolve deferred entries.

        After the core assigned the regular entries (invoices, valuation, ...),
        replay the reconciliation-based resolution for the payment/statement
        entries of this batch so they adopt the voucher of the document they
        settle, then give a shared voucher to each chain that stays unanchored
        within this batch.
        """
        super()._l10n_pe_assign_backfill_batch()
        deferred = self.filtered(lambda m: m._l10n_pe_voucher_deferred())
        if not deferred:
            return
        deferred.line_ids._l10n_pe_assign_reconcile_vouchers()
        deferred._l10n_pe_assign_own_component_vouchers()

    @api.model
    def _l10n_pe_backfill_deferred_vouchers(self, limit=None):
        """Assign a voucher to posted deferred moves that never got one (e.g.
        advances matched only with their bank statement, or legacy data).

        Deferred moves anchored to a document are resolved at reconciliation;
        this is the safety net for the chains that stay unanchored, and each such
        chain gets a single shared voucher. Meant to be run at period close
        (cron) or on demand. Returns the number of moves processed.
        """
        domain = [
            ("state", "=", "posted"),
            ("line_ids.l10n_pe_voucher_id", "=", False),
        ]
        moves = self.search(domain, limit=limit)
        moves = moves.filtered(
            lambda m: m._l10n_pe_voucher_deferred()
            and any(not line.l10n_pe_voucher_id for line in m.line_ids)
        )
        moves._l10n_pe_assign_own_component_vouchers()
        return len(moves)
