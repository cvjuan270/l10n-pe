{
    "name": "Asientos contables destino - Peru",
    "version": "18.0.1.0.1",
    "summary": """ permite generar los asientos de destino basados en los
    apuntes analíticos existentes en un rango de fechas específico.
    Al confirmar, se procesarán los apuntes analíticos dentro del
    período seleccionado (fecha de inicio y fecha final) y se aplicarán
    los porcentajes correspondientes según las normas de reparto
    establecidas. """,
    "author": "Tagre.pe,Juan D. Collado Vasquez",
    "website": "https://github.com/cvjuan270/l10n-pe",
    "category": "Accounting/Financials/Localizations",
    "depends": ["base", "web", "account", "analytic", "l10n_pe"],
    "data": [
        "security/ir.model.access.csv",
        "data/data.xml",
        "wizard/analytic_account_target_wizard.xml",
        "views/account_analytic_account_views.xml",
        "views/res_config_settings_views.xml",
        "views/account_analytic_line_views.xml",
        "views/menuitems.xml",
        "views/account_move_views.xml",
    ],
    "price": 50,
    "currency": "USD",
    "application": True,
    "installable": True,
    "auto_install": False,
    "license": "AGPL-3",
}
