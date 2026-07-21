"""Guard the new ``origin_uniq`` constraint against pre-existing duplicates.

Version 18.0.1.1.0 adds ``unique(company_id, l10n_pe_origin_model,
l10n_pe_origin_res_id)`` on ``l10n.pe.voucher``. Databases that ran the previous
version under concurrency may already hold two vouchers -- two correlatives --
for a single operation, and the constraint would then fail with a raw
PostgreSQL error in the middle of the update.

We deliberately do **not** merge them: a correlative may already have been
reported in a closed PLE (Libro Diario), so picking a survivor is an accounting
decision, not a technical one. The migration aborts with the exact list of
affected operations so it can be resolved manually before retrying.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
          SELECT company_id,
                 l10n_pe_origin_model,
                 l10n_pe_origin_res_id,
                 array_agg(id ORDER BY id) AS voucher_ids,
                 array_agg(name ORDER BY id) AS voucher_names
            FROM l10n_pe_voucher
           WHERE l10n_pe_origin_model IS NOT NULL
             AND l10n_pe_origin_res_id IS NOT NULL
        GROUP BY company_id, l10n_pe_origin_model, l10n_pe_origin_res_id
          HAVING count(*) > 1
        ORDER BY company_id, l10n_pe_origin_model, l10n_pe_origin_res_id
        """
    )
    duplicates = cr.fetchall()

    # Vouchers with an empty origin are left alone on purpose: PostgreSQL does
    # not compare NULLs in a UNIQUE index, so they cannot break the constraint.
    cr.execute(
        """
        SELECT count(*)
          FROM l10n_pe_voucher
         WHERE l10n_pe_origin_model IS NULL
            OR l10n_pe_origin_res_id IS NULL
        """
    )
    orphans = cr.fetchone()[0]
    if orphans:
        _logger.warning(
            "l10n_pe_voucher: %s voucher(s) without origin. They are not "
            "covered by the new origin_uniq constraint (NULLs never collide) "
            "and are left untouched.",
            orphans,
        )

    if not duplicates:
        return

    details = "\n".join(
        " - company {} / {}#{} -> vouchers {} ({})".format(
            company_id,
            origin_model,
            origin_res_id,
            ", ".join(str(voucher_id) for voucher_id in voucher_ids),
            ", ".join(str(name) for name in voucher_names),
        )
        for (
            company_id,
            origin_model,
            origin_res_id,
            voucher_ids,
            voucher_names,
        ) in duplicates
    )
    message = (
        f"l10n_pe_voucher 18.0.1.1.0 cannot be installed: {len(duplicates)} "
        f"operation(s) own more than one voucher, which the new origin_uniq "
        f"constraint forbids.\n"
        f"{details}\n\n"
        f"This must be resolved MANUALLY: an already reported correlative "
        f"cannot be reassigned automatically. For each group, decide which "
        f"voucher survives, re-point the journal items "
        f"(account_move_line.l10n_pe_voucher_id) to it and delete or re-purpose "
        f"the others; then re-run the update."
    )
    _logger.error(message)
    raise ValueError(message)
