# -*- coding: utf-8 -*-
# Part of the l10n_pe_purchase_stock module.

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    stock_price_adjustment = fields.Boolean(
        string="Stock Price Adjustment",
        copy=False,
        help="Tick on a vendor credit note that grants a price discount/adjustment "
             "(not a return, not a legal cancellation). When set, the credit note "
             "lowers the inventory valuation by its own net amount instead of the "
             "native reversal behaviour. Leave it unticked for return or "
             "cancellation credit notes so the standard flow is preserved.",
    )
