# -*- coding: utf-8 -*-
# Part of the l10n_pe_purchase_stock module.

from odoo import models
from odoo.tools.float_utils import float_is_zero


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _is_purchase_price_adjustment_nc(self):
        """Return True for an *independent* purchase price-adjustment credit note line.

        We only act when the user explicitly flags the credit note as a stock price
        adjustment (`stock_price_adjustment`), and it is a vendor credit note
        (`in_refund`) that is NOT a reversal (`reversed_entry_id` is empty), tied to
        a purchase order line, with a non-standard cost method.

        The explicit flag is required because a discount credit note and a *return*
        credit note are otherwise indistinguishable (both are `in_refund` without
        `reversed_entry_id` and linked to the PO line). Without it we would revalue
        return refunds that the core intentionally leaves to the return stock move.
        Real reversals (legal cancellations) also keep the native behaviour.
        """
        self.ensure_one()
        move = self.move_id
        return (
            move.stock_price_adjustment
            and move.move_type == 'in_refund'
            and not move.reversed_entry_id
            and bool(self.purchase_line_id)
            and bool(self.product_id)
            and self.product_id.cost_method != 'standard'
        )

    def _generate_price_difference_vals(self, layers):
        # Dispatch price-adjustment credit notes to our own valuation logic; every
        # other case (regular bills, real reversals, returns) keeps the core path.
        # The SVL/AML values we return are created by `_apply_price_difference` and
        # then flow into the standard `_post` recompute of `standard_price` and into
        # `_validate_accounting_entries`, exactly like the native ones.
        if self._is_purchase_price_adjustment_nc():
            return self._generate_pnc_adjustment_vals(layers)
        return super()._generate_price_difference_vals(layers)

    def _generate_pnc_adjustment_vals(self, layers):
        """Build SVL/AML values so the credit note lowers valuation by its net amount.

        Magnitude comes from the credit note itself: ``unit_diff = -N / Q_nc`` in
        company currency and product UoM (a negative per-unit adjustment for a
        discount). For every impacted parent layer we split the covered quantity
        into the part still on hand (revalued through a negative child SVL) and the
        part already shipped (COGS adjustment).

        Conservation: ``sum(SVL value) + sum(COGS) == -N`` (in company currency).
        """
        self.ensure_one()
        product_uom = self.product_id.uom_id
        company_rounding = self.company_id.currency_id.rounding

        # Defensive idempotency guard: never generate a second set of layers for a
        # line that already produced one. `account_invoice._post` already skips
        # moves that own SVLs; this protects re-entrant/partial flows too.
        if self.env['stock.valuation.layer'].sudo().search_count(
                [('account_move_line_id', '=', self.id)], limit=1):
            return [], []

        # Per-unit discount in company currency and product UoM. We mirror the core
        # conversion chain of `_prepare_pdiff_vals`: `_get_gross_unit_price` already
        # negates the price for `in_refund`, so `unit_diff` is negative for a
        # discount; dividing by `currency_rate` moves it to company currency; the
        # UoM conversion aligns it with the layer (product UoM).
        unit_diff = self._get_gross_unit_price() / self.currency_rate
        unit_diff = self.product_uom_id._compute_price(unit_diff, product_uom)
        if float_is_zero(unit_diff, precision_rounding=company_rounding):
            return [], []

        # Quantity covered by the credit note, in the product UoM.
        qty_to_cover = self.product_uom_id._compute_quantity(self.quantity, product_uom)

        # NOTE ON FIFO: the core `_replay_history` cannot distribute an *independent*
        # price-adjustment credit note. Its refund branch (no `reversed_entry_id`)
        # only consumes `_is_out` layers, whereas the layers impacted here are the
        # `_is_in` receipts. We therefore allocate the covered quantity over the
        # incoming layers in valuation order (they arrive ordered by create_date).
        # AVCO is the base case (single layer) and is exact. FIFO multi-layer works
        # but uses a plain sequential fill instead of a proportional replay.
        # TODO: refine FIFO allocation to mirror the exact billed-qty-per-layer link.
        svl_vals_list = []
        aml_vals_list = []
        for layer in layers:
            if float_is_zero(qty_to_cover, precision_rounding=product_uom.rounding):
                break

            # Quantity of this layer covered by the credit note.
            invoicing_layer_qty = min(qty_to_cover, abs(layer.quantity))
            qty_to_cover -= invoicing_layer_qty

            # Split the covered qty: revalue the on-hand part first, send the rest to
            # COGS. This keeps conservation for partial credit notes too. It matches
            # the design formula (`in_stock_qty = remaining_qty`,
            # `out_qty = min(invoicing_layer_qty, quantity - remaining_qty)`) whenever
            # the credit note fully covers the layer, which is the intended workflow.
            in_stock_qty = min(invoicing_layer_qty, layer.remaining_qty)
            out_qty = invoicing_layer_qty - in_stock_qty

            new_svl_vals, new_aml_vals = self._prepare_pnc_pdiff_vals(
                layer, unit_diff, in_stock_qty, out_qty)
            svl_vals_list += new_svl_vals
            aml_vals_list += new_aml_vals

        return svl_vals_list, aml_vals_list

    def _prepare_pnc_pdiff_vals(self, layer, unit_diff, in_stock_qty, out_qty):
        """Mirror of `_prepare_pdiff_vals` with an imposed per-unit difference.

        Unlike the core method, ``unit_diff`` (company currency, product UoM) is
        given by the credit note net amount instead of being derived from
        ``aml_price_unit - layer_price_unit``. It is already negative for a
        discount, hence a negative SVL and a COGS reduction.
        """
        self.ensure_one()
        svl_vals_list = []
        aml_vals_list = []

        # --- Already-out portion: adjust COGS only, no stock impact ---
        # Convert the company-currency unit difference back to document currency and
        # to the line UoM, and express the out qty in the line UoM, exactly like the
        # core `_prepare_pdiff_vals`.
        #
        # Sign: `_prepare_pdiff_aml_vals` builds the balance as `qty * price * sign`
        # with `sign = move.direction_sign`, which is -1 for `in_refund` (it is not in
        # `get_outbound_types`). Our `unit_diff` already carries the refund sign,
        # because `_get_gross_unit_price` negates the price for `in_refund`. Passing it
        # as-is would negate twice and *raise* COGS on a discount, so we hand
        # `_prepare_pdiff_aml_vals` the document-natural (positive) price and let
        # `direction_sign` produce the credit to the expense account.
        unit_diff_curr = unit_diff * self.currency_rate
        unit_diff_curr = self.product_id.uom_id._compute_price(unit_diff_curr, self.product_uom_id)
        out_qty_line_uom = self.product_id.uom_id._compute_quantity(out_qty, self.product_uom_id)
        if (
            not self.currency_id.is_zero(unit_diff_curr * out_qty_line_uom)
            and self.product_id.valuation == 'real_time'
        ):
            aml_vals_list += self._prepare_pdiff_aml_vals(out_qty_line_uom, -unit_diff_curr)

        # --- On-hand portion: negative child SVL that lowers the parent layer ---
        if not float_is_zero(unit_diff * in_stock_qty,
                             precision_rounding=self.company_id.currency_id.rounding):
            # `price_diff_value` is stored in document currency (see stock.valuation.layer),
            # so we pass the per-unit discount converted back to document currency.
            pdiff_curr = unit_diff * self.currency_rate
            svl_vals = self._prepare_pdiff_svl_vals(layer, in_stock_qty, unit_diff, pdiff_curr)
            # TODO: a discount larger than the layer's current value drives
            # `remaining_value` (and therefore `standard_price`) negative. Allowed for
            # now per requirements; add a guard/validation if the business needs it.
            layer.remaining_value += svl_vals['value']
            svl_vals_list.append(svl_vals)

        return svl_vals_list, aml_vals_list
