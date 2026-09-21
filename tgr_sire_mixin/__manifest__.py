{
    "name": "SIRE Mixin (SUNAT)",
    "version": "18.0.1.0.0",
    "summary": """Infraestructura compartida para integrar el SIRE de SUNAT:
    autenticacion OAuth2, cliente REST generico, cliente TUS (subida
    resumable de archivos) en Python puro y el modelo generico de ticket
    (operacion asincrona con numTicket). Agnostico de pais: no depende de
    l10n_pe -- lo consumen tgr_sire_rvie (Registro de Ventas) y, a futuro,
    tgr_sire_rce (Registro de Compras).""",
    "author": "Tagre.pe,Juan D. Collado Vasquez",
    "website": "https://github.com/cvjuan270/l10n-pe",
    "category": "Accounting/Financials/Localizations",
    "depends": ["account"],
    "data": [
        "security/sire_mixin_security.xml",
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/sire_ticket_views.xml",
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
