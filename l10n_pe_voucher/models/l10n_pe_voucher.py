import logging

import psycopg2
from psycopg2 import errorcodes

from odoo import api, fields, models
from odoo.tools import SQL
from odoo.tools.sql import index_exists

_logger = logging.getLogger(__name__)

# Sequence code used to build the per-company global voucher correlative.
VOUCHER_SEQUENCE_CODE = "l10n_pe.voucher"

# Partial unique index guarding the per-company voucher sequence. A global
# ``unique(code, company_id)`` on ``ir.sequence`` is not an option: the rest of
# Odoo legitimately holds several sequences sharing a code (per journal, per
# operation type, ...), so we restrict the index to our own code.
SEQUENCE_INDEX_NAME = "ir_sequence_l10n_pe_voucher_company_uniq"


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
        # One voucher per operation. Besides forbidding the double correlative
        # that two concurrent transactions used to produce (see
        # ``_l10n_pe_get_or_create``), the backing composite index is exactly
        # the one that lookup needs -- which also covers the previously
        # unindexed ``l10n_pe_origin_res_id``.
        #
        # NULL handling: PostgreSQL never considers two NULLs equal in a plain
        # UNIQUE, so rows with an empty origin would not collide. That is
        # acceptable *and* wanted: no code path creates a voucher without an
        # origin (every creation goes through ``_l10n_pe_get_or_create``, which
        # always receives a model and a res_id), and a hand-made voucher with
        # no origin identifies no operation, hence nothing to deduplicate. A
        # partial unique index (``WHERE ... IS NOT NULL``) would behave
        # identically here, so we keep the declarative constraint.
        (
            "origin_uniq",
            "unique(company_id, l10n_pe_origin_model, l10n_pe_origin_res_id)",
            "There is already a voucher for this operation.",
        ),
    ]

    def init(self):
        """Create the partial unique index that serialises the on-demand
        creation of the voucher sequence.

        It cannot be declared as an ``_sql_constraints`` entry of
        ``ir.sequence``: that would apply to *every* sequence of the database
        and break perfectly valid duplicated codes of other modules. A partial
        index restricted to our own code gives us the same guarantee with zero
        impact on the rest of Odoo.
        """
        res = super().init()
        if not index_exists(self.env.cr, SEQUENCE_INDEX_NAME):
            # Fail with a readable message instead of a raw PostgreSQL error if
            # the database already holds duplicated voucher sequences (they can
            # only come from the very race this index closes). Merging them
            # automatically is not possible: each one may already have handed
            # out correlatives reported in a closed PLE.
            self.env.cr.execute(
                """
                  SELECT company_id, array_agg(id ORDER BY id)
                    FROM ir_sequence
                   WHERE code = %s
                GROUP BY company_id
                  HAVING count(*) > 1
                """,
                (VOUCHER_SEQUENCE_CODE,),
            )
            duplicates = self.env.cr.fetchall()
            if duplicates:
                found = ", ".join(
                    f"{company_id}: {ids}" for company_id, ids in duplicates
                )
                raise ValueError(
                    f"Duplicated voucher sequences found (company_id: sequence "
                    f"ids): {found}. Keep a single {VOUCHER_SEQUENCE_CODE} "
                    f"sequence per company (the one holding the highest "
                    f"correlative) before updating this module."
                )
            self.env.cr.execute(
                SQL(
                    """
                    CREATE UNIQUE INDEX %s
                        ON ir_sequence (code, company_id)
                     WHERE code = %s
                    """,
                    SQL.identifier(SEQUENCE_INDEX_NAME),
                    VOUCHER_SEQUENCE_CODE,
                )
            )
            _logger.info("Created index %s on ir_sequence", SEQUENCE_INDEX_NAME)
        return res

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
    def _l10n_pe_create_or_recover(self, records, vals, domain):
        """Create ``vals`` on ``records`` model, tolerating a concurrent twin.

        Optimistic concurrency: we simply try to insert and let PostgreSQL
        arbitrate through the unique index. If a parallel transaction won the
        race, its row is already committed by the time we get the violation, so
        re-running ``domain`` returns the winner and both transactions end up
        sharing a single record.

        The ``INSERT`` must reach the database *inside* the savepoint, hence
        the explicit ``flush_all()``: the ORM would otherwise delay it until the
        end of the transaction and the violation would be raised outside the
        block, past the point where it can still be rolled back cleanly.

        Rolling back to the savepoint also undoes the ``no_gap`` sequence
        increment performed while computing ``name``, so a lost race does not
        burn a correlative.
        """
        try:
            with self.env.cr.savepoint():
                record = records.create(vals)
                self.env.flush_all()
                return record
        except psycopg2.IntegrityError as error:
            if error.pgcode != errorcodes.UNIQUE_VIOLATION:
                raise
            # The savepoint rollback cleared the caches, so this hits the
            # database and sees whatever the winner committed.
            record = records.search(domain, limit=1)
            if not record:
                # Unique violation on something else than the racing twin.
                raise
            _logger.info(
                "Concurrent creation detected on %s, reusing %s.",
                records._name,
                record,
            )
            return record

    @api.model
    def _l10n_pe_get_sequence(self, company):
        """Return (creating it on demand) the gap-less, per-company sequence
        that feeds the voucher correlative."""
        Sequence = self.env["ir.sequence"].sudo()
        domain = [
            ("code", "=", VOUCHER_SEQUENCE_CODE),
            ("company_id", "=", company.id),
        ]
        sequence = Sequence.search(domain, limit=1)
        if not sequence:
            # Guarded by the partial unique index built in ``init()``.
            sequence = self._l10n_pe_create_or_recover(
                Sequence,
                {
                    "name": f"Peruvian Voucher - {company.name}",
                    "code": VOUCHER_SEQUENCE_CODE,
                    "company_id": company.id,
                    "implementation": "no_gap",
                    "padding": 8,
                },
                domain,
            )
        return sequence

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                company = (
                    self.env["res.company"].browse(vals.get("company_id"))
                    or self.env.company
                )
                vals["name"] = self._l10n_pe_get_sequence(company).next_by_id()
        return super().create(vals_list)

    @api.model
    def _l10n_pe_get_or_create(self, company, origin_model, origin_res_id):
        """Find the voucher for the given origin or create a fresh one.

        Two transactions posting related entries of the same operation at the
        same time (POS session close, purchase receipt + bill, a payment being
        reconciled, ...) both used to find nothing and both created a voucher,
        giving the operation two CUOs. The creation is now arbitrated by the
        ``origin_uniq`` index: the loser reuses the winner's voucher.
        """
        domain = [
            ("company_id", "=", company.id),
            ("l10n_pe_origin_model", "=", origin_model),
            ("l10n_pe_origin_res_id", "=", origin_res_id),
        ]
        voucher = self.sudo().search(domain, limit=1)
        if not voucher:
            voucher = self._l10n_pe_create_or_recover(
                self.sudo(),
                {
                    "company_id": company.id,
                    "l10n_pe_origin_model": origin_model,
                    "l10n_pe_origin_res_id": origin_res_id,
                },
                domain,
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
