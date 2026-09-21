from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from .common import SireMixinTestMixin, sire_mock_response

MOCK_PATH = "odoo.addons.tgr_sire_mixin.models.sire_rest_client_mixin.requests.request"


@tagged("post_install", "-at_install")
class TestSireTicket(SireMixinTestMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write(
            {
                "sire_client_id": "test-client-id",
                "sire_client_secret": "test-client-secret",
                "sire_sol_username": "MODDATOS",
                "sire_sol_password": "moddatos",
                "sire_access_token": "cached-token",
                "sire_token_expires_at": "2999-01-01 00:00:00",
                "sire_state": "valid",
            }
        )

    def _create_ticket(self, **overrides):
        vals = {
            "company_id": self.env.company.id,
            "operation_type": "accept_proposal",
            "periodo_tributario": "202601",
            "sunat_ticket_number": "202601000001",
            "state": "sent",
        }
        vals.update(overrides)
        return self.env["sire.ticket"].create(vals)

    @staticmethod
    def _tickets_payload(
        numero_ticket, detalle_ticket, archivo_reporte=None, cod_proceso=None
    ):
        # ``archivoReporte`` es hermano de ``detalleTicket`` dentro de
        # ``registro`` -- confirmado contra un ticket real de SUNAT, NO
        # esta anidado dentro de ``detalleTicket`` (a pesar de como lo
        # describe el manual).
        registro = {"numTicket": numero_ticket, "detalleTicket": detalle_ticket}
        if archivo_reporte is not None:
            registro["archivoReporte"] = archivo_reporte
        if cod_proceso is not None:
            registro["codProceso"] = cod_proceso
        return {"registros": [registro]}

    def test_poll_pending(self):
        ticket = self._create_ticket()
        detalle = {"codEstadoEnvio": "02", "desEstadoEnvio": "En proceso"}
        payload = self._tickets_payload(ticket.sunat_ticket_number, detalle)
        with patch(MOCK_PATH, return_value=sire_mock_response(200, payload)):
            ticket.action_poll()
        self.assertEqual(ticket.state, "pending")
        self.assertEqual(ticket.sunat_state_code, "02")

    def test_poll_done_captures_result_file(self):
        """codEstadoEnvio "06"/"Terminado" es el estado de exito confirmado
        contra un ticket real de SUNAT (ver comentario en
        ``SIRE_TICKET_DONE_STATE_CODES``)."""
        ticket = self._create_ticket(state="pending")
        detalle = {"codEstadoEnvio": "06", "desEstadoEnvio": "Terminado"}
        archivo_reporte = [
            {"nomArchivoReporte": "resultado.zip", "codTipoAchivoReporte": "00"},
        ]
        payload = self._tickets_payload(
            ticket.sunat_ticket_number,
            detalle,
            archivo_reporte,
            cod_proceso="10",
        )
        with patch(MOCK_PATH, return_value=sire_mock_response(200, payload)):
            ticket.action_poll()
        self.assertEqual(ticket.state, "done")
        self.assertEqual(ticket.result_filename, "resultado.zip")
        self.assertEqual(ticket.result_file_type, "00")
        self.assertEqual(
            ticket.cod_proceso,
            "10",
            "necesario para armar la URL de descarga (ver "
            "_sire_ticket_download_url)",
        )

    def test_poll_error_state(self):
        ticket = self._create_ticket(state="pending")
        detalle = {"codEstadoEnvio": "03", "desEstadoEnvio": "Rechazado"}
        payload = self._tickets_payload(ticket.sunat_ticket_number, detalle)
        with patch(MOCK_PATH, return_value=sire_mock_response(200, payload)):
            ticket.action_poll()
        self.assertEqual(ticket.state, "error")
        self.assertEqual(ticket.error_message, "Rechazado")

    def test_poll_not_found_yet_stays_pending(self):
        ticket = self._create_ticket()
        payload = {"registros": []}
        with patch(MOCK_PATH, return_value=sire_mock_response(200, payload)):
            ticket.action_poll()
        self.assertEqual(ticket.state, "sent")
        self.assertTrue(ticket.last_polled_at)

    def test_poll_api_error_sets_error_state(self):
        ticket = self._create_ticket()
        with patch(MOCK_PATH, return_value=sire_mock_response(500, {}, text="boom")):
            ticket.action_poll()
        self.assertEqual(ticket.state, "error")
        self.assertTrue(ticket.error_message)

    def test_poll_skips_draft_and_cancelled(self):
        draft_ticket = self._create_ticket(state="draft", sunat_ticket_number=False)
        cancelled_ticket = self._create_ticket(state="cancelled")
        with patch(MOCK_PATH) as mocked:
            (draft_ticket + cancelled_ticket).action_poll()
        mocked.assert_not_called()

    def test_download_result_requires_done_state(self):
        ticket = self._create_ticket(state="pending")
        with self.assertRaises(UserError):
            ticket.action_download_result()

    def test_download_result_creates_attachment(self):
        ticket = self._create_ticket(state="done", result_filename="resultado.zip")
        with patch(
            MOCK_PATH, return_value=sire_mock_response(200, content=b"zip-bytes")
        ):
            action = ticket.action_download_result()
        self.assertTrue(ticket.result_attachment_id)
        self.assertEqual(ticket.result_attachment_id.name, "resultado.zip")
        self.assertEqual(action["type"], "ir.actions.act_url")

    def test_download_result_url_uses_pertributario_codproceso_numticket(self):
        """PROBADO EN VIVO: los parametros documentados por el manual v22
        (``codTipoArchivoReporte``/``codLibro``) devuelven un 422 falso
        "El archivo solicitado no existe" (2244) incluso para un ticket
        recien terminado. Una integracion previa que si funcionaba en
        produccion arma esta misma URL con ``perTributario``/``codProceso``/
        ``numTicket`` -- confirmado igual en vivo (200 OK, ZIP real)."""
        ticket = self._create_ticket(
            state="done",
            result_filename="resultado.zip",
            cod_proceso="10",
        )
        with patch(
            MOCK_PATH, return_value=sire_mock_response(200, content=b"zip-bytes")
        ) as mocked:
            ticket.action_download_result()
        url = mocked.call_args[0][1]
        self.assertIn("nomArchivoReporte=resultado.zip", url)
        self.assertIn(f"perTributario={ticket.periodo_tributario}", url)
        self.assertIn("codProceso=10", url)
        self.assertIn(f"numTicket={ticket.sunat_ticket_number}", url)
        self.assertNotIn("codTipoArchivoReporte", url)
        self.assertNotIn("codLibro", url)
