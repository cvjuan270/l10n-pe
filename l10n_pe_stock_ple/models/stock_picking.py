# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .sunat_tables import TABLA_12

# Patron general: 4 alfanumericos, guion, 1 a 6 digitos.
_RE_DOCUMENT_REF = re.compile(r"^[A-Za-z0-9]{4}-\d{1,6}$")


class StockPicking(models.Model):
    _inherit = "stock.picking"

    l10n_pe_ple_document_type_id = fields.Many2one(
        "l10n_latam.document.type",
        string="Tipo de documento (T10)",
        domain="[('country_id.code', '=', 'PE'), ('internal_type', '=', False)]",
        help="Tabla 10 SUNAT. Para traslados use Guía de remisión.",
    )
    l10n_pe_ple_document_ref = fields.Char(
        string="Serie y número",
        help="Formato FFF1-000001: 4 alfanuméricos, guion, 6 numéricos.",
    )
    l10n_pe_ple_operation_type = fields.Selection(
        selection=TABLA_12,
        string="Tipo de operación (T12)",
    )

    @api.model
    def _l10n_pe_normalize_document_ref(self, value):
        """Normaliza y valida la serie-numero al formato SERIE-NNNNNN.

        - La serie son 4 caracteres alfanumericos (se pasan a mayusculas).
        - El numero se rellena con ceros a la izquierda hasta 6 digitos.
        Reutilizable por el onchange, el constraint y la importacion.
        Lanza ValidationError si no cumple el patron general.
        """
        if not value:
            return value
        value = value.strip()
        if not _RE_DOCUMENT_REF.match(value):
            raise ValidationError(
                _(
                    "El campo 'Serie y número' (%(ref)s) no cumple el formato "
                    "FFF1-000001: 4 caracteres alfanuméricos, guion y hasta "
                    "6 dígitos.",
                    ref=value,
                )
            )
        serie, number = value.split("-")
        serie = serie.upper()
        return "%s-%s" % (serie, number.zfill(6))

    def _l10n_pe_apply_document_ref(self, vals):
        # Normaliza el valor en vals (create/write) para que el dato almacenado
        # siempre quede en formato SERIE-NNNNNN, venga de la UI o de la API.
        if vals.get("l10n_pe_ple_document_ref"):
            vals["l10n_pe_ple_document_ref"] = self._l10n_pe_normalize_document_ref(
                vals["l10n_pe_ple_document_ref"]
            )
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._l10n_pe_apply_document_ref(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._l10n_pe_apply_document_ref(vals)
        return super().write(vals)

    @api.onchange("l10n_pe_ple_document_ref")
    def _onchange_l10n_pe_ple_document_ref(self):
        # Autocompleta/normaliza el valor en la UI.
        if self.l10n_pe_ple_document_ref:
            self.l10n_pe_ple_document_ref = self._l10n_pe_normalize_document_ref(
                self.l10n_pe_ple_document_ref
            )
