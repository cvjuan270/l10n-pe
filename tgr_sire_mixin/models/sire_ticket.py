import base64
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from .sire_rest_client_mixin import SIRE_API_BASE_URL, SireApiError

_logger = logging.getLogger(__name__)

# codEstadoEnvio de SUNAT (Anexo III del manual "Servicios Web Api Ventas
# v22 Parte II"): 01 Cargado(solicitado), 02 Validando archivo (en
# proceso), 03 Procesado con errores, 04 Procesado sin errores
# (concluido), 05 En proceso, 06 Terminado. "01" NO es terminado -- es solo
# el ticket recien enviado. PROBADO EN VIVO contra SUNAT (ticket real de
# "descargar propuesta"): el estado que realmente se recibe al terminar es
# "06" ("Terminado"), no "04" -- se tratan ambos como done por si "04"
# aparece en otro tipo de operacion, pero "06" es el unico confirmado
# empiricamente hasta ahora.
SIRE_TICKET_DONE_STATE_CODES = ("04", "06")
SIRE_TICKET_ERROR_STATE_CODE = "03"


class SireTicket(models.Model):
    _name = "sire.ticket"
    _description = "SIRE Ticket (operación asíncrona SUNAT)"
    _inherit = ["sire.rest.client.mixin"]
    _order = "id desc"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    sunat_ticket_number = fields.Char(
        string="Nro. Ticket SUNAT", copy=False, index=True
    )
    cod_libro = fields.Char(string="Código de Libro", default="140000")
    operation_type = fields.Selection(
        selection=[
            ("accept_proposal", "Aceptar propuesta"),
            ("register_preliminary", "Registrar preliminar"),
            ("export_summary", "Exportar resumen"),
            ("export_proposal_detail", "Exportar detalle de propuesta"),
            ("upload_replacement", "Subir reemplazo de propuesta"),
            ("upload_new_vouchers", "Subir nuevos comprobantes"),
            ("upload_adjustments", "Subir ajustes posteriores"),
        ],
        string="Tipo de operación",
        required=True,
    )
    periodo_tributario = fields.Char(size=6, required=True)
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("sent", "Enviado"),
            ("pending", "Pendiente"),
            ("done", "Terminado"),
            ("error", "Error"),
            ("cancelled", "Cancelado"),
        ],
        default="draft",
        required=True,
        copy=False,
    )
    sunat_state_code = fields.Char(string="Código de Estado SUNAT", copy=False)
    sunat_state_label = fields.Char(string="Estado SUNAT", copy=False)
    result_filename = fields.Char(string="Nombre de Archivo", copy=False)
    result_file_type = fields.Char(string="Tipo de Archivo", copy=False)
    result_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Archivo de Resultado",
        copy=False,
    )
    error_message = fields.Text(copy=False)
    last_polled_at = fields.Datetime(copy=False)
    tus_location = fields.Char(string="TUS Location", copy=False)
    tus_offset = fields.Integer(string="TUS Offset", copy=False)

    def _sire_ticket_status_url(self):
        """URL del servicio "consultar estado de envío de ticket" (5.16 del
        manual "Servicios Web Api Ventas v22 Parte II", confirmado).

        ``perIni``/``perFin`` acotan la búsqueda por periodo tributario --
        usar el propio periodo del ticket alcanza para ubicarlo. La
        respuesta es paginada (``registros``), filtrada además por
        ``numTicket`` para quedarnos con el registro exacto.
        """
        self.ensure_one()
        return (
            f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rvierce/"
            "gestionprocesosmasivos/web/masivo/consultaestadotickets"
            f"?perIni={self.periodo_tributario}&perFin={self.periodo_tributario}"
            f"&page=1&perPage=20&numTicket={self.sunat_ticket_number}"
        )

    def _sire_ticket_download_url(self):
        """URL de descarga del archivo de resultado de un ticket terminado
        (servicio 5.17 "descargar archivo", confirmado).

        A diferencia de ``_sire_ticket_status_url``, esta URL NO se deriva
        de esa -- toma ``nomArchivoReporte``/``codTipoArchivoReporte`` del
        último poll (guardados en ``result_filename``/``result_file_type``)
        más ``codLibro``.
        """
        self.ensure_one()
        return (
            f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rvierce/"
            "gestionprocesosmasivos/web/masivo/archivoreporte"
            f"?nomArchivoReporte={self.result_filename or ''}"
            f"&codTipoArchivoReporte={self.result_file_type or ''}"
            f"&codLibro={self.cod_libro or ''}"
        )

    def action_poll(self):
        """Consulta el estado del ticket en SUNAT. Idempotente: puede
        llamarse repetidas veces sin más efecto que actualizar el estado
        local con la última respuesta de SUNAT."""
        for ticket in self:
            if ticket.state in ("draft", "cancelled") or not ticket.sunat_ticket_number:
                continue
            try:
                response = ticket._sire_request(
                    "GET",
                    ticket._sire_ticket_status_url(),
                    ticket.company_id,
                )
            except SireApiError as error:
                ticket.write({"state": "error", "error_message": str(error)})
                continue

            data = response.json()
            registros = data.get("registros") or []
            registro = next(
                (
                    r
                    for r in registros
                    if (r or {}).get("numTicket") == ticket.sunat_ticket_number
                ),
                registros[0] if registros else None,
            )
            if not registro:
                # Ticket aun no aparece en SUNAT (recien enviado) -- se
                # mantiene pendiente, sin tocar el resto de los campos.
                ticket.write({"last_polled_at": fields.Datetime.now()})
                continue

            detalle = registro.get("detalleTicket") or {}
            state_code = detalle.get("codEstadoEnvio")
            state_label = detalle.get("desEstadoEnvio")
            vals = {
                "sunat_state_code": state_code,
                "sunat_state_label": state_label,
                "last_polled_at": fields.Datetime.now(),
            }
            if state_code in SIRE_TICKET_DONE_STATE_CODES:
                # archivoReporte es hermano de detalleTicket dentro de
                # registro (confirmado contra un ticket real), NO esta
                # anidado dentro de detalleTicket.
                archivo_reporte = (registro.get("archivoReporte") or [{}])[0] or {}
                vals.update(
                    {
                        "state": "done",
                        "result_filename": archivo_reporte.get("nomArchivoReporte"),
                        "result_file_type": archivo_reporte.get("codTipoAchivoReporte"),
                    }
                )
            elif state_code == SIRE_TICKET_ERROR_STATE_CODE:
                vals.update({"state": "error", "error_message": state_label})
            else:
                vals["state"] = "pending"
            ticket.write(vals)
        return True

    def action_download_result(self):
        self.ensure_one()
        if self.state != "done":
            raise UserError(
                _("Solo se puede descargar el resultado de un ticket terminado.")
            )
        response = self._sire_request(
            "GET",
            self._sire_ticket_download_url(),
            self.company_id,
        )
        attachment = self.env["ir.attachment"].create(
            {
                "name": self.result_filename or f"{self.sunat_ticket_number}.zip",
                "datas": base64.b64encode(response.content),
                "res_model": self._name,
                "res_id": self.id,
            }
        )
        self.write({"result_attachment_id": attachment.id})
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }
