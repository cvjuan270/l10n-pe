"""Camino B completo mockeado: wizard con adjunto fake -> subida TUS
(create + chunk) -> ticket -> registrar preliminar."""

import base64
from unittest.mock import patch

import requests

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from .common import SireRceTestMixin, sire_mock_response

# IMPORTANTE: ambos mixins hacen ``import requests`` del mismo modulo (Python
# cachea el modulo en sys.modules), asi que "sire_tus_client_mixin.requests"
# y "sire_rest_client_mixin.requests" son el MISMO objeto -- parchear
# ``requests.request`` en las dos rutas a la vez (nested ``patch``) pisa un
# mock con el otro. Cuando un test necesita mockear ambas llamadas (subida
# TUS + el GET final que recupera el numTicket), se usa UN solo ``patch``
# con una lista ``side_effect`` que cubre, en orden, las 3 llamadas HTTP
# reales del flujo (POST crear upload, PATCH subir chunk, GET numTicket).
MOCK_PATH = "odoo.addons.tgr_sire_mixin.models.sire_rest_client_mixin.requests.request"
TUS_MOCK_PATH = MOCK_PATH
SLEEP_PATH = "odoo.addons.tgr_sire_mixin.models.sire_tus_client_mixin.time.sleep"

FAKE_ZIP_BYTES = b"fake-zip-bytes"


@tagged("post_install", "-at_install")
class TestSireRceReplacementFlow(SireRceTestMixin, TransactionCase):
    def setUp(self):
        super().setUp()
        self._sire_set_company_token()

    def _create_periodo(self, **overrides):
        vals = {
            "company_id": self.env.company.id,
            "periodo_tributario": "202601",
            "local_state": "compared",
        }
        vals.update(overrides)
        return self.env["sire.rce.periodo"].create(vals)

    def _create_wizard(self, periodo, filename="reemplazo.zip", content=FAKE_ZIP_BYTES):
        return self.env["sire.rce.replacement.wizard"].create(
            {
                "periodo_id": periodo.id,
                "attachment": base64.b64encode(content),
                "attachment_filename": filename,
            }
        )

    def test_upload_replacement_then_register_preliminary(self):
        periodo = self._create_periodo()
        wizard = self._create_wizard(periodo)

        create_response = sire_mock_response(
            201, headers={"Location": "/uploads/rce-1"}
        )
        patch_response = sire_mock_response(
            204, headers={"Upload-Offset": str(len(FAKE_ZIP_BYTES))}
        )
        ticket_number_response = sire_mock_response(200, {"numTicket": "202601000123"})

        with patch(
            MOCK_PATH,
            side_effect=[create_response, patch_response, ticket_number_response],
        ) as mocked:
            result = wizard.action_upload()

        self.assertEqual(mocked.call_count, 3)
        methods_called = [call.args[0] for call in mocked.call_args_list]
        self.assertEqual([m.lower() for m in methods_called], ["post", "patch", "get"])
        self.assertEqual(result.get("type"), "ir.actions.act_window_close")

        # La subida TUS por si sola solo confirma que el archivo llego a
        # SUNAT, no que ya lo proceso/valido -- local_state NO avanza hasta
        # que se consulte el estado del ticket (igual que el camino A).
        self.assertEqual(periodo.local_state, "compared")
        ticket = periodo.last_ticket_id
        self.assertTrue(ticket)
        self.assertEqual(ticket.operation_type, "upload_replacement")
        self.assertEqual(ticket.cod_libro, "080000")
        self.assertEqual(ticket.sunat_ticket_number, "202601000123")
        self.assertEqual(ticket.state, "sent")
        self.assertEqual(ticket.tus_offset, len(FAKE_ZIP_BYTES))
        self.assertTrue(ticket.tus_location.endswith("/uploads/rce-1"))

        # Se consulta el estado del ticket: SUNAT ya termino de procesar el
        # reemplazo -> local_state pasa a 'replacement_uploaded'.
        poll_payload = {
            "registros": [
                {
                    "numTicket": "202601000123",
                    "detalleTicket": {
                        "codEstadoEnvio": "04",
                        "desEstadoEnvio": "Procesado sin errores",
                    },
                },
            ],
        }
        with patch(MOCK_PATH, return_value=sire_mock_response(200, poll_payload)):
            periodo.action_poll_ticket()
        self.assertEqual(ticket.state, "done")
        self.assertEqual(periodo.local_state, "replacement_uploaded")

        # Ya en 'replacement_uploaded': registrar preliminar es sincronico,
        # sin ticket nuevo.
        with patch(
            MOCK_PATH, return_value=sire_mock_response(200, {})
        ) as prelim_mocked:
            periodo.action_register_preliminary()
        prelim_mocked.assert_called_once()
        self.assertEqual(periodo.local_state, "preliminary_registered")

    def test_upload_replacement_requires_zip_extension(self):
        periodo = self._create_periodo()
        wizard = self._create_wizard(
            periodo, filename="reemplazo.txt", content=b"not a zip"
        )
        with patch(TUS_MOCK_PATH) as tus_mocked, self.assertRaises(UserError):
            wizard.action_upload()
        tus_mocked.assert_not_called()
        self.assertFalse(periodo.last_ticket_id)

    def test_upload_replacement_blocked_after_preliminary_registered(self):
        periodo = self._create_periodo(local_state="preliminary_registered")
        wizard = self._create_wizard(periodo)
        with patch(TUS_MOCK_PATH) as tus_mocked, self.assertRaises(UserError):
            wizard.action_upload()
        tus_mocked.assert_not_called()

    def test_upload_replacement_network_error_is_caught_not_raised(self):
        """Ver decision de diseno 7 (heredada de RVIE): si la subida TUS
        falla a mitad de camino, la excepcion se atrapa DENTRO del wizard
        (no se relanza) para que el progreso conocido sobreviva -- si se
        dejara escapar, TODA la transaccion (incluida la creacion del
        ticket) se revertiria."""
        periodo = self._create_periodo()
        wizard = self._create_wizard(periodo)

        with (
            patch(TUS_MOCK_PATH, side_effect=requests.ConnectionError("boom")),
            patch(SLEEP_PATH),
        ):
            result = wizard.action_upload()

        self.assertEqual(result.get("type"), "ir.actions.client")
        self.assertEqual(
            periodo.local_state, "compared", "no avanza si la subida falla"
        )
        ticket = periodo.last_ticket_id
        self.assertTrue(ticket)
        self.assertEqual(ticket.state, "error")
        self.assertTrue(ticket.error_message)
