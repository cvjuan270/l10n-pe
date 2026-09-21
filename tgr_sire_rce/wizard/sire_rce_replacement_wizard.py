"""Camino B (reemplazar propuesta): sube un ``.zip`` adjuntado manualmente
vía TUS y deja el periodo listo para "Registrar preliminar".

Calco de ``tgr_sire_rvie/wizard/sire_rvie_replacement_wizard.py``. Mismo
punto de extensión (``_prepare_replacement_file``) y mismos TODO/SUPUESTO
heredados sin resolver (formato de ``nomArchivoImportacion``, punto exacto
donde SUNAT entrega el ``numTicket`` final de una subida TUS).
"""

import base64
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.tgr_sire_mixin.models.sire_rest_client_mixin import (
    SIRE_API_BASE_URL,
    SireApiError,
)

from ..models.sire_rce_periodo import SIRE_RCE_COD_LIBRO

_logger = logging.getLogger(__name__)

# Endpoint COMPARTIDO con RVIE (mismo segmento ``rvierce/receptorpropuesta``,
# confirmado contra el manual de Compras seccion 5.3): riesgo bajo.
SIRE_RCE_REPLACEMENT_UPLOAD_URL = (
    f"{SIRE_API_BASE_URL}/v1/contribuyente/migeigv/libros/rvierce/"
    "receptorpropuesta/web/propuesta/upload"
)

# Anexo I, codProceso "Reemplazo de la Propuesta" DEL MANUAL DE COMPRAS --
# DISTINTO del "3" que usa RVIE para su propio reemplazo. Cada libro tiene
# su propio catalogo Anexo I, no se puede asumir que coinciden.
SIRE_RCE_COD_PROCESO_REEMPLAZO = "61"


class SireRceReplacementWizard(models.TransientModel):
    _name = "sire.rce.replacement.wizard"
    _description = "SIRE RCE - Reemplazar propuesta (subida TUS)"
    _inherit = ["sire.tus.client.mixin", "sire.rest.client.mixin"]

    periodo_id = fields.Many2one(
        "sire.rce.periodo",
        string="Periodo RCE",
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
        puede sobreescribir este método sin tocar ``action_upload()``.
        """
        self.ensure_one()
        if not self.attachment:
            raise UserError(_("Debe adjuntar el archivo .zip de reemplazo."))
        filename = self.attachment_filename or "reemplazo.zip"
        return filename, base64.b64decode(self.attachment)

    def _sire_rce_replacement_import_filename(self, filename):
        """Nombre exigido por el metadato ``nomArchivoImportacion``.

        TODO/SUPUESTO: el formato exacto (Tabla 6, Anexo 1, RS 112-2021) no
        está confirmado contra el manual completo de Compras. Se usa el
        propio nombre del adjunto como placeholder -- confirmar antes de
        operar en producción.
        """
        return filename

    def _sire_rce_fetch_tus_ticket_number(self, location, company):
        """Obtiene el ``numTicket`` final de una subida TUS completada.

        TODO/SUPUESTO: el punto exacto donde SUNAT entrega el ``numTicket``
        final de una subida TUS no está confirmado. Se asume aquí un GET
        sobre la propia URL de upload (``location``, la que devuelve el
        protocolo TUS en el header ``Location`` al crear el upload)
        esperando un JSON con ``numTicket`` -- mismo criterio que RVIE dejó
        sin resolver; confirmar contra logs de una subida real antes de
        operar en producción.
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
            "codProceso": SIRE_RCE_COD_PROCESO_REEMPLAZO,
            "codTipoCorrelativo": "01",
            "nomArchivoImportacion": self._sire_rce_replacement_import_filename(
                filename
            ),
            "codLibro": SIRE_RCE_COD_LIBRO,
        }

        # Se crea el ticket ANTES de la subida para tener donde persistir el
        # progreso (tus_location/tus_offset) entre chunks -- el mixin TUS es
        # agnostico de persistencia, es este wizard quien la orquesta.
        ticket = self.env["sire.ticket"].create(
            {
                "company_id": company.id,
                "cod_libro": SIRE_RCE_COD_LIBRO,
                "operation_type": "upload_replacement",
                "periodo_tributario": periodo.periodo_tributario,
                "state": "draft",
                "rce_periodo_id": periodo.id,
            }
        )

        # Ver decision de diseno 7 (heredada de RVIE): si la subida TUS
        # falla a mitad de camino, la excepcion se ATRAPA aqui (no se
        # relanza) para que el progreso conocido (location al menos, offset
        # del ultimo chunk exitoso) sobreviva -- si se dejara escapar sin
        # atrapar, TODA la transaccion (incluida la creacion de este mismo
        # ticket) se revertiria y no quedaria ningun rastro para reintentar.
        location = None
        offset = 0
        numero_ticket = None
        try:
            for progress in self._tus_upload_file(
                SIRE_RCE_REPLACEMENT_UPLOAD_URL,
                file_bytes,
                metadata,
                company,
            ):
                location = progress["location"]
                offset = progress["offset"]
            numero_ticket = self._sire_rce_fetch_tus_ticket_number(location, company)
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
                    "title": _("Reemplazo de propuesta RCE"),
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
        # _sire_rce_sync_state_from_ticket), igual que el camino A -- la
        # subida TUS solo confirma que el archivo llego a SUNAT, no que ya
        # lo proceso/valido.
        periodo.write({"last_ticket_id": ticket.id})
        return {"type": "ir.actions.act_window_close"}
