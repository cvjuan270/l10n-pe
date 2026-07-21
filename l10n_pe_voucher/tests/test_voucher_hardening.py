"""Regression tests for the concurrency/robustness hardening of the voucher.

Covers:

* the ``origin_uniq`` SQL constraint that forbids two vouchers (two CUOs) for a
  single business operation;
* the optimistic retry of ``_l10n_pe_create_or_recover`` used by
  ``_l10n_pe_get_or_create`` and ``_l10n_pe_get_sequence``;
* the ``batch_size`` validation of the backfill wizard.
"""

from unittest.mock import patch

import psycopg2
from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_pe_voucher.models.l10n_pe_voucher import (
    SEQUENCE_INDEX_NAME,
    VOUCHER_SEQUENCE_CODE,
)
from odoo.addons.l10n_pe_voucher.tests.common import L10nPeVoucherTestMixin


@tagged("post_install", "-at_install")
class TestL10nPeVoucherHardening(L10nPeVoucherTestMixin, AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Voucher = cls.env["l10n.pe.voucher"]
        cls.misc_journal = cls.company_data["default_journal_misc"]
        cls.account_a = cls.company_data["default_account_revenue"]
        cls.account_b = cls.company_data["default_account_expense"]

    # -- helpers --------------------------------------------------------------
    def _new_misc_move(self, amount=100.0):
        return self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "line_ids": [
                    Command.create(
                        {
                            "account_id": self.account_a.id,
                            "debit": amount,
                            "credit": 0.0,
                            "name": "t",
                        }
                    ),
                    Command.create(
                        {
                            "account_id": self.account_b.id,
                            "debit": 0.0,
                            "credit": amount,
                            "name": "t",
                        }
                    ),
                ],
            }
        )

    def _sequence(self):
        return self.Voucher._l10n_pe_get_sequence(self.env.company)

    # =========================================================================
    # A) origin_uniq: one voucher per operation, enforced by PostgreSQL
    # =========================================================================
    def test_origin_uniq_constraint_exists(self):
        """The constraint and the supporting indexes really are in the DB."""
        self.env.cr.execute(
            """
            SELECT 1 FROM pg_constraint
             WHERE conname = 'l10n_pe_voucher_origin_uniq'
               AND conrelid = 'l10n_pe_voucher'::regclass
            """
        )
        self.assertTrue(
            self.env.cr.fetchone(),
            "origin_uniq constraint installed on l10n_pe_voucher",
        )
        self.env.cr.execute(
            "SELECT 1 FROM pg_indexes WHERE indexname = %s", (SEQUENCE_INDEX_NAME,)
        )
        self.assertTrue(
            self.env.cr.fetchone(),
            "partial unique index on ir_sequence installed by init()",
        )

    @mute_logger("odoo.sql_db")
    def test_duplicate_origin_create_raises_integrity_error(self):
        """A second voucher for the same (company, origin) is rejected by the
        database, not merely avoided by the search-then-create."""
        first = self.Voucher.create(
            {
                "company_id": self.env.company.id,
                "l10n_pe_origin_model": "purchase.order",
                "l10n_pe_origin_res_id": 4242424,
            }
        )
        self.env.flush_all()
        self.assertTrue(first.name, "the first voucher got its correlative")

        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.Voucher.create(
                    {
                        "company_id": self.env.company.id,
                        "l10n_pe_origin_model": "purchase.order",
                        "l10n_pe_origin_res_id": 4242424,
                    }
                )
                self.env.flush_all()

        # The savepoint isolated the abort: the cursor is still usable.
        self.assertEqual(
            self.Voucher.search_count(
                [
                    ("company_id", "=", self.env.company.id),
                    ("l10n_pe_origin_model", "=", "purchase.order"),
                    ("l10n_pe_origin_res_id", "=", 4242424),
                ]
            ),
            1,
            "a single voucher survives for the operation",
        )

    @mute_logger("odoo.sql_db")
    def test_duplicate_origin_raw_insert_raises_unique_violation(self):
        """Same guarantee bypassing the ORM entirely (raw INSERT)."""
        voucher = self.Voucher.create(
            {
                "company_id": self.env.company.id,
                "l10n_pe_origin_model": "sale.order",
                "l10n_pe_origin_res_id": 5353535,
            }
        )
        self.env.flush_all()

        with self.assertRaises(psycopg2.errors.UniqueViolation):
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    """
                    INSERT INTO l10n_pe_voucher
                                (name, company_id, l10n_pe_origin_model,
                                 l10n_pe_origin_res_id, create_uid, write_uid,
                                 create_date, write_date)
                         VALUES (%s, %s, %s, %s, %s, %s, now(), now())
                    """,
                    (
                        f"{voucher.name}-dup",
                        self.env.company.id,
                        "sale.order",
                        5353535,
                        self.env.uid,
                        self.env.uid,
                    ),
                )

        self.env.cr.execute(
            """
            SELECT count(*) FROM l10n_pe_voucher
             WHERE company_id = %s AND l10n_pe_origin_model = 'sale.order'
               AND l10n_pe_origin_res_id = 5353535
            """,
            (self.env.company.id,),
        )
        self.assertEqual(self.env.cr.fetchone()[0], 1)

    def test_different_company_same_origin_allowed(self):
        """The constraint is per company: two companies may hold a voucher for
        the same origin id without colliding."""
        other_company = self.setup_other_company()["company"]
        v1 = self.Voucher._l10n_pe_get_or_create(
            self.env.company, "purchase.order", 7171717
        )
        v2 = self.Voucher._l10n_pe_get_or_create(
            other_company, "purchase.order", 7171717
        )
        self.env.flush_all()
        self.assertNotEqual(v1, v2)
        self.assertNotEqual(v1.company_id, v2.company_id)

    # =========================================================================
    # B) optimistic retry / idempotency
    # =========================================================================
    def test_get_or_create_is_idempotent(self):
        """Two consecutive calls with the same origin return the SAME voucher."""
        first = self.Voucher._l10n_pe_get_or_create(
            self.env.company, "pos.session", 606060
        )
        second = self.Voucher._l10n_pe_get_or_create(
            self.env.company, "pos.session", 606060
        )
        self.assertEqual(first, second)
        self.assertEqual(
            self.Voucher.search_count(
                [
                    ("company_id", "=", self.env.company.id),
                    ("l10n_pe_origin_model", "=", "pos.session"),
                    ("l10n_pe_origin_res_id", "=", 606060),
                ]
            ),
            1,
        )

    @mute_logger("odoo.sql_db", "odoo.addons.l10n_pe_voucher.models.l10n_pe_voucher")
    def test_get_or_create_recovers_from_concurrent_twin(self):
        """Simulated race: the lookup misses the voucher another transaction
        already committed, the INSERT hits ``origin_uniq``, and the helper
        RECOVERS the winner instead of propagating the exception.

        The first ``search`` is blinded (as if the twin had not been committed
        yet at that point); the recovery ``search`` inside
        ``_l10n_pe_create_or_recover`` sees it.
        """
        winner = self.Voucher._l10n_pe_get_or_create(
            self.env.company, "purchase.order", 8181818
        )
        self.env.flush_all()
        next_before = self._sequence().number_next_actual

        VoucherCls = type(self.Voucher)
        original_search = VoucherCls.search
        calls = {"n": 0}

        def blind_first_search(self, domain, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return self.browse()
            return original_search(self, domain, *args, **kwargs)

        with patch.object(VoucherCls, "search", blind_first_search):
            recovered = self.Voucher._l10n_pe_get_or_create(
                self.env.company, "purchase.order", 8181818
            )

        self.assertGreaterEqual(calls["n"], 2, "the recovery search really ran")
        self.assertEqual(
            recovered, winner, "the loser of the race reuses the winner's voucher"
        )
        self.assertEqual(
            self.Voucher.search_count(
                [
                    ("company_id", "=", self.env.company.id),
                    ("l10n_pe_origin_model", "=", "purchase.order"),
                    ("l10n_pe_origin_res_id", "=", 8181818),
                ]
            ),
            1,
            "the operation still owns exactly one CUO",
        )
        self.assertEqual(
            self._sequence().number_next_actual,
            next_before,
            "the lost race did not burn a correlative (savepoint rollback)",
        )

    @mute_logger("odoo.sql_db", "odoo.addons.l10n_pe_voucher.models.l10n_pe_voucher")
    def test_create_or_recover_reraises_unrelated_unique_violation(self):
        """A unique violation that is NOT the racing twin must propagate: the
        helper only swallows the collision it can resolve."""
        existing = self.Voucher.create(
            {
                "company_id": self.env.company.id,
                "l10n_pe_origin_model": "stock.picking",
                "l10n_pe_origin_res_id": 9191919,
            }
        )
        self.env.flush_all()

        # Same name (name_company_uniq), different origin -> the recovery search
        # on the origin domain finds nothing, so the error is re-raised.
        with self.assertRaises(IntegrityError):
            self.Voucher._l10n_pe_create_or_recover(
                self.Voucher,
                {
                    "name": existing.name,
                    "company_id": self.env.company.id,
                    "l10n_pe_origin_model": "stock.picking",
                    "l10n_pe_origin_res_id": 9292929,
                },
                [
                    ("company_id", "=", self.env.company.id),
                    ("l10n_pe_origin_model", "=", "stock.picking"),
                    ("l10n_pe_origin_res_id", "=", 9292929),
                ],
            )

    @mute_logger("odoo.sql_db", "odoo.addons.l10n_pe_voucher.models.l10n_pe_voucher")
    def test_get_sequence_recovers_from_concurrent_twin(self):
        """Same optimistic retry on the on-demand creation of the voucher
        sequence: a blinded lookup must not end up with two sequences."""
        company = self.env.company
        winner = self.Voucher._l10n_pe_get_sequence(company)
        self.env.flush_all()

        Sequence = self.env["ir.sequence"].sudo()
        SequenceCls = type(Sequence)
        original_search = SequenceCls.search
        calls = {"n": 0}

        def blind_first_search(self, domain, *args, **kwargs):
            if self._name == "ir.sequence" and any(
                VOUCHER_SEQUENCE_CODE in str(leaf) for leaf in domain
            ):
                calls["n"] += 1
                if calls["n"] == 1:
                    return self.browse()
            return original_search(self, domain, *args, **kwargs)

        with patch.object(SequenceCls, "search", blind_first_search):
            recovered = self.Voucher._l10n_pe_get_sequence(company)

        self.assertGreaterEqual(calls["n"], 2, "the recovery search really ran")
        self.assertEqual(recovered, winner, "the single sequence is reused")
        self.assertEqual(
            Sequence.search_count(
                [
                    ("code", "=", VOUCHER_SEQUENCE_CODE),
                    ("company_id", "=", company.id),
                ]
            ),
            1,
            "no duplicated voucher sequence for the company",
        )

    # =========================================================================
    # C) backfill wizard: batch_size validation
    # =========================================================================
    def test_backfill_batch_size_zero_rejected_on_create(self):
        with self.assertRaises(ValidationError):
            self.env["l10n.pe.voucher.backfill"].create({"batch_size": 0})

    def test_backfill_batch_size_negative_rejected_on_create(self):
        with self.assertRaises(ValidationError):
            self.env["l10n.pe.voucher.backfill"].create({"batch_size": -10})

    def test_backfill_batch_size_rejected_on_write(self):
        wizard = self.env["l10n.pe.voucher.backfill"].create({"batch_size": 50})
        with self.assertRaises(ValidationError):
            wizard.write({"batch_size": 0})
        with self.assertRaises(ValidationError):
            wizard.write({"batch_size": -1})

    def test_backfill_run_batch_rejects_non_positive_size(self):
        """Second line of defence: ``_run_batch`` re-checks the value even when
        it was not set through the ORM (default-less programmatic run)."""
        wizard = self.env["l10n.pe.voucher.backfill"].create({"batch_size": 50})
        # Bypass the constraint on purpose to exercise the guard in _run_batch.
        self.env.cr.execute(
            "UPDATE l10n_pe_voucher_backfill SET batch_size = 0 WHERE id = %s",
            (wizard.id,),
        )
        wizard.invalidate_recordset(["batch_size"])
        self.assertEqual(wizard.batch_size, 0)
        with self.assertRaises(ValidationError):
            wizard._run_batch()

        self.env.cr.execute(
            "UPDATE l10n_pe_voucher_backfill SET batch_size = -5 WHERE id = %s",
            (wizard.id,),
        )
        wizard.invalidate_recordset(["batch_size"])
        with self.assertRaises(ValidationError):
            wizard._run_batch()

    def test_backfill_happy_path_processes_the_batch(self):
        """A valid batch_size assigns vouchers to the pending entries."""
        move_a = self._new_misc_move(11.0)
        move_b = self._new_misc_move(22.0)
        (move_a + move_b).action_post()
        # Strip the vouchers to turn them into historical pending entries.
        (move_a + move_b).line_ids.l10n_pe_voucher_id = False
        self.env.flush_all()

        pending = self.env["account.move"]._l10n_pe_moves_to_backfill()
        self.assertIn(move_a, pending)
        self.assertIn(move_b, pending)

        wizard = self.env["l10n.pe.voucher.backfill"].create({"batch_size": 1})
        wizard.action_start()
        self.assertEqual(wizard.state, "running", "one batch of one move only")
        self.assertEqual(wizard.processed_count, 1)

        wizard.batch_size = 50
        wizard.action_continue()
        self.assertGreaterEqual(wizard.processed_count, 2)
        self.assertFalse(
            (move_a + move_b).line_ids.filtered(
                lambda line: not line.l10n_pe_voucher_id
            ),
            "every line of both moves got a voucher back",
        )
