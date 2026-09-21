"""Periodo tributario RCE (``sire.rce.periodo``): consulta de periodos
habilitados, comparacion de la propuesta SUNAT contra el registro de compras
generado desde ``account.move``, aceptacion/reemplazo de propuesta, registro
preliminar y descarga de resumenes.

Calco de ``tgr_sire_rvie/models/sire_rvie_periodo.py`` -- ver plan aprobado
("Implementar tgr_sire_rce"), seccion "Riesgos y limitaciones conocidas".

PROBADO EN VIVO (periodo 202608, RUC de CLINICA MALL SALUD PERU S.A.C.,
o18_cms, 2026-09-21): ``action_check_period`` (servicio compartido) y
``action_compare_proposal``/``_sire_rce_proposal_detail_url`` (servicio
propio 5.34, antes sin confirmar) funcionan correctamente contra SUNAT real
-- el ticket asincrono termina, descarga el archivo real y el cruce contra
189 facturas de proveedor reales dio 172 "matched", con diferencias
plausibles en el resto (boletas de personas naturales sin cruce en SUNAT,
2 montos con discrepancia real). El layout de columnas del archivo de
propuesta (``_sire_rce_parse_proposal_line``) tambien quedo confirmado y
corregido contra ese archivo real -- es DISTINTO al de RVIE, no un calco.
Aun NO probados en vivo: ``action_accept_proposal``/``aceptapropuesta``,
``action_register_preliminary``/``registrapreliminares`` y
``action_download_summary`` (deliberadamente, son irreversibles/no
idempotentes -- ver plan de verificacion).

Misma decision de diseno 7 de RVIE (nunca escribir un campo de estado justo
antes de lanzar una excepcion): todo ``write()`` de
``local_state``/``sunat_periodo_state`` esta en un camino que NO relanza; los
guards de estado que SI fallan con ``UserError`` (1005/1008/1009 de
``action_register_preliminary``) lo hacen ANTES de llamar a SUNAT.
"""

import base64
import io
import logging
import zipfile
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.tgr_sire_mixin.models.sire_rest_client_mixin import (
    SIRE_API_BASE_URL,
)

from .sunat_rce_tables import SIRE_RCE_COD_TIPO_RESUMEN, SIRE_RCE_ERROR_MESSAGES

_logger = logging.getLogger(__name__)

# codLibro de RCE (Registro de Compras), confirmado contra el manual v22 --
# ver tgr_sire_mixin/models/sunat_sire_tables.py.
SIRE_RCE_COD_LIBRO = "080000"

# Estados locales desde los que SI se puede llamar a "registrar preliminar".
SIRE_RCE_PRELIMINARY_READY_STATES = ("proposal_accepted", "replacement_uploaded")

# Estados locales desde los que ya no se puede (re)aceptar/reemplazar la
# propuesta -- evita crear un segundo ticket de aceptacion en paralelo.
SIRE_RCE_ALREADY_DECIDED_STATES = (
    "proposal_accepted",
    "replacement_uploaded",
    "preliminary_registered",
    "closed",
)


