import logging

from odoo import fields, models
from odoo.tools import SQL
from odoo.tools.sql import index_exists

_logger = logging.getLogger(__name__)

# Partial index feeding the backfill lookup (see ``init`` below).
PENDING_INDEX_NAME = "account_move_line_l10n_pe_voucher_pending_idx"


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_pe_voucher_id = fields.Many2one(
        "l10n.pe.voucher",
        string="Voucher",
        copy=False,
        # Day-to-day usage looks the field up *by voucher* (journal book,
        # voucher form, reconciliation bridge), never for NULLs, and on a fresh
        # installation almost every line is NULL: ``btree_not_null`` is the
        # right index there, it indexes only the rows anyone searches for and
        # grows as the data does. The complement (the backfill, which looks for
        # the lines still *without* a voucher) is served by the partial index
        # created in ``init``.
        index="btree_not_null",
        help="Accounting operation (CUO) this journal item belongs to, used "
        "to group the entries in the Peruvian Journal Book.",
    )

    def init(self):
        """Index the journal items that still have no voucher.

        ``account.move._l10n_pe_moves_to_backfill`` searches
        ``line_ids.l10n_pe_voucher_id = False``, i.e. exactly the rows that
        ``btree_not_null`` leaves out, so that query could only ever be a
        sequential scan over the whole ``account_move_line`` table -- and the
        wizard re-runs it after *every* batch to refresh the progress bar. The
        index is on ``move_id`` because that is the column the generated
        ``account_move.id IN (SELECT move_id FROM account_move_line WHERE
        l10n_pe_voucher_id IS NULL)`` sub-query reads.

        Trade-off: a partial ``WHERE ... IS NULL`` index is the mirror image of
        the field index. It is at its largest right after installing (when the
        backfill needs it most) and shrinks to nothing as the backfill
        progresses, so it costs the most exactly when it pays for itself. A
        plain full btree would have covered both cases with one index, but it
        would also index forever the millions of rows nobody queries by NULL
        once the backfill is done.
        """
        res = super().init()
        if not index_exists(self.env.cr, PENDING_INDEX_NAME):
            self.env.cr.execute(
                SQL(
                    """
                    CREATE INDEX %s
                        ON account_move_line (move_id)
                     WHERE l10n_pe_voucher_id IS NULL
                    """,
                    SQL.identifier(PENDING_INDEX_NAME),
                )
            )
            _logger.info("Created index %s on account_move_line", PENDING_INDEX_NAME)
        return res

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
