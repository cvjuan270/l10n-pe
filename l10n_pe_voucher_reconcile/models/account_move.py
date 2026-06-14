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

    def _l10n_pe_assign_backfill_batch(self):
        """Extend the historical backfill batch to resolve deferred entries.

        After the core assigned the regular entries (invoices, valuation, ...),
        replay the reconciliation-based resolution for the payment/statement
        entries of this batch so they adopt the voucher of the document they
        settle, then give an own voucher to the ones that stay unreconciled
        (standalone) within this batch.
        """
        super()._l10n_pe_assign_backfill_batch()
        deferred = self.filtered(lambda m: m._l10n_pe_voucher_deferred())
        if not deferred:
            return
        deferred.line_ids._l10n_pe_assign_reconcile_vouchers()
        Voucher = self.env["l10n.pe.voucher"]
        for move in deferred:
            pending = move.line_ids.filtered(lambda line: not line.l10n_pe_voucher_id)
            if pending:
                voucher = Voucher._l10n_pe_get_or_create(
                    move.company_id, "account.move", move.id
                )
                pending.write({"l10n_pe_voucher_id": voucher.id})

    @api.model
    def _l10n_pe_backfill_deferred_vouchers(self, limit=None):
        """Assign an own voucher to posted deferred moves that never got one
        (e.g. standalone advances never reconciled, or legacy data).

        Reconciled deferred moves are handled at reconciliation; this is the
        safety net for the ones that stay open. Meant to be run at period close
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
        Voucher = self.env["l10n.pe.voucher"]
        for move in moves:
            voucher = Voucher._l10n_pe_get_or_create(
                move.company_id, "account.move", move.id
            )
            lines = move.line_ids.filtered(lambda line: not line.l10n_pe_voucher_id)
            lines.write({"l10n_pe_voucher_id": voucher.id})
        return len(moves)
