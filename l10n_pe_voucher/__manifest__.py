{
    "name": "Peruvian Accounting Voucher",
    "version": "18.0.1.0.0",
    "summary": """Groups journal items by voucher (CUO) for the Peruvian
    Journal Book (Libro Diario). Related entries such as the inventory
    valuation move and its invoice share the same voucher number so they
    can be reported as a single accounting operation.""",
    "author": "Tagre.pe,Juan D. Collado Vasquez",
    "website": "https://github.com/cvjuan270/l10n-pe",
    "category": "Accounting/Financials/Localizations",
    "depends": ["account", "l10n_pe"],
    "data": [
        "security/ir.model.access.csv",
        "security/l10n_pe_voucher_security.xml",
        "wizard/l10n_pe_voucher_backfill_views.xml",
        "views/l10n_pe_voucher_views.xml",
        "views/account_move_line_views.xml",
        "views/account_move_views.xml",
        "views/menuitems.xml",
    ],
    "price": 0,
    "currency": "USD",
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "AGPL-3",
}
