# -*- coding: utf-8 -*-
# Part of the l10n_pe_purchase_stock module.

from odoo import fields
from odoo.tests import tagged
from odoo.addons.purchase_stock.tests.test_stockvaluation import TestStockValuationWithCOA


@tagged('post_install', '-at_install')
class TestPurchaseNCValuation(TestStockValuationWithCOA):
    """Vendor credit notes flagged as a stock price adjustment.

    Such a credit note must lower the inventory valuation by its own net amount
    ``N`` (company currency):
      - the on-hand part revalues the receipt layer through a negative child SVL,
      - the already-shipped part adjusts COGS through account move lines,
    keeping the conservation ``sum(SVL) + sum(COGS) == -N``.

    Every other credit note (return refund, legal reversal, standard-cost
    product) must keep the native ``purchase_stock`` behaviour.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # The price-difference machinery of purchase_stock only routes value
        # between the stock interim account and the expense account under
        # anglo-saxon accounting, which is the target setup of this module.
        cls.env.company.anglo_saxon_accounting = True

        # AVCO + real time valuation: single receipt layer, exact arithmetic.
        cls.cat.write({
            'property_cost_method': 'average',
            'property_valuation': 'real_time',
        })

        # The base test user only carries the accounting groups; we also move
        # stock around (deliveries) and confirm purchase orders.
        cls.env.user.groups_id += (
            cls.env.ref('stock.group_stock_manager')
            + cls.env.ref('purchase.group_purchase_manager')
        )

        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1)
        cls.customer_location = cls.env.ref('stock.stock_location_customers')
        cls.expense_account = cls.product1.product_tmpl_id.get_product_accounts()['expense']
        cls.stock_in_account = cls.product1.product_tmpl_id.get_product_accounts()['stock_input']

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @classmethod
    def _create_po(cls, product=None, qty=10.0, price=10.0, currency=None):
        product = product or cls.product1
        po = cls.env['purchase.order'].create({
            'partner_id': cls.partner_id.id,
            'currency_id': (currency or cls.env.company.currency_id).id,
            'order_line': [(0, 0, {
                'name': product.name,
                'product_id': product.id,
                'product_qty': qty,
                'product_uom': product.uom_id.id,
                'price_unit': price,
                'taxes_id': [(6, 0, [])],
            })],
        })
        po.button_confirm()
        return po

    def _receive(self, po, qty=None):
        receipt = po.picking_ids
        qty = qty if qty is not None else po.order_line[0].product_qty
        receipt.move_ids.move_line_ids.quantity = qty
        receipt.move_ids.picked = True
        receipt.button_validate()
        return receipt

    def _deliver(self, product, qty):
        """Ship `qty` out of stock so part of the received goods is already out."""
        move = self.env['stock.move'].create({
            'name': product.name,
            'product_id': product.id,
            'product_uom_qty': qty,
            'product_uom': product.uom_id.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.customer_location.id,
            'picking_type_id': self.warehouse.out_type_id.id,
        })
        move._action_confirm()
        move._action_assign()
        move.move_line_ids.quantity = qty
        move.picked = True
        move._action_done()
        return move

    def _adjustment_nc(self, po, qty, price, flag=True, currency=None):
        """Independent price-adjustment credit note tied to the PO line."""
        po_line = po.order_line[0]
        nc = self.env['account.move'].create({
            'move_type': 'in_refund',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.today(),
            'currency_id': (currency or po.currency_id).id,
            'stock_price_adjustment': flag,
            'invoice_line_ids': [(0, 0, {
                'name': 'price adjustment',
                'product_id': po_line.product_id.id,
                'quantity': qty,
                'price_unit': price,
                'product_uom_id': po_line.product_uom.id,
                'purchase_line_id': po_line.id,
                'tax_ids': [(6, 0, [])],
            })],
        })
        nc.action_post()
        return nc

    def _reversal_nc(self, bill, flag=True):
        """Legal reversal (credit note created with the reversal wizard)."""
        wizard = self.env['account.move.reversal'].with_context(
            active_ids=bill.ids, active_model='account.move',
        ).create({'journal_id': bill.journal_id.id})
        nc = self.env['account.move'].browse(wizard.refund_moves()['res_id'])
        nc.stock_price_adjustment = flag
        nc.action_post()
        return nc

    def _nc_svls(self, nc):
        return self.env['stock.valuation.layer'].search([
            ('account_move_line_id', 'in', nc.invoice_line_ids.ids)])

    def _cogs_amount(self, nc):
        """Net effect booked by the credit note on the expense account."""
        amls = nc.line_ids.filtered(
            lambda l: l.display_type == 'cogs' and l.account_id == self.expense_account)
        return sum(amls.mapped('balance'))

    def _interim_amount(self, nc):
        """Net effect booked by the credit note on the stock interim account."""
        amls = nc.line_ids.filtered(lambda l: l.account_id == self.stock_in_account)
        return sum(amls.mapped('balance'))

    # ------------------------------------------------------------------
    # 1. AVCO, everything still on hand
    # ------------------------------------------------------------------
    def test_avco_all_in_stock(self):
        po = self._create_po(qty=10, price=10)
        self._receive(po)
        self._bill(po, price=10)

        product = self.product1
        self.assertEqual(product.value_svl, 100.0)
        self.assertEqual(product.standard_price, 10.0)
        parent_layer = product.stock_valuation_layer_ids.sorted('id')[0]
        self.assertEqual(parent_layer.remaining_value, 100.0)

        nc = self._adjustment_nc(po, qty=10, price=2)  # N = 20

        svls = self._nc_svls(nc)
        self.assertEqual(len(svls), 1, "A single adjustment SVL is expected under AVCO")
        svl = svls[0]
        self.assertEqual(svl.value, -20.0,
                         "The SVL must lower the valuation by the credit note net amount")
        self.assertEqual(svl.quantity, 0.0, "A price adjustment SVL carries no quantity")
        self.assertFalse(svl.stock_move_id, "The adjustment SVL is not tied to a stock move")
        self.assertEqual(svl.account_move_line_id, nc.invoice_line_ids,
                         "The SVL must point back to the credit note line")
        self.assertEqual(svl.stock_valuation_layer_id, parent_layer,
                         "The child SVL must point to the receipt layer")

        self.assertEqual(parent_layer.remaining_value, 80.0,
                         "The parent remaining_value drops by the adjustment")
        self.assertEqual(product.value_svl, 80.0)
        self.assertEqual(product.standard_price, 8.0,
                         "standard_price = value_svl / quantity_svl = 80/10")

        self.assertAlmostEqual(
            sum(svls.mapped('value')) + self._cogs_amount(nc), -20.0,
            msg="Conservation: sum(SVL) + sum(COGS) == -N")

    # ------------------------------------------------------------------
    # 2. AVCO, part of the goods already delivered
    # ------------------------------------------------------------------
    def test_avco_mixed_in_and_out(self):
        po = self._create_po(qty=10, price=10)
        self._receive(po)
        self._bill(po, price=10)
        self._deliver(self.product1, 4)  # 6 units left on hand

        product = self.product1
        parent_layer = product.stock_valuation_layer_ids.sorted('id')[0]
        self.assertEqual(parent_layer.remaining_qty, 6.0)
        self.assertEqual(product.value_svl, 60.0)

        nc = self._adjustment_nc(po, qty=10, price=2)  # N = 20 -> unit discount 2

        svls = self._nc_svls(nc)
        self.assertEqual(len(svls), 1)
        svl = svls[0]
        self.assertEqual(svl.value, -12.0, "On-hand part: 6 units * -2")
        self.assertEqual(svl.stock_valuation_layer_id, parent_layer)

        cogs = self._cogs_amount(nc)
        self.assertAlmostEqual(
            cogs, -8.0,
            msg="Shipped part (4 units * -2) must REDUCE COGS, i.e. credit the expense account")

        self.assertAlmostEqual(sum(svls.mapped('value')) + cogs, -20.0,
                               msg="Conservation: sum(SVL) + sum(COGS) == -N")

        self.assertEqual(parent_layer.remaining_value, 48.0, "60 on hand - 12 of adjustment")
        self.assertEqual(product.value_svl, 48.0)
        self.assertEqual(product.standard_price, 8.0, "48 / 6 units")

    # ------------------------------------------------------------------
    # 3. Everything already sold: no SVL, the whole adjustment hits COGS
    # ------------------------------------------------------------------
    def test_avco_fully_sold(self):
        po = self._create_po(qty=10, price=10)
        self._receive(po)
        self._bill(po, price=10)
        self._deliver(self.product1, 10)  # nothing left on hand

        product = self.product1
        self.assertEqual(product.quantity_svl, 0.0)

        nc = self._adjustment_nc(po, qty=10, price=2)  # N = 20

        svls = self._nc_svls(nc)
        self.assertFalse(svls, "No adjustment SVL when nothing is on hand")

        cogs = self._cogs_amount(nc)
        self.assertAlmostEqual(cogs, -20.0, msg="The whole adjustment goes to COGS")
        self.assertAlmostEqual(sum(svls.mapped('value')) + cogs, -20.0,
                               msg="Conservation: sum(SVL) + sum(COGS) == -N")

    # ------------------------------------------------------------------
    # 4. Foreign currency credit note
    # ------------------------------------------------------------------
    def test_multicurrency_adjustment(self):
        company_currency = self.env.company.currency_id
        foreign = self.eur_currency if self.eur_currency != company_currency else self.usd_currency
        # Deterministic rate: 2 foreign units == 1 company unit.
        self.env['res.currency.rate'].search([('currency_id', '=', foreign.id)]).unlink()
        self.env['res.currency.rate'].create({
            'name': '2020-01-01',
            'rate': 2.0,
            'currency_id': foreign.id,
            'company_id': self.env.company.id,
        })

        po = self._create_po(qty=10, price=20, currency=foreign)  # 20 foreign == 10 company
        self._receive(po)
        self._bill(po, price=20)

        product = self.product1
        self.assertAlmostEqual(product.value_svl, 100.0,
                               msg="The receipt is valued in company currency")
        self.assertAlmostEqual(product.standard_price, 10.0)
        parent_layer = product.stock_valuation_layer_ids.sorted('id')[0]

        # 10 units @ 4 foreign == 2 company each -> N (company) = 20, N (doc) = 40
        nc = self._adjustment_nc(po, qty=10, price=4, currency=foreign)
        self.assertEqual(nc.currency_id, foreign)

        svls = self._nc_svls(nc)
        self.assertEqual(len(svls), 1)
        svl = svls[0]
        self.assertAlmostEqual(svl.value, -20.0,
                               msg="SVL value is in company currency (40 foreign / rate 2)")
        self.assertAlmostEqual(svl.price_diff_value, -40.0,
                               msg="price_diff_value stays in the document currency")
        self.assertAlmostEqual(parent_layer.remaining_value, 80.0)
        self.assertAlmostEqual(product.value_svl, 80.0)
        self.assertAlmostEqual(product.standard_price, 8.0)
        self.assertAlmostEqual(sum(svls.mapped('value')) + self._cogs_amount(nc), -20.0,
                               msg="Conservation holds in company currency")

    # ------------------------------------------------------------------
    # 5. Idempotency
    # ------------------------------------------------------------------
    def test_idempotency_reset_to_draft_and_repost(self):
        po = self._create_po(qty=10, price=10)
        self._receive(po)
        self._bill(po, price=10)

        nc = self._adjustment_nc(po, qty=10, price=2)
        svls = self._nc_svls(nc)
        self.assertEqual(len(svls), 1)
        self.assertEqual(svls.value, -20.0)

        # Our own guard: re-running the generation must not duplicate anything.
        new_svls, dummy = nc.invoice_line_ids._apply_price_difference()
        self.assertFalse(new_svls, "Re-applying the price difference must not create a new SVL")

        # Full round trip: back to draft and posted again.
        nc.button_draft()
        nc.action_post()

        svls_after = self._nc_svls(nc)
        self.assertEqual(svls_after, svls, "Re-posting must not duplicate the adjustment SVL")
        self.assertEqual(sum(svls_after.mapped('value')), -20.0)
        self.assertEqual(self.product1.value_svl, 80.0,
                         "The valuation is adjusted exactly once")

    # ------------------------------------------------------------------
    # 6. No regression: return refund without the flag
    # ------------------------------------------------------------------
    def test_no_regression_return_refund_without_flag(self):
        po = self._create_po(qty=10, price=10)
        receipt = self._receive(po)
        self._bill(po, price=10)
        self._return(receipt, qty=2)  # send 2 units back to the vendor

        svl_before = self.env['stock.valuation.layer'].search(
            [('product_id', '=', self.product1.id)])
        value_before = self.product1.value_svl

        refund = self._bill(po, price=10)  # native in_refund for the returned qty
        self.assertEqual(refund.move_type, 'in_refund')
        self.assertFalse(refund.reversed_entry_id)
        self.assertFalse(refund.stock_price_adjustment)

        self.assertFalse(self._nc_svls(refund),
                         "An unflagged return refund must not create our adjustment SVL")
        svl_after = self.env['stock.valuation.layer'].search(
            [('product_id', '=', self.product1.id)])
        self.assertEqual(svl_after, svl_before,
                         "Our module must not add any SVL on a native return refund")
        self.assertEqual(self.product1.value_svl, value_before,
                         "The valuation is untouched by the native return refund")

    # ------------------------------------------------------------------
    # 6b. No regression: legal reversal, even when flagged
    # ------------------------------------------------------------------
    def test_no_regression_reversal_with_flag(self):
        po = self._create_po(qty=10, price=10)
        self._receive(po)
        bill = self._bill(po, price=15)  # +5/unit price difference -> SVL +50

        product = self.product1
        bill_svl = self.env['stock.valuation.layer'].search([
            ('account_move_line_id', 'in', bill.invoice_line_ids.ids)])
        self.assertEqual(bill_svl.value, 50.0, "The bill raises the valuation by 50")
        self.assertEqual(product.value_svl, 150.0)

        # A real reversal keeps the native path even when the flag is (wrongly) set.
        reversal = self._reversal_nc(bill, flag=True)
        self.assertTrue(reversal.reversed_entry_id)
        self.assertTrue(reversal.stock_price_adjustment)

        reversal_svls = self._nc_svls(reversal)
        self.assertEqual(len(reversal_svls), 1)
        self.assertEqual(
            reversal_svls.value, -50.0,
            "The reversal must undo the bill correction (native behaviour), not apply -150")
        self.assertEqual(product.value_svl, 100.0,
                         "Back to the receipt valuation, exactly as without our module")

    # ------------------------------------------------------------------
    # 7. Standard cost is excluded
    # ------------------------------------------------------------------
    def test_standard_cost_excluded(self):
        accounts = self.product1.product_tmpl_id.get_product_accounts()
        std_cat = self.env['product.category'].create({
            'name': 'standard cost cat',
            'property_cost_method': 'standard',
            'property_valuation': 'real_time',
            'property_stock_account_input_categ_id': self.stock_input_account.id,
            'property_stock_account_output_categ_id': self.stock_output_account.id,
            'property_stock_valuation_account_id': self.stock_valuation_account.id,
            'property_stock_journal': self.stock_journal.id,
            'property_account_creditor_price_difference_categ': accounts['expense'].id,
        })
        std_product = self.env['product.product'].create({
            'name': 'standard cost product',
            'is_storable': True,
            'categ_id': std_cat.id,
            'standard_price': 10.0,
        })

        po = self._create_po(product=std_product, qty=10, price=10)
        self._receive(po)
        self._bill(po, price=10)
        value_before = std_product.value_svl

        nc = self._adjustment_nc(po, qty=10, price=2)

        self.assertFalse(self._nc_svls(nc),
                         "A standard-cost product never gets an adjustment SVL")
        self.assertEqual(std_product.standard_price, 10.0,
                         "The standard cost is not touched by the credit note")
        self.assertEqual(std_product.value_svl, value_before,
                         "The valuation of a standard-cost product is not touched")
