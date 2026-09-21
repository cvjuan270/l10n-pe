# -*- coding: utf-8 -*-
from odoo import fields, models

from .sunat_tables import TABLA_5


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_pe_existence_type = fields.Selection(
        selection=TABLA_5,
        string="Tipo de existencia (T5)",
        default="01",
        help="Tabla 5 SUNAT tipo de existencia para el Formato 13.1.",
    )
