# -*- coding: utf-8 -*-
from odoo import fields, models


class UomUom(models.Model):
    _inherit = "uom.uom"

    l10n_pe_sunat_code = fields.Char(
        string="Código SUNAT (T6)",
        help="Tabla 6 SUNAT código de unidad de medida.",
    )
