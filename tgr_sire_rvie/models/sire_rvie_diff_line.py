"""Resultado del cruce Odoo vs. propuesta SUNAT para un periodo RVIE.

Generado por ``sire.rvie.periodo.action_compare_proposal()`` -- ver plan
aprobado, seccion "Comparacion propuesta SUNAT vs. Odoo". Clave de cruce:
``(tipo CP, serie, numero)``.
"""

from odoo import api, fields, models


class SireRvieDiffLine(models.Model):
    _name = "sire.rvie.diff.line"
    _description = "SIRE RVIE - Linea de diferencia (Odoo vs. SUNAT)"
    _order = "match_status, fecha_emision, tipo_cp, serie, numero"

    periodo_id = fields.Many2one(
        "sire.rvie.periodo",
        string="Periodo RVIE",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="periodo_id.company_id",
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    match_status = fields.Selection(
        selection=[
            ("matched", "Coincide"),
            ("amount_mismatch", "Monto no coincide"),
            ("missing_in_odoo", "Falta en Odoo"),
            ("missing_in_sunat", "Falta en SUNAT"),
        ],
        string="Estado",
        required=True,
        index=True,
    )
    move_id = fields.Many2one("account.move", string="Comprobante Odoo")
    proposal_line_id = fields.Many2one(
        "sire.rvie.proposal.line",
        string="Línea de propuesta SUNAT",
    )
    tipo_cp = fields.Char(string="Tipo CP")
    serie = fields.Char()
    numero = fields.Char(string="Número")
    fecha_emision = fields.Date(string="Fecha de emisión")
    partner_name = fields.Char(string="Cliente")
    amount_taxed_odoo = fields.Monetary(string="Base Imponible Odoo")
    amount_taxed_sunat = fields.Monetary(string="Base Imponible SUNAT")
    amount_taxed_diff = fields.Monetary(
        string="Diferencia Base Imponible",
        compute="_compute_amount_diff",
        store=True,
    )
    amount_igv_odoo = fields.Monetary(string="Impuestos Odoo")
    amount_igv_sunat = fields.Monetary(string="Impuestos SUNAT")
    amount_igv_diff = fields.Monetary(
        string="Diferencia Impuestos",
        compute="_compute_amount_diff",
        store=True,
    )
    amount_odoo = fields.Monetary(string="Total Odoo")
    amount_sunat = fields.Monetary(string="Total SUNAT")
    amount_diff = fields.Monetary(
        string="Diferencia",
        compute="_compute_amount_diff",
        store=True,
    )

    @api.depends(
        "amount_odoo",
        "amount_sunat",
        "amount_taxed_odoo",
        "amount_taxed_sunat",
        "amount_igv_odoo",
        "amount_igv_sunat",
    )
    def _compute_amount_diff(self):
        for line in self:
            line.amount_diff = round(line.amount_odoo - line.amount_sunat, 2)
            line.amount_taxed_diff = round(
                line.amount_taxed_odoo - line.amount_taxed_sunat, 2
            )
            line.amount_igv_diff = round(
                line.amount_igv_odoo - line.amount_igv_sunat, 2
            )
