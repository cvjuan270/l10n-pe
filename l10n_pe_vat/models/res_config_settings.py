# -*- coding: utf-8 -*-
# Copyright 2026 tagre.pe
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_pe_vat_api_token = fields.Char(
        string="APIs Peru Token",
        help="Token for https://apisperu.com used to query DNI (RENIEC) "
             "and RUC (SUNAT).",
        config_parameter="l10n_pe_vat.api_token",
    )
