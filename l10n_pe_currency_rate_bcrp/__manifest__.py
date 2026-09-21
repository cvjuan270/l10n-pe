{
    "name": "Peru - Tipo de cambio BCRP (API oficial)",
    "version": "18.0.2.1.0",
    "summary": """Actualizacion diaria del tipo de cambio PEN/USD desde la
    API oficial del BCRP (serie PD04640PD, TC SBS venta). Cada corrida
    consulta los ultimos 7 dias publicados y hace upsert de las tasas.
    Compatible con Community (cron propio); en Enterprise el modulo
    l10n_pe_currency_rate_bcrp_enterprise lo integra con currency_rate_live.""",
    "author": "Tagre.pe,Juan D. Collado Vasquez",
    "website": "https://github.com/cvjuan270/l10n-pe",
    "category": "Accounting/Financials/Localizations",
    "depends": ["account"],
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
