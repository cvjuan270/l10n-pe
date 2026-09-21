{
    "name": "Peru - Tipo de cambio BCRP (integracion Enterprise)",
    "version": "18.0.1.1.0",
    "summary": """Modulo puente: registra el proveedor '[PE] BCRP (API
    oficial)' en el framework de tasas automaticas de currency_rate_live
    (enterprise). Se instala automaticamente cuando ambos modulos estan
    presentes.""",
    "author": "Tagre.pe,Juan D. Collado Vasquez",
    "website": "https://github.com/cvjuan270/l10n-pe",
    "category": "Accounting/Financials/Localizations",
    "depends": ["l10n_pe_currency_rate_bcrp", "currency_rate_live"],
    "data": [],
    "post_init_hook": "_l10n_pe_set_bcrp_api_provider",
    "price": 0,
    "currency": "USD",
    "application": False,
    "installable": True,
    "auto_install": True,
    "license": "AGPL-3",
}
