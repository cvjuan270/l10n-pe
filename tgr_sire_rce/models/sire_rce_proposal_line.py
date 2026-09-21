"""Detalle crudo de la propuesta RCE descargada de SUNAT.

Una fila por comprobante que SUNAT entrega en el servicio de descarga de
propuesta (``exportacioncomprobantepropuesta``, ver
``sire.rce.periodo._sire_rce_download_proposal``). Calco de
``tgr_sire_rvie/models/sire_rvie_proposal_line.py`` sin ``amount_export``
(no aplica a compras) y sin los campos de exclusion (``excluded*``, ver plan
aprobado decision 0.b: sin wizard de exclusion en el MVP de RCE, nada los
llenaria).
"""

from odoo import fields, models


class SireRceProposalLine(models.Model):
    _name = "sire.rce.proposal.line"
    _description = "SIRE RCE - Linea de propuesta SUNAT"
    _order = "fecha_emision, tipo_cp, serie, numero"

    periodo_id = fields.Many2one(
        "sire.rce.periodo",
        string="Periodo RCE",
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
    cod_tipo_registro = fields.Char(
        string="Tipo de Registro SUNAT",
        help="Espejo crudo de codTipoRegistro (1 doméstico / 2 no "
        "domiciliado), tal como lo entrega SUNAT. Sin lógica de negocio "
        "asociada -- ver plan aprobado, decisión 0.c (preparación para un "
        "futuro soporte de 'No Domiciliados', fuera de este MVP).",
    )
    tipo_cp = fields.Char(string="Tipo CP")
    serie = fields.Char()
    numero = fields.Char(string="Número")
    fecha_emision = fields.Date(string="Fecha de emisión")
    partner_id_type = fields.Char(string="Tipo Doc. Proveedor")
    partner_vat = fields.Char(string="Nro. Doc. Proveedor")
    partner_name = fields.Char(string="Proveedor")
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
