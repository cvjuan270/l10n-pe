from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _l10n_pe_pos_settlement_journal(self, pos_journal):
        """Cash/bank journal this POS line settles, or an empty recordset.

        Used to split the session closing entry and the per-method settlement
        entries into one voucher per payment journal. A line settles a journal
        when it -- or one of its reconciled counterparts -- lives in a non-POS
        cash/bank journal, or when it reconciles an order payment whose payment
        method posts to such a journal. Lines not tied to any settlement (sales,
        IGV, cost summary) return an empty recordset and stay on the single
        pos.session voucher.
        """
        self.ensure_one()
        Journal = self.env["account.journal"]
        own = self.move_id.journal_id
        if own.type in ("cash", "bank") and own != pos_journal:
            return own
        journals = Journal
        counterparts = (
            self.matched_debit_ids.debit_move_id
            | self.matched_credit_ids.credit_move_id
        ) - self
        for line in counterparts:
            journal = line.move_id.journal_id
            if journal.type in ("cash", "bank") and journal != pos_journal:
                journals |= journal
            elif line.move_id.pos_payment_ids:
                journals |= line.move_id.pos_payment_ids.payment_method_id.journal_id
        return journals if len(journals) == 1 else Journal
