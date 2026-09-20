"""Camino A completo mockeado: consultar periodo -> aceptar propuesta ->
actualizar ticket -> ``local_state == 'proposal_accepted'``."""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from .common import SireRvieTestMixin, sire_mock_response

MOCK_PATH = "odoo.addons.tgr_sire_mixin.models.sire_rest_client_mixin.requests.request"


@tagged("post_install", "-at_install")
class TestSireRviePeriodoFlow(SireRvieTestMixin, TransactionCase):
    def setUp(self):
        super().setUp()
        self._sire_set_company_token()

    def _create_periodo(self, **overrides):
        vals = {"company_id": self.env.company.id, "periodo_tributario": "202601"}
        vals.update(overrides)
        return self.env["sire.rvie.periodo"].create(vals)

    def test_camino_a_check_accept_poll(self):
        periodo = self._create_periodo()

        periodos_payload = [
            {
                "numEjercicio": "2026",
                "desEstado": "Vigente",
                "lisPeriodos": [
                    {
                        "perTributario": "202601",
                        "codEstado": "05",
                        "desEstado": "Propuesta pendiente",
                    },
                ],
            }
        ]
        with patch(
            MOCK_PATH, return_value=sire_mock_response(200, periodos_payload)
        ) as mocked:
            periodo.action_check_period()
        mocked.assert_called_once()
        self.assertEqual(periodo.sunat_periodo_state, "05")
        self.assertEqual(periodo.sunat_periodo_state_label, "Propuesta pendiente")
        self.assertEqual(periodo.local_state, "checked")

        accept_payload = {"numTicket": "202601000099"}
        with patch(
            MOCK_PATH, return_value=sire_mock_response(200, accept_payload)
        ) as mocked:
            tickets = periodo.action_accept_proposal()
        mocked.assert_called_once()
        self.assertEqual(len(tickets), 1)
        self.assertEqual(periodo.last_ticket_id, tickets)
        self.assertEqual(periodo.last_ticket_id.operation_type, "accept_proposal")
        self.assertEqual(periodo.last_ticket_id.sunat_ticket_number, "202601000099")
        self.assertEqual(periodo.last_ticket_id.rvie_periodo_id, periodo)
        self.assertEqual(
            periodo.local_state,
            "checked",
            "no cambia hasta que el ticket termine",
        )

        poll_payload = {
            "registros": [
                {
                    "numTicket": "202601000099",
                    "detalleTicket": {
                        "codEstadoEnvio": "04",
                        "desEstadoEnvio": "Procesado sin errores",
                    },
                },
            ],
        }
        with patch(MOCK_PATH, return_value=sire_mock_response(200, poll_payload)):
            periodo.action_poll_ticket()

        self.assertEqual(periodo.last_ticket_id.state, "done")
        self.assertEqual(periodo.local_state, "proposal_accepted")
        self.assertIn(periodo.last_ticket_id, periodo.ticket_ids)
        self.assertEqual(periodo.ticket_count, 1)

    def test_check_period_not_found_in_response(self):
        periodo = self._create_periodo()
        with patch(MOCK_PATH, return_value=sire_mock_response(200, [])):
            periodo.action_check_period()
        self.assertFalse(periodo.sunat_periodo_state)
        self.assertEqual(periodo.local_state, "checked")

    def test_poll_ticket_without_ticket_raises(self):
        periodo = self._create_periodo()
        with self.assertRaises(UserError):
            periodo.action_poll_ticket()

    def test_download_summary_is_synchronous_no_ticket(self):
        """El servicio 5.20 "descargar resumen" es sincrono (buffer binario
        directo) -- no debe crear ningun ``sire.ticket``."""
        periodo = self._create_periodo()
        with patch(
            MOCK_PATH,
            return_value=sire_mock_response(200, content=b"zip-bytes"),
        ) as mocked:
            action = periodo.action_download_summary()
        mocked.assert_called_once()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertFalse(periodo.ticket_ids)