class SireRcePeriodo(models.Model):
    _name = "sire.rce.periodo"
    _description = "SIRE RCE - Periodo tributario"
    _inherit = ["sire.rest.client.mixin"]
    _order = "periodo_tributario desc"
    _rec_name = "periodo_tributario"

    _sql_constraints = [
        (
            "periodo_company_uniq",
            "unique(company_id, periodo_tributario)",
            "Ya existe un periodo RCE para esta empresa y este periodo tributario.",
        ),
    ]

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    periodo_tributario = fields.Char(
        size=6,
        required=True,
        help="Formato AAAAMM, p.ej. 202601.",
    )

    # -- espejo del estado remoto (SUNAT) ------------------------------------
    sunat_periodo_state = fields.Char(
        string="Código Estado SUNAT",
        copy=False,
        help="Espejo textual de codEstado, tal como lo entrega SUNAT.",
    )
    sunat_periodo_state_label = fields.Char(string="Estado SUNAT", copy=False)

    # -- estado local (maquina de estados propia de este modulo) ------------
    local_state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("checked", "Periodo consultado"),
            ("compared", "Propuesta comparada"),
            ("proposal_accepted", "Propuesta aceptada"),
            ("replacement_uploaded", "Reemplazo subido"),
            ("preliminary_registered", "Preliminar registrado"),
            ("closed", "Cerrado"),
            ("error", "Error"),
        ],
        default="draft",
        required=True,
        copy=False,
    )

    last_ticket_id = fields.Many2one(
        "sire.ticket",
        string="Último ticket",
        copy=False,
    )
    ticket_ids = fields.One2many(
        "sire.ticket",
        "rce_periodo_id",
        string="Tickets",
    )
    ticket_count = fields.Integer(compute="_compute_ticket_count")

    proposal_line_ids = fields.One2many(
        "sire.rce.proposal.line",
        "periodo_id",
        string="Propuesta SUNAT",
    )
    diff_line_ids = fields.One2many(
        "sire.rce.diff.line",
        "periodo_id",
        string="Diferencias",
    )
    diff_count_matched = fields.Integer(
        string="Coinciden",
        compute="_compute_diff_counts",
        store=True,
    )
    diff_count_missing_odoo = fields.Integer(
        string="Faltan en Odoo",
        compute="_compute_diff_counts",
        store=True,
    )
    diff_count_missing_sunat = fields.Integer(
        string="Faltan en SUNAT",
        compute="_compute_diff_counts",
        store=True,
    )
    diff_count_amount_mismatch = fields.Integer(
        string="Montos no coinciden",
        compute="_compute_diff_counts",
        store=True,
    )
    diff_total_count = fields.Integer(
        string="Total diferencias",
        compute="_compute_diff_counts",
        store=True,
    )
    diff_taxed_matched = fields.Monetary(
        string="Base imponible coincide",
        compute="_compute_diff_counts",
        store=True,
    )
    diff_taxed_missing_sunat = fields.Monetary(
        string="Base imponible falta en SUNAT",
        compute="_compute_diff_counts",
        store=True,
    )
    diff_taxed_missing_odoo = fields.Monetary(
        string="Base imponible falta en Odoo",
        compute="_compute_diff_counts",
        store=True,
    )
    diff_igv_matched = fields.Monetary(
        string="Impuestos coincide",
        compute="_compute_diff_counts",
        store=True,
    )
    diff_igv_missing_sunat = fields.Monetary(
        string="Impuestos falta en SUNAT",
        compute="_compute_diff_counts",
        store=True,
    )
    diff_igv_missing_odoo = fields.Monetary(
        string="Impuestos falta en Odoo",
        compute="_compute_diff_counts",
        store=True,
    )
    diff_amount_matched = fields.Monetary(
        string="Total coincide",
        compute="_compute_diff_counts",
        store=True,
    )
    diff_amount_missing_sunat = fields.Monetary(
        string="Total falta en SUNAT",
        compute="_compute_diff_counts",
        store=True,
    )
    diff_amount_missing_odoo = fields.Monetary(
        string="Total falta en Odoo",
        compute="_compute_diff_counts",
        store=True,
    )

    download_summary_cod_tipo = fields.Selection(
        selection=SIRE_RCE_COD_TIPO_RESUMEN,
        string="Tipo de resumen a descargar",
        default="1",
    )
    download_summary_cod_tipo_archivo = fields.Selection(
        selection=[("0", "txt"), ("1", "excel"), ("2", "csv")],
        string="Formato de archivo",
        default="0",
        required=True,
    )

    # -- computed -------------------------------------------------------------
    def _compute_ticket_count(self):
        for periodo in self:
            periodo.ticket_count = len(periodo.ticket_ids)

    @api.depends(
        "diff_line_ids.match_status",
        "diff_line_ids.amount_odoo",
        "diff_line_ids.amount_sunat",
        "diff_line_ids.amount_taxed_odoo",
        "diff_line_ids.amount_taxed_sunat",
        "diff_line_ids.amount_igv_odoo",
        "diff_line_ids.amount_igv_sunat",
    )
    def _compute_diff_counts(self):
        for periodo in self:
            lines = periodo.diff_line_ids
            matched = lines.filtered(lambda ln: ln.match_status == "matched")
            missing_sunat = lines.filtered(lambda ln: ln.match_status == "missing_in_sunat")
            missing_odoo = lines.filtered(lambda ln: ln.match_status == "missing_in_odoo")

            periodo.diff_count_matched = len(matched)
            periodo.diff_count_missing_odoo = len(missing_odoo)
            periodo.diff_count_missing_sunat = len(missing_sunat)
            periodo.diff_count_amount_mismatch = len(
                lines.filtered(lambda ln: ln.match_status == "amount_mismatch")
            )
            periodo.diff_total_count = len(lines)

            # missing_in_sunat solo existe en Odoo (lado SUNAT vacio) y
            # missing_in_odoo solo existe en SUNAT (lado Odoo vacio) -- se
            # suma el lado que si tiene monto real en cada caso.
            periodo.diff_taxed_matched = sum(matched.mapped("amount_taxed_odoo"))
            periodo.diff_taxed_missing_sunat = sum(
                missing_sunat.mapped("amount_taxed_odoo")
            )
            periodo.diff_taxed_missing_odoo = sum(
                missing_odoo.mapped("amount_taxed_sunat")
            )
            periodo.diff_igv_matched = sum(matched.mapped("amount_igv_odoo"))
            periodo.diff_igv_missing_sunat = sum(
                missing_sunat.mapped("amount_igv_odoo")
            )
            periodo.diff_igv_missing_odoo = sum(
                missing_odoo.mapped("amount_igv_sunat")
            )
            periodo.diff_amount_matched = sum(matched.mapped("amount_odoo"))
            periodo.diff_amount_missing_sunat = sum(missing_sunat.mapped("amount_odoo"))
            periodo.diff_amount_missing_odoo = sum(missing_odoo.mapped("amount_sunat"))

    # -- constrains -------------------------------------------------------------
    @api.constrains("periodo_tributario")
    def _check_periodo_tributario(self):
        for periodo in self:
            value = periodo.periodo_tributario or ""
            if len(value) != 6 or not value.isdigit():
                raise UserError(
                    _("El periodo tributario debe tener el formato AAAAMM (6 dígitos).")
                )

    # -- URLs (servicios SIRE RCE) ---------------------------------------------
    def _sire_rce_periodos_url(self, cod_libro=SIRE_RCE_COD_LIBRO):
        """URL del servicio 5.33 "consultar año y mes del RCE" -- endpoint
        COMPARTIDO con RVIE (mismo segmento ``rvierce/padron``, solo cambia
        ``codLibro``): riesgo bajo."""
        return (
            f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rvierce/padron/"
            f"web/omisos/{cod_libro}/periodos"
        )

    def _sire_rce_accept_proposal_url(self):
        """URL del servicio 5.2 "aceptar propuesta" del manual de Compras.
        RUTA PROPIA de RCE (distinta a la de RVIE), NO probada en vivo."""
        self.ensure_one()
        return (
            f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rce/propuesta/"
            f"web/registroslibros/{self.periodo_tributario}/aceptapropuesta"
        )

    def _sire_rce_register_preliminary_url(self):
        """URL del servicio 5.4 "registrar preliminar" del manual de
        Compras. RUTA PROPIA de RCE: segmentacion distinta a la de RVIE
        (``rce/preliminar/...``, verbo en plural ``registrapreliminares``) --
        copiada tal cual del manual, NO probada en vivo."""
        self.ensure_one()
        return (
            f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rce/preliminar/"
            f"web/registroslibros/{self.periodo_tributario}/registrapreliminares"
        )

    def _sire_rce_proposal_detail_url(self, cod_tipo_archivo="0"):
        """URL del servicio 5.34 "descargar propuesta" del manual de
        Compras. Es un servicio ASINCRONO: la respuesta es ``{numTicket}``,
        no el detalle de comprobantes -- ver ``action_compare_proposal``.

        RUTA PROPIA de RCE, NO probada en vivo. El manual documenta muchos
        filtros opcionales (fecEmisionIni/Fin, codTipoCDP, numSerieCDP,
        numCDP, codInconsistencia, codCar, numDocAdquiriente, mtoDesde/
        Hasta) -- para el MVP se usan solo los parámetros obligatorios
        (``codTipoArchivo``, ``codOrigenEnvio``), igual criterio que RVIE
        tomó con su propio detalle de propuesta.
        """
        self.ensure_one()
        return (
            f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rce/propuesta/"
            f"web/propuesta/{self.periodo_tributario}/exportacioncomprobantepropuesta"
            f"?codTipoArchivo={cod_tipo_archivo}&codOrigenEnvio=2"
        )

    def _sire_rce_summary_url(self, cod_tipo_resumen, cod_tipo_archivo):
        """URL del servicio 5.35 "descargar resumen" del manual de Compras.
        Endpoint COMPARTIDO con RVIE (mismo segmento ``rvierce/resumen``) --
        riesgo medio: validar en vivo el signo/formato de ``tipoReporte``
        (RVIE tuvo el error 1056 por usar "-1" en vez de "1"). Sincrono: la
        respuesta es el buffer binario directo, no un ``numTicket``."""
        self.ensure_one()
        return (
            f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rvierce/"
            f"resumen/web/resumencomprobantes/{self.periodo_tributario}/"
            f"{cod_tipo_resumen}/{cod_tipo_archivo}/exporta"
            f"?codLibro={SIRE_RCE_COD_LIBRO}"
        )

    # -- accion: consultar periodo ------------------------------------------
    def action_check_period(self):
        """GET periodos habilitados (servicio 5.33, codLibro=080000) y
        actualiza el espejo local del estado SUNAT de ``self``."""
        for periodo in self:
            response = periodo._sire_request(
                "GET",
                periodo._sire_rce_periodos_url(),
                periodo.company_id,
            )
            data = response.json()
            state_code, state_label = periodo._sire_rce_find_period_state(data)
            vals = {
                "sunat_periodo_state": state_code,
                "sunat_periodo_state_label": state_label,
            }
            if periodo.local_state == "draft":
                vals["local_state"] = "checked"
            periodo.write(vals)
        return True

    def _sire_rce_find_period_state(self, data):
        self.ensure_one()
        if not isinstance(data, list):
            return False, False
        for ejercicio in data:
            for item in (ejercicio or {}).get("lisPeriodos") or []:
                if item.get("perTributario") == self.periodo_tributario:
                    return item.get("codEstado"), item.get("desEstado")
        return False, False

    # -- accion: descargar propuesta (asincrono) -------------------------------
    def action_compare_proposal(self):
        """Dispara la descarga de la propuesta SUNAT -- ver
        ``_sire_rce_download_proposal``."""
        self.ensure_one()
        return self._sire_rce_download_proposal()

    def _sire_rce_download_proposal(self):
        """Llama al servicio 5.34 "descargar propuesta" (asincrono: la
        respuesta es ``{numTicket}``, no el detalle de comprobantes) y crea
        el ``sire.ticket`` correspondiente.

        A diferencia del camino "aceptar propuesta"/"registrar preliminar",
        aqui NO hay un ``local_state`` al que avanzar todavia: el ticket
        recien creado esta "Enviado", no "Terminado" -- el parseo del
        archivo real (ver ``_sire_rce_parse_proposal_content``) se dispara
        recien cuando el usuario actualiza el ticket
        (``action_poll_ticket`` -> ``_sire_rce_sync_state_from_ticket``) y
        SUNAT ya lo marco como terminado.

        Mismo guard critico que RVIE (fix ``255d040``, PROBADO EN VIVO para
        RVIE): sin el guard de abajo, cada clic en "Comparar propuesta"
        dispara una llamada real a SUNAT y crea un ticket nuevo sin importar
        si el anterior ya se resolvio, acumulando tickets huerfanos en
        "Enviado" y sumando llamadas redundantes. Se bloquea solo si el
        ULTIMO ticket de este mismo tipo todavia esta en curso
        (``sent``/``pending``) -- se mira solo el ultimo (``search`` con
        ``order="id desc"``, NO ``self.ticket_ids`` filtrado: ese campo no
        garantiza el orden ``id desc`` de ``sire.ticket`` cuando los
        registros se acaban de crear en la misma transaccion), para que un
        ticket huerfano de un clic viejo no bloquee para siempre una vez que
        un ticket posterior ya termino."""
        self.ensure_one()
        last_proposal_ticket = self.env["sire.ticket"].search(
            [
                ("rce_periodo_id", "=", self.id),
                ("operation_type", "=", "export_proposal_detail"),
            ],
            order="id desc",
            limit=1,
        )
        if last_proposal_ticket.state in ("sent", "pending"):
            raise UserError(
                _(
                    "Ya hay un ticket de comparación en curso para este "
                    'periodo. Presiona "Actualizar ticket" para revisar su '
                    "estado antes de volver a comparar."
                )
            )
        response = self._sire_request(
            "GET",
            self._sire_rce_proposal_detail_url(),
            self.company_id,
        )
        data = response.json()
        ticket = self.env["sire.ticket"].create(
            {
                "company_id": self.company_id.id,
                "cod_libro": SIRE_RCE_COD_LIBRO,
                "operation_type": "export_proposal_detail",
                "periodo_tributario": self.periodo_tributario,
                "sunat_ticket_number": data.get("numTicket"),
                "state": "sent",
                "rce_periodo_id": self.id,
            }
        )
        self.write({"last_ticket_id": ticket.id})
        return ticket

    def _sire_rce_import_proposal_from_ticket(self, ticket):
        """Descarga el archivo del ticket "export_proposal_detail" ya
        terminado, (re)genera ``proposal_line_ids`` y cruza contra el
        registro de compras Odoo del periodo (``_sire_rce_cross``).

        Llamado desde ``_sire_rce_sync_state_from_ticket`` -- no crea su
        propio ``ir.attachment`` (a diferencia de
        ``sire.ticket.action_download_result``, pensado para que el usuario
        inspeccione el archivo crudo manualmente): aqui solo interesan los
        bytes para parsear.
        """
        self.ensure_one()
        content = ticket._sire_ticket_fetch_result_content()
        proposal_vals = self._sire_rce_parse_proposal_content(content)
        self.proposal_line_ids.unlink()
        if proposal_vals:
            self.env["sire.rce.proposal.line"].create(proposal_vals)
        odoo_rows = self.env["account.move"]._sire_rce_get_compras_register(
            self.company_id, self.periodo_tributario
        )
        self._sire_rce_cross(odoo_rows)
        if self.local_state in ("draft", "checked"):
            self.local_state = "compared"

    def _sire_rce_parse_proposal_content(self, content):
        """``content``: bytes del ZIP devuelto por el servicio 5.32 para un
        ticket "export_proposal_detail" de RCE.

        PROBADO EN VIVO (periodo 202608, RUC de CLINICA MALL SALUD PERU
        S.A.C., o18_cms): el contenedor SI es un ZIP con un único .txt
        delimitado por ``|``, encabezado en la primera línea -- igual
        estructura contenedora que RVIE, pero el LAYOUT de columnas es
        distinto (ver ``_sire_rce_parse_proposal_line``): no es una copia
        1:1 del de ventas.
        """
        self.ensure_one()
        with zipfile.ZipFile(io.BytesIO(content)) as zip_file:
            inner_name = zip_file.namelist()[0]
            raw_text = zip_file.read(inner_name).decode("utf-8-sig")
        body_lines = [line for line in raw_text.splitlines() if line.strip()][1:]
        return [
            self._sire_rce_parse_proposal_line(line.split("|"))
            for line in body_lines
        ]

    def _sire_rce_parse_proposal_line(self, columns):
        """Mapea una fila (columnas ya separadas por ``|``) del .txt de
        detalle de propuesta a los ``vals`` de ``sire.rce.proposal.line``.

        Índices de columna PROBADOS EN VIVO (periodo 202608, o18_cms) contra
        el encabezado real:
        ``RUC|Apellidos y Nombres o Razón social|Periodo|CAR SUNAT|Fecha de
        emisión|Fecha Vcto/Pago|Tipo CP/Doc.|Serie del CDP|Año|Nro CP o Doc.
        Nro Inicial (Rango)|Nro Final (Rango)|Tipo Doc Identidad|Nro Doc
        Identidad|Apellidos Nombres/ Razón Social|BI Gravado DG|IGV / IPM
        DG|BI Gravado DGNG|IGV / IPM DGNG|BI Gravado DNG|IGV / IPM DNG|Valor
        Adq. NG|ISC|ICBPER|Otros Trib/ Cargos|Total CP|Moneda|Tipo de
        Cambio|Fecha Emisión Doc Modificado|Tipo CP Modificado|Serie CP
        Modificado|COD. DAM O DSI|Nro CP Modificado|...(CLU1..CLU39)``.

        Layout COMPLETAMENTE DISTINTO al de RVIE (no es un calco):
        - Columnas 0/1 son el RUC/razón social del propio declarante
          (comprador), NO del proveedor -- el proveedor está en 11/12/13.
        - "Nro CP o Doc. Nro Inicial (Rango)" (col 9) es el número de
          documento real (no un tipo de rango), la columna 8 "Año" no se usa
          para RUC/comprobante.
        - La base imponible viene partida en 3 buckets según destino del
          crédito fiscal (DG = gravadas, DGNG = gravadas y no gravadas, DNG
          = no gravadas), cada uno con su propio IGV -- sin distinguir eso
          (fuera de alcance del MVP, ver FV0621), se suman los 3 en un único
          ``amount_taxed``/``amount_igv``. No hay columnas separadas de
          "exonerado"/"inafecto" como en RVIE; "Valor Adq. NG" es lo más
          cercano y se mapea a ``amount_unaffected``.
        - "COD. DAM O DSI" (col 30) se intercala entre "Serie CP Modificado"
          (col 29) y "Nro CP Modificado" (col 31) -- ojo con el desfase.
        """
        self.ensure_one()

        def col(index):
            return (
                columns[index].strip()
                if index < len(columns) and columns[index].strip()
                else False
            )

        def num(index):
            return float(col(index) or 0.0)

        return {
            "periodo_id": self.id,
            "cod_car": col(3),
            "tipo_cp": col(6),
            "serie": col(7),
            "numero": col(9),
            "fecha_emision": self._sire_rce_parse_date(col(4)),
            "partner_id_type": col(11),
            "partner_vat": col(12),
            "partner_name": col(13),
            "amount_taxed": round(num(14) + num(16) + num(18), 2),
            "amount_exempt": 0.0,
            "amount_unaffected": num(20),
            "amount_isc": num(21),
            "amount_igv": round(num(15) + num(17) + num(19), 2),
            "amount_other_taxes": round(num(22) + num(23), 2),
            "amount_total": num(24),
            "currency_code": col(25),
            "exchange_rate": num(26) or False,
            "ref_fecha_emision": self._sire_rce_parse_date(col(27)),
            "ref_tipo_cp": col(28),
            "ref_serie": col(29),
            "ref_numero": col(31),
        }

    @staticmethod
    def _sire_rce_parse_date(value):
        if not value:
            return False
        try:
            return datetime.strptime(value, "%d/%m/%Y").date()
        except ValueError:
            _logger.warning("SIRE RCE: fecha de propuesta no parseable: %r", value)
            return False

    def _sire_rce_cross(self, odoo_rows):
        """Cruza ``odoo_rows`` (lista de dicts, ver
        ``account.move._sire_rce_build_register_row``) contra
        ``self.proposal_line_ids`` por la clave de negocio ``(tipo CP,
        serie, número)`` y (re)genera ``self.diff_line_ids``."""
        self.ensure_one()
        self.diff_line_ids.unlink()

        odoo_by_key = {}
        for row in odoo_rows:
            key = self._sire_rce_cross_key(row["tipo_cp"], row["serie"], row["numero"])
            odoo_by_key.setdefault(key, row)

        proposal_by_key = {}
        for line in self.proposal_line_ids:
            key = self._sire_rce_cross_key(line.tipo_cp, line.serie, line.numero)
            proposal_by_key.setdefault(key, line)

        diff_vals = []
        for key in set(odoo_by_key) | set(proposal_by_key):
            odoo_row = odoo_by_key.get(key)
            proposal_line = proposal_by_key.get(key)

            if odoo_row and not proposal_line:
                diff_vals.append(
                    self._sire_rce_diff_vals("missing_in_sunat", odoo_row=odoo_row)
                )
            elif proposal_line and not odoo_row:
                diff_vals.append(
                    self._sire_rce_diff_vals(
                        "missing_in_odoo", proposal_line=proposal_line
                    )
                )
            else:
                amount_diff = round(
                    odoo_row["amount_total"] - proposal_line.amount_total, 2
                )
                status = "matched" if abs(amount_diff) < 0.005 else "amount_mismatch"
                diff_vals.append(
                    self._sire_rce_diff_vals(
                        status, odoo_row=odoo_row, proposal_line=proposal_line
                    )
                )
        if diff_vals:
            self.env["sire.rce.diff.line"].create(diff_vals)
        return True

    def _sire_rce_diff_vals(self, match_status, odoo_row=None, proposal_line=None):
        self.ensure_one()
        vals = {"periodo_id": self.id, "match_status": match_status}
        if odoo_row:
            vals.update(
                {
                    "move_id": odoo_row["move_id"],
                    "tipo_cp": odoo_row["tipo_cp"],
                    "serie": odoo_row["serie"],
                    "numero": odoo_row["numero"],
                    "fecha_emision": odoo_row["fecha_emision"],
                    "partner_name": odoo_row["partner_name"],
                    "amount_taxed_odoo": odoo_row["amount_taxed"],
                    "amount_igv_odoo": odoo_row["amount_igv"],
                    "amount_odoo": odoo_row["amount_total"],
                }
            )
        if proposal_line:
            vals.update(
                {
                    "proposal_line_id": proposal_line.id,
                    "tipo_cp": vals.get("tipo_cp") or proposal_line.tipo_cp,
                    "serie": vals.get("serie") or proposal_line.serie,
                    "numero": vals.get("numero") or proposal_line.numero,
                    "fecha_emision": vals.get("fecha_emision")
                    or proposal_line.fecha_emision,
                    "partner_name": vals.get("partner_name")
                    or proposal_line.partner_name,
                    "amount_taxed_sunat": proposal_line.amount_taxed,
                    "amount_igv_sunat": proposal_line.amount_igv,
                    "amount_sunat": proposal_line.amount_total,
                }
            )
        return vals

    @staticmethod
    def _sire_rce_cross_key(tipo_cp, serie, numero):
        """Normalización de ceros a la izquierda -- replicada por
        precaución del mismo hallazgo PROBADO EN VIVO de RVIE (fix
        ``0caaae5``: Odoo genera ``numero`` con ceros a la izquierda según
        el ancho de la secuencia del diario, p.ej. ``"00001134"``, mientras
        que SUNAT lo entrega sin ellos, p.ej. ``"1134"`` -- sin esta
        normalización ningún comprobante cruza). NO confirmado con un
        archivo real de RCE, pero no hay motivo para asumir que SUNAT
        entrega el número en un formato distinto para compras que para
        ventas. Se recorta el cero a la izquierda solo cuando ``numero`` es
        puramente numérico."""
        numero = numero or False
        if numero and numero.isdigit():
            numero = numero.lstrip("0") or "0"
        return (tipo_cp or False, serie or False, numero)

    def action_view_diff_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Diferencias del periodo {}").format(self.periodo_tributario),
            "res_model": "sire.rce.diff.line",
            "view_mode": "list,form",
            "domain": [("periodo_id", "=", self.id)],
            "context": {"default_periodo_id": self.id},
        }

    # -- accion: aceptar propuesta (camino A) ----------------------------------
    def action_accept_proposal(self):
        """Restringido a un solo período por llamada: cada iteración hace
        una llamada real (no idempotente) a SUNAT, así que si se permitiera
        invocar sobre varios registros a la vez y una fallara a mitad de
        camino, Odoo revertiría toda la transacción -- incluido el
        ``sire.ticket`` ya creado para un período cuya aceptación SÍ llegó a
        ejecutarse en SUNAT, dejando esa operación sin ningún rastro local
        con el que reconciliarla después.

        Limitación conocida del MVP (ver plan aprobado): el manual de
        Compras indica que la respuesta real puede traer un indicador de
        comprobantes "No Domiciliados" (``codTipoRegistro``); aquí NO se lee
        ese campo de la respuesta ni se ramifica ninguna lógica -- queda
        fuera de alcance."""
        self.ensure_one()
        if self.local_state in SIRE_RCE_ALREADY_DECIDED_STATES:
            raise UserError(
                _(
                    "El periodo %s ya tiene una propuesta aceptada o "
                    "reemplazada; no se puede volver a aceptar."
                )
                % self.periodo_tributario
            )
        response = self._sire_request(
            "POST",
            self._sire_rce_accept_proposal_url(),
            self.company_id,
        )
        data = response.json()
        ticket = self.env["sire.ticket"].create(
            {
                "company_id": self.company_id.id,
                "cod_libro": SIRE_RCE_COD_LIBRO,
                "operation_type": "accept_proposal",
                "periodo_tributario": self.periodo_tributario,
                "sunat_ticket_number": data.get("numTicket"),
                "state": "sent",
                "rce_periodo_id": self.id,
            }
        )
        self.write({"last_ticket_id": ticket.id})
        return ticket

    # -- accion: consultar/descargar el ticket vigente ---------------------
    def action_poll_ticket(self):
        """Actualiza el estado del ``last_ticket_id`` y sincroniza
        ``local_state`` si el ticket ya terminó. ``sire.ticket.action_poll()``
        nunca relanza una excepción (atrapa ``SireApiError`` y la persiste
        como ``error`` en el propio ticket, ver tgr_sire_mixin), así que este
        método tampoco necesita atrapar nada para poder escribir después."""
        self.ensure_one()
        if not self.last_ticket_id:
            raise UserError(_("Este periodo no tiene un ticket asociado."))
        self.last_ticket_id.action_poll()
        self._sire_rce_sync_state_from_ticket()
        return True

    def _sire_rce_sync_state_from_ticket(self):
        self.ensure_one()
        ticket = self.last_ticket_id
        if not ticket or ticket.state != "done":
            return
        if ticket.operation_type == "export_proposal_detail":
            # El cruce se puede refrescar en cualquier momento (no solo
            # antes de "aceptar propuesta") -- no toca local_state salvo
            # para avanzarlo desde el arranque (draft/checked -> compared).
            self._sire_rce_import_proposal_from_ticket(ticket)
            return
        if self.local_state in ("preliminary_registered", "closed"):
            return
        if ticket.operation_type == "accept_proposal":
            self.local_state = "proposal_accepted"
        elif ticket.operation_type == "upload_replacement":
            self.local_state = "replacement_uploaded"

    # -- accion: registrar preliminar ------------------------------------------
    def action_register_preliminary(self):
        """Registra el preliminar del periodo (servicio 5.4).

        Guards de estado LOCAL (ANTES de llamar a SUNAT), análogos a los
        2293/2294/2295 de RVIE pero con los códigos propios de Compras
        (1005/1008/1009 del manual v22) -- ver docstring del módulo y
        decisión de diseño 7 heredada de RVIE: si el guard falla, NO se
        llamó a SUNAT, así que no hay ningún estado remoto que haya
        cambiado."""
        self.ensure_one()
        self._sire_rce_check_register_preliminary_guard()
        self._sire_request(
            "POST",
            self._sire_rce_register_preliminary_url(),
            self.company_id,
        )
        self.write({"local_state": "preliminary_registered"})
        return True

    def _sire_rce_check_register_preliminary_guard(self):
        self.ensure_one()
        if self.local_state not in SIRE_RCE_PRELIMINARY_READY_STATES:
            if self.local_state == "preliminary_registered":
                raise UserError(SIRE_RCE_ERROR_MESSAGES[1008])
            if self.local_state == "closed":
                raise UserError(SIRE_RCE_ERROR_MESSAGES[1009])
            raise UserError(SIRE_RCE_ERROR_MESSAGES[1005])

    # -- accion: reemplazar propuesta (camino B) -------------------------------
    def action_open_replacement_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reemplazar propuesta RCE"),
            "res_model": "sire.rce.replacement.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_periodo_id": self.id},
        }

    # -- accion: descargar resumen (sincrono) ----------------------------------
    def action_download_summary(self, cod_tipo_resumen=None):
        """Llama al servicio 5.35 "descargar resumen" (SINCRONO: el buffer
        binario viene directo en la respuesta, sin pasar por
        ``sire.ticket``) y deja el resultado como adjunto descargable."""
        self.ensure_one()
        cod_tipo_resumen = cod_tipo_resumen or self.download_summary_cod_tipo
        response = self._sire_request(
            "GET",
            self._sire_rce_summary_url(
                cod_tipo_resumen,
                self.download_summary_cod_tipo_archivo,
            ),
            self.company_id,
        )
        attachment = self.env["ir.attachment"].create(
            {
                "name": f"resumen_{self.periodo_tributario}_{cod_tipo_resumen}.zip",
                "datas": base64.b64encode(response.content),
                "res_model": self._name,
                "res_id": self.id,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }
