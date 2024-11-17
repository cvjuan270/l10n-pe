from odoo import fields, models


class L10nPeTable12(models.Model):
    _name = "l10n_pe.table.12"
    _description = "TABLA 12: TIPO DE OPERACIÓN"

    code = fields.Char()
    name = fields.Char(string="Nombre")
