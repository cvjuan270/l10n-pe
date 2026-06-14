from odoo import api, fields, models

# Sequence code used to build the per-company global voucher correlative.
VOUCHER_SEQUENCE_CODE = "l10n_pe.voucher"


class L10nPeVoucher(models.Model):
    """A voucher groups every journal item that belongs to the same business
    operation (CUO) so the Peruvian Journal Book can present them together.

    The voucher is identified by its *origin* (the source document such as a
    purchase order, sale order, POS order/session, or the move itself as a
    fallback). The origin lets related journal entries -- e.g. the inventory
    valuation move and the vendor bill of the same purchase -- reuse the very
    same voucher number.
    """

    _name = "l10n.pe.voucher"
    _description = "Peruvian Accounting Voucher"
    _order = "id desc"

    name = fields.Char(
        string="Voucher",
        readonly=True,
        copy=False,
        index=True,
        help="Per-company correlative number of the accounting operation.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    # Origin of the operation. Used to deduplicate the voucher so related
    # moves (inventory valuation + invoice, payment + invoice, ...) reuse it.
    l10n_pe_origin_model = fields.Char(string="Origin Model", index=True)
    l10n_pe_origin_res_id = fields.Integer(string="Origin Reference")

    move_line_ids = fields.One2many(
        "account.move.line",
        "l10n_pe_voucher_id",
        string="Journal Items",
    )
    move_ids = fields.Many2many(
        "account.move",
        string="Journal Entries",
        compute="_compute_move_ids",
    )
    move_count = fields.Integer(string="# Entries", compute="_compute_move_ids")
    line_count = fields.Integer(string="# Items", compute="_compute_move_ids")
    date = fields.Date(string="First Entry Date", compute="_compute_date", store=True)

    _sql_constraints = [
        (
            "name_company_uniq",
            "unique(name, company_id)",
            "The voucher number must be unique per company.",
        ),
    ]

    @api.depends("move_line_ids.move_id")
    def _compute_move_ids(self):
        for voucher in self:
            moves = voucher.move_line_ids.move_id
            voucher.move_ids = moves
            voucher.move_count = len(moves)
            voucher.line_count = len(voucher.move_line_ids)

    @api.depends("move_line_ids.date")
    def _compute_date(self):
        for voucher in self:
            dates = voucher.move_line_ids.mapped("date")
            voucher.date = min(dates) if dates else False

    @api.model
    def _l10n_pe_get_sequence(self, company):
        """Return (creating it on demand) the gap-less, per-company sequence
        that feeds the voucher correlative."""
        Sequence = self.env["ir.sequence"].sudo()
        sequence = Sequence.search(
            [
                ("code", "=", VOUCHER_SEQUENCE_CODE),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        if not sequence:
            sequence = Sequence.create(
                {
                    "name": "Peruvian Voucher - %s" % company.name,
                    "code": VOUCHER_SEQUENCE_CODE,
                    "company_id": company.id,
                    "implementation": "no_gap",
                    "padding": 8,
                }
            )
        return sequence

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                company = self.env["res.company"].browse(
                    vals.get("company_id")
                ) or self.env.company
                vals["name"] = self._l10n_pe_get_sequence(company).next_by_id()
        return super().create(vals_list)

    @api.model
    def _l10n_pe_get_or_create(self, company, origin_model, origin_res_id):
        """Find the voucher for the given origin or create a fresh one."""
        voucher = self.sudo().search(
            [
                ("company_id", "=", company.id),
                ("l10n_pe_origin_model", "=", origin_model),
                ("l10n_pe_origin_res_id", "=", origin_res_id),
            ],
            limit=1,
        )
        if not voucher:
            voucher = self.sudo().create(
                {
                    "company_id": company.id,
                    "l10n_pe_origin_model": origin_model,
                    "l10n_pe_origin_res_id": origin_res_id,
                }
            )
        return voucher

    def action_open_journal_items(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "account.move.line",
            "view_mode": "list,form",
            "domain": [("l10n_pe_voucher_id", "=", self.id)],
            "context": {"create": False},
        }
