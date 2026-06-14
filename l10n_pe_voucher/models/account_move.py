from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_pe_voucher_ids = fields.Many2many(
        "l10n.pe.voucher",
        string="Vouchers",
        compute="_compute_l10n_pe_voucher_ids",
        help="Accounting operations (CUO) the journal items of this entry "
        "belong to.",
    )

    @api.depends("line_ids.l10n_pe_voucher_id")
    def _compute_l10n_pe_voucher_ids(self):
        for move in self:
            move.l10n_pe_voucher_ids = move.line_ids.l10n_pe_voucher_id

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted._l10n_pe_assign_vouchers()
        return posted

    # -------------------------------------------------------------------------
    # Voucher resolution
    #
    # The core only knows the fallback (the move itself). Each domain-specific
    # bridge module (purchase/sale/stock, POS, ...) extends the resolvers below
    # through ``super()`` to map a move/line to its real business operation.
    # -------------------------------------------------------------------------
    def _l10n_pe_voucher_move_key(self):
        """Return the operation origin ``(model, res_id)`` shared by the whole
        move, or ``None`` when it must be resolved line by line.

        Base implementation knows no move-level operation; bridge modules
        override it (e.g. inventory valuation -> purchase/sale order, POS).
        """
        self.ensure_one()
        return None

    def _l10n_pe_voucher_deferred(self):
        """Whether the voucher of this move is resolved after posting instead of
        at ``_post`` time.

        Base implementation never defers. The reconciliation bridge overrides it
        for payment and bank/cash statement entries, whose voucher is decided at
        reconciliation (so they can share the voucher of the document they
        settle, without burning a correlative on a throwaway voucher).
        """
        self.ensure_one()
        return False

    def _l10n_pe_resolve_line_keys(self):
        """Map every journal item of the move to an operation origin."""
        self.ensure_one()
        lines = self.line_ids
        move_key = self._l10n_pe_voucher_move_key()
        if move_key:
            return {line: move_key for line in lines}

        keys = {line: line._l10n_pe_voucher_line_key() for line in lines}
        resolved = {key for key in keys.values() if key}
        # Lines without their own origin (taxes, payable/receivable, rounding)
        # follow the move's single operation, or fall back to the move itself.
        fallback = next(iter(resolved)) if len(resolved) == 1 else ("account.move", self.id)
        return {line: (key or fallback) for line, key in keys.items()}

    def _l10n_pe_assign_vouchers(self):
        """Assign a voucher to every journal item of the posted moves."""
        for move in self:
            if move.state != "posted" or move._l10n_pe_voucher_deferred():
                continue
            keys = move._l10n_pe_resolve_line_keys()
            cache = {}
            lines_by_voucher = {}
            for line, key in keys.items():
                # Respect a voucher already set (manual edit or re-posting).
                if line.l10n_pe_voucher_id or not key:
                    continue
                if key not in cache:
                    cache[key] = move._l10n_pe_get_voucher_for_key(key)
                lines_by_voucher.setdefault(cache[key].id, []).append(line.id)
            for voucher_id, line_ids in lines_by_voucher.items():
                self.env["account.move.line"].browse(line_ids).write(
                    {"l10n_pe_voucher_id": voucher_id}
                )

    def _l10n_pe_get_voucher_for_key(self, key):
        self.ensure_one()
        origin_model, origin_res_id = key
        return self.env["l10n.pe.voucher"]._l10n_pe_get_or_create(
            self.company_id, origin_model, origin_res_id
        )

    # -------------------------------------------------------------------------
    # Backfill of historical entries
    # -------------------------------------------------------------------------
    @api.model
    def _l10n_pe_backfill_vouchers(self, date_from=None, limit=None, commit=False):
        """Assign vouchers to already posted entries that have none.

        Meant to be run once after installing on a database that already holds
        accounting data. It is:

        * idempotent -- only entries with at least one line without a voucher are
          touched, so it can be re-run or resumed safely;
        * ordered -- entries are processed by ``date`` then ``id`` so the
          correlative follows the chronological order of the documents;
        * chunkable -- ``limit`` processes only the next chunk of pending moves,
          which is what the wizard uses to advance a progress bar one batch at a
          time; ``commit=True`` (shell/cron only) commits the chunk.

        Returns the number of moves processed in this call.
        """
        ordered = self._l10n_pe_ordered_backfill_moves(date_from)
        if limit:
            ordered = ordered[:limit]
        if ordered:
            ordered._l10n_pe_assign_backfill_batch()
            if commit:
                self.env.cr.commit()
        return len(ordered)

    @api.model
    def _l10n_pe_ordered_backfill_moves(self, date_from=None):
        """Pending posted moves: non-deferred first, then deferred, each by date.

        Regular entries (invoices, valuation) must get their voucher before the
        deferred ones (payments/statements) so the latter can adopt it.
        """
        moves = self._l10n_pe_moves_to_backfill(date_from)
        non_deferred = moves.filtered(lambda m: not m._l10n_pe_voucher_deferred())
        deferred = moves - non_deferred
        return non_deferred + deferred

    def _l10n_pe_assign_backfill_batch(self):
        """Assign vouchers to a batch of historical moves. The core handles the
        regular (non-deferred) entries; bridge modules extend this through
        ``super()`` to resolve their own deferred entries."""
        non_deferred = self.filtered(lambda m: not m._l10n_pe_voucher_deferred())
        non_deferred._l10n_pe_assign_vouchers()

    @api.model
    def _l10n_pe_moves_to_backfill(self, date_from=None):
        domain = [
            ("state", "=", "posted"),
            ("line_ids.l10n_pe_voucher_id", "=", False),
        ]
        if date_from:
            domain.append(("date", ">=", date_from))
        return self.search(domain, order="date, id")
