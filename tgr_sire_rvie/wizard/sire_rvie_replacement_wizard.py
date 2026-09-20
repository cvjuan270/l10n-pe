"""Camino B (reemplazar propuesta): sube un ``.zip`` adjuntado manualmente
vía TUS y deja el periodo listo para "Registrar preliminar".

Ver plan aprobado, decisión de diseño 5: este ticket NO genera el archivo
oficial de reemplazo (37+ campos del Anexo 3) -- solo sube el que el usuario
adjunta a mano, ya informado por el diff de ``action_compare_proposal()``.
``_prepare_replacement_file()`` es el punto de extensión documentado para
que un ticket futuro lo genere automáticamente desde el mismo dataset que ya
arma el comparador.
"""

import base64
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.tgr_sire_mixin.models.sire_rest_client_mixin import (
    SIRE_API_BASE_URL,
    SireApiError,
)

from ..models.sire_rvie_periodo import SIRE_RVIE_COD_LIBRO

_logger = logging.getLogger(__name__)

# URL confirmada contra el manual v25 (plan aprobado, seccion B): reemplazo
# y nuevos comprobantes en propuesta, se distinguen por ``codProceso``.
SIRE_RVIE_REPLACEMENT_UPLOAD_URL = (
    f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rvierce/"
    "receptorpropuesta/web/propuesta/upload"
)

# Anexo I, codProceso "Reemplazo de la Propuesta" (confirmado, ver
# tgr_sire_mixin/models/sunat_sire_tables.py::SIRE_COD_PROCESO).
SIRE_RVIE_COD_PROCESO_REEMPLAZO = "3"


class SireRvieReplacementWizard(models.TransientModel):
    _name = "sire.rvie.replacement.wizard"
    _description = "SIRE RVIE - Reemplazar propuesta (subida TUS)"
    _inherit = ["sire.tus.client.mixin", "sire.rest.client.mixin"]

    periodo_id = fields.Many2one(
        "sire.rvie.periodo",
        string="Periodo RVIE",
        required=True,
    )
    company_id = fields.Many2one(
        related="periodo_id.company_id",
        string="Compañía",
    )
    attachment = fields.Binary(string="Archivo de reemplazo (.zip)", required=True)
    attachment_filename = fields.Char(string="Nombre de archivo")

    # -- punto de extension ---------------------------------------------------
    def _prepare_replacement_file(self):
        """(filename, bytes) del archivo a subir.

        Implementación por defecto: usa el adjunto manual del wizard. Un
        ticket futuro que automatice la generación del archivo de reemplazo
        (a partir del mismo dataset que arma ``action_compare_proposal()``)
        puede sobreescribir este método sin tocar ``action_upload()``.
        """
        self.ensure_one()
        if not self.attachment:
            raise UserError(_("Debe adjuntar el archivo .zip de reemplazo."))
        filename = self.attachment_filename or "reemplazo.zip"
        return filename, base64.b64decode(self.attachment)

    def _sire_rvie_replacement_import_filename(self, filename):
        """Nombre exigido por el metadato ``nomArchivoImportacion``.

        TODO/SUPUESTO: el formato exacto (Tabla 6, Anexo 1, RS 112-2021) no
        está confirmado contra el manual v25 completo (ver plan aprobado,
        "riesgo abierto"). Se usa el propio nombre del adjunto como
        placeholder -- confirmar contra el manual antes de operar en
        producción.
        """
        return filename

    def _sire_rvie_fetch_tus_ticket_number(self, location, company):
        """Obtiene el ``numTicket`` final de una subida TUS completada.

        TODO/SUPUESTO: el plan aprobado deja explícitamente como "riesgo
        abierto" el punto exacto donde SUNAT entrega el ``numTicket`` final
        de una subida TUS (¿respuesta del último PATCH? ¿otra llamada?). Se
        asume aquí un GET sobre la propia URL de upload (``location``, la
        que devuelve el protocolo TUS en el header ``Location`` al crear el
        upload) esperando un JSON con ``numTicket`` -- confirmar contra el
        manual v25 completo o contra logs de una subida real antes de operar
        en producción (ver plan aprobado, verificación manual paso 4).
        """
        response = self._sire_request("GET", location, company)
        data = response.json()
        return (data or {}).get("numTicket")

    # -- accion principal -------------------------------------------------------
    def action_upload(self):
        self.ensure_one()
        periodo = self.periodo_id
        if periodo.local_state in ("preliminary_registered", "closed"):
            raise UserError(
                _(
                    "El periodo %s ya tiene el preliminar registrado; no se "
                    "puede reemplazar la propuesta."
                )
                % periodo.periodo_tributario
            )

        filename, file_bytes = self._prepare_replacement_file()
        if not filename.lower().endswith(".zip"):
            raise UserError(_("El archivo de reemplazo debe ser un .zip."))

        company = periodo.company_id
        metadata = {
            "filename": filename,
            "filetype": "application/zip",
            "perTributario": periodo.periodo_tributario,
            "codOrigenEnvio": "2",
            "codProceso": SIRE_RVIE_COD_PROCESO_REEMPLAZO,
            "codTipoCorrelativo": "01",
            "nomArchivoImportacion": self._sire_rvie_replacement_import_filename(
                filename
            ),
            "codLibro": SIRE_RVIE_COD_LIBRO,
        }

        # Se crea el ticket ANTES de la subida para tener donde persistir el
        # progreso (tus_location/tus_offset) entre chunks -- el mixin TUS es
        # agnostico de persistencia (ver sire_tus_client_mixin.py), es este
        # wizard quien la orquesta.
        ticket = self.env["sire.ticket"].create(
            {
                "company_id": company.id,
                "operation_type": "upload_replacement",
                "periodo_tributario": periodo.periodo_tributario,
                "state": "draft",
                "rvie_periodo_id": periodo.id,
            }
        )

        # Ver decision de diseno 7 del plan aprobado (lesson 7 del ticket):
        # si la subida TUS falla a mitad de camino, la excepcion se ATRAPA
        # aqui (no se relanza) para que el progreso conocido (location al
        # menos, offset del ultimo chunk exitoso) sobreviva -- si se dejara
        # escapar sin atrapar, TODA la transaccion (incluida la creacion de
        # este mismo ticket) se revertiria y no quedaria ningun rastro para
        # reintentar.
        location = None
        offset = 0
        numero_ticket = None
        try:
            for progress in self._tus_upload_file(
                SIRE_RVIE_REPLACEMENT_UPLOAD_URL,
                file_bytes,
                metadata,
                company,
            ):
                location = progress["location"]
                offset = progress["offset"]
            numero_ticket = self._sire_rvie_fetch_tus_ticket_number(location, company)
        except SireApiError as error:
            ticket.write(
                {
                    "state": "error",
                    "tus_location": location,
                    "tus_offset": offset,
                    "error_message": str(error),
                }
            )
            periodo.write({"last_ticket_id": ticket.id})
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Reemplazo de propuesta RVIE"),
                    "message": str(error),
                    "type": "danger",
                    "sticky": True,
                },
            }

        ticket.write(
            {
                "tus_location": location,
                "tus_offset": offset,
                "sunat_ticket_number": numero_ticket,
                "state": "sent",
            }
        )
        # local_state pasa a "replacement_uploaded" recien cuando
        # action_poll_ticket() confirme ticket.state == 'done' (via
        # _sire_rvie_sync_state_from_ticket), igual que el camino A -- la
        # subida TUS solo confirma que el archivo llego a SUNAT, no que ya
        # lo proceso/valido.
        periodo.write({"last_ticket_id": ticket.id})
        return {"type": "ir.actions.act_window_close"}
