{
    "name": "Peruvian Accounting Voucher - Reconciliation",
    "version": "18.0.1.0.0",
    "summary": """Resolves the voucher (CUO) of payment and bank/cash statement
    entries at reconciliation time, so they share the voucher of the document
    they settle along the invoice <-> payment <-> statement chain, without
    burning a correlative on a throwaway voucher.""",
    "author": "Tagre.pe,Juan D. Collado Vasquez",
    "website": "https://github.com/cvjuan270/l10n-pe",
    "category": "Accounting/Financials/Localizations",
    "depends": ["l10n_pe_voucher", "account"],
    "data": [
        "data/ir_cron.xml",
    ],
    "price": 0,
    "currency": "USD",
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "AGPL-3",
}
