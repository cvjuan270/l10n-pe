from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_pe_voucher_id = fields.Many2one(
        "l10n.pe.voucher",
        string="Voucher",
        copy=False,
        index="btree_not_null",
        help="Accounting operation (CUO) this journal item belongs to, used "
        "to group the entries in the Peruvian Journal Book.",
    )

    def _l10n_pe_voucher_line_key(self):
        """Return the operation origin ``(model, res_id)`` of a single journal
        item, or ``None`` when it cannot be resolved at line level.

        Base implementation has no line-level origin; bridge modules override it
        (e.g. ``purchase_line_id``/``sale_line_ids``) so that an invoice line and
        the inventory valuation of the same order share one voucher, while a
        consolidated move pointing to several orders is split per line.
        """
        self.ensure_one()
        return None
