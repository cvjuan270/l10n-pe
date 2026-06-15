from odoo import Command
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestVoucherAnalyticTarget(AccountTestInvoicingCommon):
    """The analytic destination entry shares the origin item's voucher."""

    def _destination_move(self, origin_move, origin_line):
        company = self.env.company
        accounts = self.env["account.account"].search(
            [
                ("company_ids", "in", company.id),
                ("account_type", "in", ("expense", "expense_direct_cost")),
            ],
            limit=2,
        )
        return self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.company_data["default_journal_misc"].id,
                "origin_move_id": origin_move.id,
                "origin_move_line_id": origin_line.id,
                "line_ids": [
                    Command.create(
                        {
                            "account_id": accounts[0].id,
                            "debit": 50.0,
                            "credit": 0.0,
                            "name": "dest",
                        }
                    ),
                    Command.create(
                        {
                            "account_id": accounts[1].id,
                            "debit": 0.0,
                            "credit": 50.0,
                            "name": "dest",
                        }
                    ),
                ],
            }
        )

    def test_destination_inherits_origin_voucher(self):
        origin = self.init_invoice(
            "out_invoice", products=self.product_a, taxes=self.tax_sale_a, post=True
        )
        origin_line = origin.line_ids.filtered("l10n_pe_voucher_id")[:1]
        origin_voucher = origin_line.l10n_pe_voucher_id
        self.assertTrue(origin_voucher)

        destination = self._destination_move(origin, origin_line)
        destination.action_post()

        self.assertEqual(
            destination.line_ids.l10n_pe_voucher_id,
            origin_voucher,
            "destination entry shares the origin voucher",
        )
        # No own fallback voucher was created for the destination move.
        self.assertFalse(
            self.env["l10n.pe.voucher"].search(
                [
                    ("l10n_pe_origin_model", "=", "account.move"),
                    ("l10n_pe_origin_res_id", "=", destination.id),
                ]
            )
        )

    def test_destination_without_origin_voucher_falls_back(self):
        """If the origin item has no voucher, the destination gets its own."""
        origin = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.company_data["default_journal_misc"].id,
                "line_ids": [
                    Command.create(
                        {
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "debit": 50.0,
                            "credit": 0.0,
                            "name": "o",
                        }
                    ),
                    Command.create(
                        {
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "debit": 0.0,
                            "credit": 50.0,
                            "name": "o",
                        }
                    ),
                ],
            }
        )
        # origin stays in draft -> no voucher on its lines
        origin_line = origin.line_ids[:1]
        self.assertFalse(origin_line.l10n_pe_voucher_id)

        destination = self._destination_move(origin, origin_line)
        destination.action_post()

        voucher = destination.line_ids.l10n_pe_voucher_id
        self.assertEqual(len(voucher), 1, "destination still gets a voucher")
        self.assertEqual(voucher.l10n_pe_origin_res_id, destination.id, "own fallback")
