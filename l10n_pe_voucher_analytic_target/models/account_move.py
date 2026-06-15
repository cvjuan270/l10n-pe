from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_pe_assign_vouchers(self):
        """A destination entry inherits the voucher of the origin journal item
        it was generated from, so the source operation (e.g. a vendor bill) and
        its analytic destination entry are grouped under the same CUO.

        Origins are resolved first so the destinations can inherit even when both
        are processed together (e.g. during the historical backfill). A
        destination whose origin item still has no voucher falls back to the
        standard resolution.
        """
        destinations = self.filtered(lambda m: m.origin_move_line_id)
        # 1) Everything that is not a destination (origins included) gets its
        #    voucher first.
        super(AccountMove, self - destinations)._l10n_pe_assign_vouchers()

        # 2) Destinations whose origin item now has a voucher inherit it.
        inheriting = destinations.filtered(
            lambda m: m.state == "posted"
            and not m._l10n_pe_voucher_deferred()
            and m.origin_move_line_id.l10n_pe_voucher_id
        )
        for move in inheriting:
            voucher = move.origin_move_line_id.l10n_pe_voucher_id
            lines = move.line_ids.filtered(lambda line: not line.l10n_pe_voucher_id)
            if lines:
                lines.write({"l10n_pe_voucher_id": voucher.id})

        # 3) Remaining destinations (origin without voucher) fall back.
        return super(
            AccountMove, destinations - inheriting
        )._l10n_pe_assign_vouchers()

    def _l10n_pe_ordered_backfill_moves(self, date_from=None):
        """Process destination entries last, after all their possible origins,
        so the historical backfill lets them inherit the origin voucher."""
        ordered = super()._l10n_pe_ordered_backfill_moves(date_from)
        targets = ordered.filtered(lambda m: m.origin_move_line_id)
        return (ordered - targets) + targets
