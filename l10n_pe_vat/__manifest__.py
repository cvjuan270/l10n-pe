# -*- coding: utf-8 -*-
# Copyright 2026 tagre.pe
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Perú - Consulta DNI/RUC",
    "summary": "Consulta el DNI o RUC del contacto contra el servicio APIs Perú "
               "(RENIEC/SUNAT) y completa automáticamente nombre, dirección, "
               "distrito, ciudad y departamento.",
    "version": "16.0.1.0.0",
    "category": "Accounting/Localizations",
    "license": "LGPL-3",
    "author": "tagre.pe, Juan Collado",
    "website": "https://tagre.pe",
    "depends": [
        "base_setup",
        "l10n_pe",
        "web",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_pe_vat/static/src/**/*.js",
            "l10n_pe_vat/static/src/**/*.xml",
            "l10n_pe_vat/static/src/**/*.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
