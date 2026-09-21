{
    "name": "SIRE Registro de Compras (RCE)",
    "version": "18.0.1.0.0",
    "summary": """Integra el Registro de Compras Electronico (RCE) del SIRE
    de SUNAT: consulta de periodos habilitados, comparacion de la propuesta
    SUNAT contra el registro de compras generado desde account.move,
    aceptacion de propuesta, reemplazo via TUS y registro preliminar.
    Construido sobre tgr_sire_mixin (cliente REST/TUS y sire.ticket).
    No incluye (ver README): no domiciliados, ajustes posteriores, FV0621,
    tipo de cambio masivo, reportes estadisticos, ni exclusion/inclusion
    masiva de comprobantes.""",
    "author": "Tagre.pe,Juan D. Collado Vasquez",
    "website": "https://github.com/cvjuan270/l10n-pe",
    "category": "Accounting/Financials/Localizations",
    "depends": ["tgr_sire_mixin", "l10n_pe"],
    "data": [
        "security/sire_rce_security.xml",
        "security/ir.model.access.csv",
        "wizard/sire_rce_replacement_wizard_views.xml",
        "views/sire_rce_periodo_views.xml",
        "views/sire_rce_diff_line_views.xml",
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
