"""Detalle crudo de la propuesta RVIE descargada de SUNAT.

Una fila por comprobante que SUNAT entrega en el servicio de descarga de
propuesta (``exportacioncomprobantepropuesta``, ver
``sire.rvie.periodo._sire_rvie_download_proposal``). Subconjunto "comparable"
del Anexo 3 (ver plan aprobado, "Limite explicito"): NO es el archivo
completo de reemplazo -- le faltan CLU, reglas de signo finas, etc., que solo
importan al generar el ``.txt`` oficial (fuera de alcance de este ticket).
"""

from odoo import fields, models


class SireRvieProposalLine(models.Model):
    _name = "sire.rvie.proposal.line"
    _description = "SIRE RVIE - Linea de propuesta SUNAT"
    _order = "fecha_emision, tipo_cp, serie, numero"

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
    cod_car = fields.Char(string="CAR SUNAT", help="Código de Anotación de Registro.")
    tipo_cp = fields.Char(string="Tipo CP")
    serie = fields.Char()
    numero = fields.Char(string="Número")
    fecha_emision = fields.Date(string="Fecha de emisión")
    partner_id_type = fields.Char(string="Tipo Doc. Cliente")
    partner_vat = fields.Char(string="Nro. Doc. Cliente")
    partner_name = fields.Char(string="Cliente")
    amount_export = fields.Float(string="Exportación")
    amount_taxed = fields.Float(string="BI Gravada")
    amount_exempt = fields.Float(string="Exonerada")
    amount_unaffected = fields.Float(string="Inafecta")
    amount_isc = fields.Float(string="ISC")
    amount_igv = fields.Float(string="IGV / IPM")
    amount_other_taxes = fields.Float(string="Otros tributos")
    amount_total = fields.Float(string="Total CP")
    currency_code = fields.Char(string="Moneda")
    exchange_rate = fields.Float(string="Tipo de Cambio", digits=(6, 3))
    ref_fecha_emision = fields.Date(string="Fecha doc. modificado")
    ref_tipo_cp = fields.Char(string="Tipo doc. modificado")
    ref_serie = fields.Char(string="Serie doc. modificado")
    ref_numero = fields.Char(string="Número doc. modificado")
    excluded = fields.Boolean(
        string="Excluido definitivamente",
        help="Marcado por sire.rvie.exclude.voucher.wizard tras una "
        "exclusión irreversible confirmada en SUNAT.",
    )
    excluded_date = fields.Datetime(string="Fecha de exclusión")
    excluded_by_user_id = fields.Many2one("res.users", string="Excluido por")
