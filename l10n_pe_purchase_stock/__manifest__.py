# -*- coding: utf-8 -*-
{
    'name': 'Peru - Purchase Stock Price Adjustment',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Purchase',
    'summary': "Purchase credit notes for price discounts adjust stock valuation "
               "by their own net amount",
    'description': """
Purchase price-adjustment credit notes and stock valuation
==========================================================

.. warning::
   **ALPHA - NOT READY FOR PRODUCTION.** This module changes inventory valuation
   and posts accounting entries. It is a prototype kept for demo purposes only.
   Do not install it on a production database.

A vendor credit note issued to grant a price discount/adjustment (not a return,
not a legal cancellation) should lower the inventory valuation by *its own net
amount*. The native `purchase_stock` behaviour, when the credit note is a
reversal, undoes the invoice price correction and ignores the credit note value.

This module targets *independent* purchase credit notes linked to a purchase
order line (``in_refund`` without ``reversed_entry_id``) and explicitly flagged
with ``stock_price_adjustment``, and revalues the impacted layers using the
credit note net amount instead. See the module comments for the formula and its
conservation property.

Known limitations
-----------------
* FIFO multi-layer allocation is a plain sequential fill, not a faithful replay
  of the billed-quantity-per-layer link (see the ``TODO`` in
  ``models/account_move_line.py``). AVCO (single layer) is exact.
* Partial credit notes (``Q_nc < Q_received``) are not covered by tests.
* A discount larger than the layer value drives ``standard_price`` negative; no
  guard is in place.
""",
    'author': 'Tagre.pe,Juan D. Collado Vasquez',
    'website': 'https://github.com/cvjuan270/l10n-pe',
    'development_status': 'Alpha',
    'depends': ['purchase_stock'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'AGPL-3',
}
