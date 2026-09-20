{
    "name": "SIRE Registro de Ventas (RVIE)",
    "version": "18.0.1.0.0",
    "summary": """Integra el Registro de Ventas e Ingresos Electronico (RVIE)
    del SIRE de SUNAT: consulta de periodos habilitados, comparacion de la
    propuesta SUNAT contra el registro de ventas generado desde account.move,
    aceptacion de propuesta, reemplazo via TUS, registro preliminar y
    exclusion definitiva de comprobantes. Construido sobre tgr_sire_mixin
    (cliente REST/TUS y sire.ticket).""",
    "author": "Tagre.pe,Juan D. Collado Vasquez",
    "website": "https://github.com/cvjuan270/l10n-pe",
    "category": "Accounting/Financials/Localizations",
    "depends": ["tgr_sire_mixin", "l10n_pe"],
    "data": [
        "security/sire_rvie_security.xml",
        "security/ir.model.access.csv",
        "wizard/sire_rvie_replacement_wizard_views.xml",
        "wizard/sire_rvie_exclude_voucher_wizard_views.xml",
        "views/sire_rvie_periodo_views.xml",
        "views/sire_rvie_diff_line_views.xml",
        "views/menuitems.xml",
        "data/ir_cron.xml",
    ],
    "price": 0,
    "currency": "USD",
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "AGPL-3",
}
