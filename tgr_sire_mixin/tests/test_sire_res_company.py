import datetime
from unittest.mock import patch

import requests
from freezegun import freeze_time

from odoo.tests.common import TransactionCase, tagged

from ..models.sire_rest_client_mixin import SireApiError
from .common import sire_mock_response

MOCK_PATH = "odoo.addons.tgr_sire_mixin.models.res_company.requests.post"


@tagged("post_install", "-at_install")
class TestSireResCompany(TransactionCase):
    def _sire_set_credentials(self, **overrides):
        vals = {
            "sire_client_id": "test-client-id",
            "sire_client_secret": "test-client-secret",
            "sire_sol_username": "MODDATOS",
            "sire_sol_password": "moddatos",
        }
        vals.update(overrides)
        self.env.company.write(vals)
        return self.env.company

    def test_authenticate_ok_caches_token(self):
        company = self._sire_set_credentials()
        payload = {"access_token": "tok-123", "expires_in": 3600}
        with patch(MOCK_PATH, return_value=sire_mock_response(200, payload)) as mocked:
            token = company._sire_get_valid_token()
        self.assertEqual(token, "tok-123")
        self.assertEqual(company.sire_state, "valid")
        self.assertEqual(company.sire_access_token, "tok-123")
        self.assertTrue(company.sire_token_expires_at)
        mocked.assert_called_once()

        # Segunda llamada dentro de la vigencia: no vuelve a autenticar.
        with patch(MOCK_PATH) as mocked_second:
            token_2 = company._sire_get_valid_token()
        mocked_second.assert_not_called()
        self.assertEqual(token_2, "tok-123")

    @freeze_time("2026-01-01 00:00:00")
    def test_token_expiry_triggers_reauth(self):
        company = self._sire_set_credentials()
        company.write(
            {
                "sire_access_token": "old-token",
                "sire_token_expires_at": datetime.datetime(2026, 1, 1, 0, 0, 30),
                "sire_state": "valid",
            }
        )
        payload = {"access_token": "fresh-token", "expires_in": 3600}
        with patch(MOCK_PATH, return_value=sire_mock_response(200, payload)) as mocked:
            token = company._sire_get_valid_token()
        mocked.assert_called_once()
        self.assertEqual(token, "fresh-token")

    def test_authenticate_rejected_raises_with_sunat_error_code(self):
        """Ante un 4xx de SUNAT, se propaga SireApiError con el codigo y
        mensaje de SUNAT. NO se verifica que ``sire_state`` quede en
        ``invalid``: Odoo revierte toda la transaccion cuando un UserError
        escapa hasta el controlador HTTP (su propio ``assertRaises``
        envuelve el bloque en un savepoint que hace rollback al capturar
        la excepcion, simulando exactamente eso), asi que un write hecho
        justo antes de este raise no sobrevive -- el feedback real es el
        mensaje de la excepcion, no ese campo."""
        company = self._sire_set_credentials()
        error_payload = {"cod": "401", "msg": "Usuario o clave incorrecta"}
        with patch(MOCK_PATH, return_value=sire_mock_response(400, error_payload)):
            with self.assertRaises(SireApiError) as capture:
                company._sire_get_valid_token()
        self.assertEqual(capture.exception.error_code, "401")

    def test_authenticate_network_error_raises(self):
        company = self._sire_set_credentials()
        with patch(MOCK_PATH, side_effect=requests.ConnectionError("boom")):
            with self.assertRaises(SireApiError):
                company._sire_get_valid_token()

    def test_action_test_connection_ok(self):
        company = self._sire_set_credentials()
        payload = {"access_token": "tok-123", "expires_in": 3600}
        with patch(MOCK_PATH, return_value=sire_mock_response(200, payload)):
            result = company.action_sire_test_connection()
        self.assertEqual(company.sire_state, "valid")
        self.assertEqual(result["params"]["type"], "success")

    def test_action_test_connection_failure_persists_invalid(self):
        """A diferencia de _sire_authenticate() llamado directo, esta
        accion SI atrapa la excepcion (no la relanza), asi que el write a
        sire_state = invalid no queda expuesto al rollback simulado por
        assertRaises -- no hay excepcion que capturar aqui."""
        company = self._sire_set_credentials()
        error_payload = {"cod": "401", "msg": "Usuario o clave incorrecta"}
        with patch(MOCK_PATH, return_value=sire_mock_response(400, error_payload)):
            result = company.action_sire_test_connection()
        self.assertEqual(company.sire_state, "invalid")
        self.assertEqual(result["params"]["type"], "danger")
