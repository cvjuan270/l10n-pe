from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestVoucherSalePurchase(AccountTestInvoicingCommon):
    """Voucher resolution for purchase, sale and inventory valuation entries."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        Account = cls.env["account.account"]
        assets = Account.search(
            [("company_ids", "in", company.id), ("account_type", "=", "asset_current")],
            limit=2,
        )
        out_acc = Account.search(
            [("company_ids", "in", company.id),
             ("account_type", "in", ("expense", "expense_direct_cost"))],
            limit=1,
        )
        stock_journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", company.id)], limit=1
        )
        cls._enough_accounts = len(assets) >= 2 and bool(out_acc) and bool(stock_journal)
        if cls._enough_accounts:
            cls.categ = cls.env["product.category"].create({
                "name": "Voucher Test",
                "property_cost_method": "standard",
                "property_valuation": "real_time",
                "property_stock_account_input_categ_id": assets[0].id,
                "property_stock_account_output_categ_id": out_acc.id,
                "property_stock_valuation_account_id": assets[1].id,
                "property_stock_journal": stock_journal.id,
            })

    def test_purchase_valuation_and_bill_share_voucher(self):
        """The receipt valuation move and the vendor bill of the same PO share
        one voucher whose origin is the purchase order."""
        if not self._enough_accounts:
            self.skipTest("chart of accounts cannot configure real-time valuation")

        product = self.env["product.product"].create({
            "name": "Voucher Product",
            "type": "consu",
            "is_storable": True,
            "categ_id": self.categ.id,
            "standard_price": 50.0,
            "purchase_method": "receive",
            "supplier_taxes_id": [Command.set([])],
        })
        vendor = self.env["res.partner"].create({"name": "Voucher Vendor"})

        po = self.env["purchase.order"].create({
            "partner_id": vendor.id,
            "order_line": [Command.create({
                "product_id": product.id,
                "product_qty": 10.0,
                "price_unit": 50.0,
                "name": product.name,
                "taxes_id": [Command.set([])],
            })],
        })
        po.button_confirm()

        picking = po.picking_ids
        picking.move_ids.write({"quantity": 10.0, "picked": True})
        picking._action_done()

        val_move = picking.move_ids.account_move_ids.filtered(lambda m: m.state == "posted")
        val_voucher = val_move.line_ids.l10n_pe_voucher_id
        self.assertEqual(len(val_voucher), 1)
        self.assertEqual(val_voucher.l10n_pe_origin_model, "purchase.order")
        self.assertEqual(val_voucher.l10n_pe_origin_res_id, po.id)

        po.action_create_invoice()
        bill = po.invoice_ids
        bill.invoice_date = fields.Date.context_today(bill)
        bill.action_post()

        bill_voucher = bill.line_ids.filtered("purchase_line_id").l10n_pe_voucher_id
        self.assertEqual(bill_voucher, val_voucher, "bill shares the valuation voucher")
        self.assertEqual(len(bill.line_ids.l10n_pe_voucher_id), 1, "single voucher on the bill")

    def test_sale_invoice_line_resolves_to_order(self):
        """A customer invoice created from a sale order resolves its product
        line to the sale order."""
        partner = self.partner_a
        so = self.env["sale.order"].create({
            "partner_id": partner.id,
            "order_line": [Command.create({
                "product_id": self.product_a.id,
                "product_uom_qty": 3.0,
                "price_unit": 100.0,
            })],
        })
        so.action_confirm()
        invoice = so._create_invoices()
        invoice.invoice_date = fields.Date.context_today(invoice)
        invoice.action_post()

        line = invoice.line_ids.filtered("sale_line_ids")
        voucher = line.l10n_pe_voucher_id
        self.assertEqual(len(voucher), 1)
        self.assertEqual(voucher.l10n_pe_origin_model, "sale.order")
        self.assertEqual(voucher.l10n_pe_origin_res_id, so.id)
        self.assertEqual(len(invoice.line_ids.l10n_pe_voucher_id), 1,
                         "all invoice lines under the same voucher")
