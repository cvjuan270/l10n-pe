from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_pe_voucher_move_key(self):
        """Resolve the operation of a Point of Sale journal entry.

        An order invoice maps to its ``pos.order``; the session closing entry
        maps to its ``pos.session`` so every entry of the same POS operation is
        grouped under one voucher.
        """
        self.ensure_one()
        if self.pos_order_ids:
            return ("pos.order", self.pos_order_ids[:1].id)
        if self.pos_session_ids:
            return ("pos.session", self.pos_session_ids[:1].id)
        return super()._l10n_pe_voucher_move_key()
