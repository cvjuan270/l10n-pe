from odoo import _, api, fields, models


class L10nPeVoucherBackfill(models.TransientModel):
    _name = "l10n.pe.voucher.backfill"
    _description = "Assign vouchers to historical entries"

    date_from = fields.Date(
        string="From date",
        help="Only assign vouchers to entries posted on or after this date. "
        "Leave empty to process all posted entries.",
    )
    batch_size = fields.Integer(
        string="Batch size",
        default=500,
        help="Number of entries processed on each step of the progress bar. "
        "Lower it if a step exceeds the worker time limit.",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("running", "Running"), ("done", "Done")],
        default="draft",
    )
    total_count = fields.Integer(string="To process", readonly=True)
    processed_count = fields.Integer(string="Processed", readonly=True)
    pending_count = fields.Integer(
        string="Remaining", compute="_compute_pending_count"
    )
    progress = fields.Float(string="Progress", compute="_compute_progress")

    @api.depends("date_from", "state", "processed_count")
    def _compute_pending_count(self):
        Move = self.env["account.move"]
        for wizard in self:
            wizard.pending_count = len(
                Move._l10n_pe_moves_to_backfill(wizard.date_from)
            )

    @api.depends("total_count", "processed_count")
    def _compute_progress(self):
        for wizard in self:
            wizard.progress = (
                100.0 * wizard.processed_count / wizard.total_count
                if wizard.total_count
                else 0.0
            )

    def action_start(self):
        self.ensure_one()
        self.write({
            "state": "running",
            "total_count": len(
                self.env["account.move"]._l10n_pe_moves_to_backfill(self.date_from)
            ),
            "processed_count": 0,
        })
        return self._run_batch()

    def action_continue(self):
        self.ensure_one()
        return self._run_batch()

    def _run_batch(self):
        processed = self.env["account.move"]._l10n_pe_backfill_vouchers(
            date_from=self.date_from, limit=self.batch_size
        )
        self.processed_count += processed
        if not self.env["account.move"]._l10n_pe_moves_to_backfill(self.date_from):
            self.state = "done"
        return self._reopen()

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Assign Historical Vouchers"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
        }
