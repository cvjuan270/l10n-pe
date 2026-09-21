"""Periodo tributario RVIE (``sire.rvie.periodo``): consulta de periodos
habilitados, comparacion de la propuesta SUNAT contra el registro de ventas
generado desde ``account.move``, aceptacion/reemplazo de propuesta, registro
preliminar y descarga de resumenes.

Ver plan aprobado, "Flujo UI" y decision de diseno 7 (nunca escribir un
campo de estado justo antes de lanzar una excepcion): todo ``write()`` de
``local_state``/``sunat_periodo_state`` en este modulo esta en un camino que
NO relanza -- si la llamada a SUNAT falla, la excepcion se propaga sin haber
escrito nada antes; los guards de estado que SI fallan con ``UserError``
(2293/2294/2295 de ``action_register_preliminary``) lo hacen ANTES de llamar
a SUNAT, asi que no hay ningun estado remoto que haya cambiado y nada que
persistir.
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
from odoo.addons.tgr_sire_mixin.models.sunat_sire_tables import (
    SIRE_COD_TIPO_ARCHIVO,
    SIRE_ERROR_MESSAGES,
)

from .sunat_rvie_tables import SIRE_COD_TIPO_RESUMEN

_logger = logging.getLogger(__name__)

# codLibro de RVIE (Registro de Ventas e Ingresos), confirmado contra el
# manual v25 -- ver tgr_sire_mixin/models/sunat_sire_tables.py.
SIRE_RVIE_COD_LIBRO = "140000"

# Estados locales desde los que SI se puede llamar a "registrar preliminar".
SIRE_RVIE_PRELIMINARY_READY_STATES = ("proposal_accepted", "replacement_uploaded")

# Estados locales desde los que ya no se puede (re)aceptar/reemplazar la
# propuesta -- evita crear un segundo ticket de aceptacion en paralelo.
SIRE_RVIE_ALREADY_DECIDED_STATES = (
    "proposal_accepted",
    "replacement_uploaded",
    "preliminary_registered",
    "closed",
)


class SireRviePeriodo(models.Model):
    _name = "sire.rvie.periodo"
    _description = "SIRE RVIE - Periodo tributario"
    _inherit = ["sire.rest.client.mixin"]
    _order = "periodo_tributario desc"
    _rec_name = "periodo_tributario"

    _sql_constraints = [
        (
            "periodo_company_uniq",
            "unique(company_id, periodo_tributario)",
            "Ya existe un periodo RVIE para esta empresa y este periodo tributario.",
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
        "rvie_periodo_id",
        string="Tickets",
    )
    ticket_count = fields.Integer(compute="_compute_ticket_count")

    proposal_line_ids = fields.One2many(
        "sire.rvie.proposal.line",
        "periodo_id",
        string="Propuesta SUNAT",
    )
    diff_line_ids = fields.One2many(
        "sire.rvie.diff.line",
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
        selection=SIRE_COD_TIPO_RESUMEN,
        string="Tipo de resumen a descargar",
        default="1",
    )
    download_summary_cod_tipo_archivo = fields.Selection(
        selection=SIRE_COD_TIPO_ARCHIVO,
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

    # -- URLs (servicios SIRE RVIE) ---------------------------------------------
    def _sire_rvie_periodos_url(self, cod_libro=SIRE_RVIE_COD_LIBRO):
        return (
            f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rvierce/padron/"
            f"web/omisos/{cod_libro}/periodos"
        )

    def _sire_rvie_accept_proposal_url(self):
        self.ensure_one()
        return (
            f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rvie/propuesta/"
            f"web/propuesta/{self.periodo_tributario}/aceptapropuesta"
        )

    def _sire_rvie_register_preliminary_url(self):
        self.ensure_one()
        return (
            f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rvierce/"
            f"gestionlibro/web/registroslibros/{self.periodo_tributario}"
            "/registrapreliminar"
        )

    def _sire_rvie_exclude_voucher_url(self, cod_car):
        self.ensure_one()
        return (
            f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rvie/propuesta/"
            f"web/propuesta/{self.periodo_tributario}/retiracomprobante"
            f"?codCar={cod_car}&codSituacion=0"
        )

    def _sire_rvie_proposal_detail_url(self, cod_tipo_archivo="0"):
        """URL del servicio 5.18 "descargar propuesta" (confirmado contra
        el manual "Servicios Web Api Ventas v22 Parte II").

        Es un servicio ASINCRONO: la respuesta es ``{numTicket}``, no el
        detalle de comprobantes -- ver ``action_compare_proposal``.
        ``codTipoArchivo`` es obligatorio. El Anexo IV general lista 0 txt/
        1 excel/2 csv, pero PROBADO EN VIVO contra SUNAT: este servicio
        rechaza ``2`` (csv) con el error 1059 "Código tipo de Archivo no
        permitido o no valido" -- solo se confirmo ``0`` (txt, igual que
        los ejemplos del propio manual) como valido. Default a txt.
        """
        self.ensure_one()
        return (
            f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rvie/propuesta/"
            f"web/propuesta/{self.periodo_tributario}/exportapropuesta"
            f"?codTipoArchivo={cod_tipo_archivo}"
        )

    def _sire_rvie_summary_url(self, cod_tipo_resumen, cod_tipo_archivo):
        """URL del servicio 5.20 "descargar resumen" (confirmado contra el
        manual "Servicios Web Api Ventas v22 Parte II"). A diferencia de la
        mayoria de servicios RVIE, este es SINCRONO: la respuesta es el
        buffer binario directo, no un ``numTicket`` -- ver
        ``action_download_summary``."""
        self.ensure_one()
        return (
            f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rvierce/"
            f"resumen/web/resumencomprobantes/{self.periodo_tributario}/"
            f"{cod_tipo_resumen}/{cod_tipo_archivo}/exporta"
            f"?codLibro={SIRE_RVIE_COD_LIBRO}"
        )

    # -- accion: consultar periodo ------------------------------------------
    def action_check_period(self):
        """GET periodos habilitados (servicio 5.2, codLibro=140000) y
        actualiza el espejo local del estado SUNAT de ``self``."""
        for periodo in self:
            response = periodo._sire_request(
                "GET",
                periodo._sire_rvie_periodos_url(),
                periodo.company_id,
            )
            data = response.json()
            state_code, state_label = periodo._sire_rvie_find_period_state(data)
            vals = {
                "sunat_periodo_state": state_code,
                "sunat_periodo_state_label": state_label,
            }
            if periodo.local_state == "draft":
                vals["local_state"] = "checked"
            periodo.write(vals)
        return True

    def _sire_rvie_find_period_state(self, data):
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
        ``_sire_rvie_download_proposal``."""
        self.ensure_one()
        return self._sire_rvie_download_proposal()

    def _sire_rvie_download_proposal(self):
        """Llama al servicio 5.18 "descargar propuesta" (confirmado,
        asincrono: la respuesta es ``{numTicket}``, no el detalle de
        comprobantes) y crea el ``sire.ticket`` correspondiente.

        A diferencia del camino "aceptar propuesta"/"registrar preliminar",
        aqui NO hay un ``local_state`` al que avanzar todavia: el ticket
        recien creado esta "Enviado", no "Terminado" -- el parseo del
        archivo real (ver ``_sire_rvie_parse_proposal_content``) se dispara
        recien cuando el usuario actualiza el ticket
        (``action_poll_ticket`` -> ``_sire_rvie_sync_state_from_ticket``) y
        SUNAT ya lo marco como terminado."""
        self.ensure_one()
        response = self._sire_request(
            "GET",
            self._sire_rvie_proposal_detail_url(),
            self.company_id,
        )
        data = response.json()
        ticket = self.env["sire.ticket"].create(
            {
                "company_id": self.company_id.id,
                "operation_type": "export_proposal_detail",
                "periodo_tributario": self.periodo_tributario,
                "sunat_ticket_number": data.get("numTicket"),
                "state": "sent",
                "rvie_periodo_id": self.id,
            }
        )
        self.write({"last_ticket_id": ticket.id})
        return ticket

    def _sire_rvie_import_proposal_from_ticket(self, ticket):
        """Descarga el archivo del ticket "export_proposal_detail" ya
        terminado, (re)genera ``proposal_line_ids`` y cruza contra el
        registro de ventas Odoo del periodo (``_sire_rvie_cross``).

        Llamado desde ``_sire_rvie_sync_state_from_ticket`` -- no crea su
        propio ``ir.attachment`` (a diferencia de
        ``sire.ticket.action_download_result``, pensado para que el
        usuario inspeccione el archivo crudo manualmente): aqui solo
        interesan los bytes para parsear.
        """
        self.ensure_one()
        content = ticket._sire_ticket_fetch_result_content()
        proposal_vals = self._sire_rvie_parse_proposal_content(content)
        self.proposal_line_ids.unlink()
        if proposal_vals:
            self.env["sire.rvie.proposal.line"].create(proposal_vals)
        odoo_rows = self.env["account.move"]._sire_rvie_get_ventas_register(
            self.company_id, self.periodo_tributario
        )
        self._sire_rvie_cross(odoo_rows)
        if self.local_state in ("draft", "checked"):
            self.local_state = "compared"

    def _sire_rvie_parse_proposal_content(self, content):
        """``content``: bytes del ZIP devuelto por el servicio 5.17 para un
        ticket "export_proposal_detail" -- PROBADO EN VIVO contra un
        archivo real de SUNAT (Comparar propuesta, periodo 202609): dentro
        del ZIP hay un unico .txt delimitado por ``|`` con encabezado en la
        primera linea (columnas: Ruc, Razon Social, Periodo, CAR SUNAT,
        Fecha de emision, Fecha Vcto/Pago, Tipo CP/Doc., Serie del CDP, Nro
        CP o Doc. Nro Inicial (Rango), Nro Final (Rango), Tipo Doc
        Identidad, Nro Doc Identidad, Apellidos Nombres/Razon Social, Valor
        Facturado Exportacion, BI Gravada, Dscto BI, IGV / IPM, Dscto IGV /
        IPM, Mto Exonerado, Mto Inafecto, ISC, BI Grav IVAP, IVAP, ICBPER,
        Otros Tributos, Total CP, Moneda, Tipo Cambio, Fecha Emision Doc
        Modificado, Tipo CP Modificado, Serie CP Modificado, Nro CP
        Modificado, ...). NO es JSON (a diferencia de lo que asumia una
        version anterior de este parseo) ni el formato "Anexo IV" generico
        de otros servicios SIRE -- es propio de este export.
        """
        self.ensure_one()
        with zipfile.ZipFile(io.BytesIO(content)) as zip_file:
            inner_name = zip_file.namelist()[0]
            raw_text = zip_file.read(inner_name).decode("utf-8-sig")
        body_lines = [line for line in raw_text.splitlines() if line.strip()][1:]
        return [
            self._sire_rvie_parse_proposal_line(line.split("|"))
            for line in body_lines
        ]

    def _sire_rvie_parse_proposal_line(self, columns):
        """Mapea una fila (columnas ya separadas por ``|``) del .txt de
        detalle de propuesta a los ``vals`` de ``sire.rvie.proposal.line``.
        Indices de columna confirmados contra un archivo real (ver
        ``_sire_rvie_parse_proposal_content``)."""
        self.ensure_one()

        def col(index):
            return (
                columns[index].strip()
                if index < len(columns) and columns[index].strip()
                else False
            )

        return {
            "periodo_id": self.id,
            "cod_car": col(3),
            "tipo_cp": col(6),
            "serie": col(7),
            "numero": col(8),
            "fecha_emision": self._sire_rvie_parse_date(col(4)),
            "partner_id_type": col(10),
            "partner_vat": col(11),
            "partner_name": col(12),
            "amount_export": float(col(13) or 0.0),
            "amount_taxed": float(col(14) or 0.0),
            "amount_exempt": float(col(18) or 0.0),
            "amount_unaffected": float(col(19) or 0.0),
            "amount_isc": float(col(20) or 0.0),
            "amount_igv": float(col(16) or 0.0),
            "amount_other_taxes": float(col(24) or 0.0),
            "amount_total": float(col(25) or 0.0),
            "currency_code": col(26),
            "exchange_rate": float(col(27) or 0.0) or False,
            "ref_fecha_emision": self._sire_rvie_parse_date(col(28)),
            "ref_tipo_cp": col(29),
            "ref_serie": col(30),
            "ref_numero": col(31),
        }

    @staticmethod
    def _sire_rvie_parse_date(value):
        if not value:
            return False
        try:
            return datetime.strptime(value, "%d/%m/%Y").date()
        except ValueError:
            _logger.warning("SIRE RVIE: fecha de propuesta no parseable: %r", value)
            return False

    def _sire_rvie_cross(self, odoo_rows):
        """Cruza ``odoo_rows`` (lista de dicts, ver
        ``account.move._sire_rvie_build_register_row``) contra
        ``self.proposal_line_ids`` por la clave de negocio ``(tipo CP,
        serie, número)`` y (re)genera ``self.diff_line_ids``."""
        self.ensure_one()
        self.diff_line_ids.unlink()

        odoo_by_key = {}
        for row in odoo_rows:
            key = self._sire_rvie_cross_key(row["tipo_cp"], row["serie"], row["numero"])
            odoo_by_key.setdefault(key, row)

        proposal_by_key = {}
        for line in self.proposal_line_ids:
            key = self._sire_rvie_cross_key(line.tipo_cp, line.serie, line.numero)
            proposal_by_key.setdefault(key, line)

        diff_vals = []
        for key in set(odoo_by_key) | set(proposal_by_key):
            odoo_row = odoo_by_key.get(key)
            proposal_line = proposal_by_key.get(key)

            if odoo_row and not proposal_line:
                diff_vals.append(
                    self._sire_rvie_diff_vals("missing_in_sunat", odoo_row=odoo_row)
                )
            elif proposal_line and not odoo_row:
                diff_vals.append(
                    self._sire_rvie_diff_vals(
                        "missing_in_odoo", proposal_line=proposal_line
                    )
                )
            else:
                amount_diff = round(
                    odoo_row["amount_total"] - proposal_line.amount_total, 2
                )
                status = "matched" if abs(amount_diff) < 0.005 else "amount_mismatch"
                diff_vals.append(
                    self._sire_rvie_diff_vals(
                        status, odoo_row=odoo_row, proposal_line=proposal_line
                    )
                )
        if diff_vals:
            self.env["sire.rvie.diff.line"].create(diff_vals)
        return True

    def _sire_rvie_diff_vals(self, match_status, odoo_row=None, proposal_line=None):
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
    def _sire_rvie_cross_key(tipo_cp, serie, numero):
        """PROBADO EN VIVO (periodo 202609, comprobante B001-1134): Odoo
        genera ``numero`` con ceros a la izquierda segun el ancho de la
        secuencia del diario (``"00001134"``), pero el .txt de propuesta de
        SUNAT lo entrega sin ellos (``"1134"``) -- sin esta normalizacion
        NINGUN comprobante cruza (aparecen duplicados como
        missing_in_odoo + missing_in_sunat aunque el documento exista en
        ambos lados). Se recorta el cero a la izquierda solo cuando
        ``numero`` es puramente numerico; un numero con letras (poco
        usual pero no descartable) se deja tal cual."""
        numero = numero or False
        if numero and numero.isdigit():
            numero = numero.lstrip("0") or "0"
        return (tipo_cp or False, serie or False, numero)

    def action_view_diff_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Diferencias del periodo {}").format(self.periodo_tributario),
            "res_model": "sire.rvie.diff.line",
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
        con el que reconciliarla después."""
        self.ensure_one()
        if self.local_state in SIRE_RVIE_ALREADY_DECIDED_STATES:
            raise UserError(
                _(
                    "El periodo %s ya tiene una propuesta aceptada o "
                    "reemplazada; no se puede volver a aceptar."
                )
                % self.periodo_tributario
            )
        response = self._sire_request(
            "POST",
            self._sire_rvie_accept_proposal_url(),
            self.company_id,
        )
        data = response.json()
        ticket = self.env["sire.ticket"].create(
            {
                "company_id": self.company_id.id,
                "operation_type": "accept_proposal",
                "periodo_tributario": self.periodo_tributario,
                "sunat_ticket_number": data.get("numTicket"),
                "state": "sent",
                "rvie_periodo_id": self.id,
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
        self._sire_rvie_sync_state_from_ticket()
        return True

    def _sire_rvie_sync_state_from_ticket(self):
        self.ensure_one()
        ticket = self.last_ticket_id
        if not ticket or ticket.state != "done":
            return
        if ticket.operation_type == "export_proposal_detail":
            # El cruce se puede refrescar en cualquier momento (no solo
            # antes de "aceptar propuesta") -- no toca local_state salvo
            # para avanzarlo desde el arranque (draft/checked -> compared).
            self._sire_rvie_import_proposal_from_ticket(ticket)
            return
        if self.local_state in ("preliminary_registered", "closed"):
            return
        if ticket.operation_type == "accept_proposal":
            self.local_state = "proposal_accepted"
        elif ticket.operation_type == "upload_replacement":
            self.local_state = "replacement_uploaded"

    # -- accion: registrar preliminar ------------------------------------------
    def action_register_preliminary(self):
        """Registra el preliminar del periodo (servicio 5.9).

        Guards de estado LOCAL (ANTES de llamar a SUNAT) que replican
        2293/2294/2295 del manual v25 -- ver docstring del modulo y
        decision de diseno 7 del plan aprobado: si el guard falla, NO se
        llamó a SUNAT, así que no hay ningún estado remoto que haya
        cambiado y nada que conservar; el mensaje de la excepción es el
        único feedback necesario."""
        self.ensure_one()
        self._sire_rvie_check_register_preliminary_guard()
        self._sire_request(
            "POST",
            self._sire_rvie_register_preliminary_url(),
            self.company_id,
        )
        self.write({"local_state": "preliminary_registered"})
        return True

    def _sire_rvie_check_register_preliminary_guard(self):
        self.ensure_one()
        if self.local_state not in SIRE_RVIE_PRELIMINARY_READY_STATES:
            if self.local_state == "preliminary_registered":
                raise UserError(SIRE_ERROR_MESSAGES[2294])
            if self.local_state == "closed":
                raise UserError(SIRE_ERROR_MESSAGES[2295])
            raise UserError(SIRE_ERROR_MESSAGES[2293])

    # -- accion: reemplazar propuesta (camino B) -------------------------------
    def action_open_replacement_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reemplazar propuesta RVIE"),
            "res_model": "sire.rvie.replacement.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_periodo_id": self.id},
        }

    # -- accion: excluir comprobante -------------------------------------------
    def action_open_exclude_voucher_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Excluir comprobante (irreversible)"),
            "res_model": "sire.rvie.exclude.voucher.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_periodo_id": self.id},
        }

    # -- accion: descargar resumen (sincrono) ----------------------------------
    def action_download_summary(self, cod_tipo_resumen=None):
        """Llama al servicio 5.20 "descargar resumen" (confirmado,
        SINCRONO: el buffer binario viene directo en la respuesta, sin
        pasar por ``sire.ticket``) y deja el resultado como adjunto
        descargable."""
        self.ensure_one()
        cod_tipo_resumen = cod_tipo_resumen or self.download_summary_cod_tipo
        response = self._sire_request(
            "GET",
            self._sire_rvie_summary_url(
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
