from unittest.mock import patch

import requests

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.tgr_sire_mixin.models.sire_rest_client_mixin import (
    SIRE_MAX_RETRIES,
    SireApiError,
)

from .common import SireMixinTestMixin, sire_mock_response

MOCK_PATH = "odoo.addons.tgr_sire_mixin.models.sire_rest_client_mixin.requests.request"
SLEEP_PATH = "odoo.addons.tgr_sire_mixin.models.sire_rest_client_mixin.time.sleep"


@tagged("post_install", "-at_install")
class TestSireRestClient(SireMixinTestMixin, TransactionCase):
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
        cls.company = cls.env.company
        cls.ticket_model = cls.env["sire.ticket"]

    def test_request_ok(self):
        with patch(
            MOCK_PATH, return_value=sire_mock_response(200, {"ok": True})
        ) as mocked:
            response = self.ticket_model._sire_request(
                "GET",
                "https://api-sire.sunat.gob.pe/v1/test",
                self.company,
            )
        self.assertEqual(response.json(), {"ok": True})
        headers = mocked.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer cached-token")

    def test_request_retries_network_error_then_succeeds(self):
        responses = [
            requests.ConnectionError("boom"),
            sire_mock_response(200, {"ok": True}),
        ]

        def side_effect(*args, **kwargs):
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with patch(MOCK_PATH, side_effect=side_effect) as mocked, patch(SLEEP_PATH):
            response = self.ticket_model._sire_request(
                "GET",
                "https://api-sire.sunat.gob.pe/v1/test",
                self.company,
            )
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(mocked.call_count, 2)

    def test_request_network_error_exhausts_retries(self):
        with (
            patch(MOCK_PATH, side_effect=requests.ConnectionError("boom")) as mocked,
            patch(SLEEP_PATH),
            self.assertRaises(SireApiError),
        ):
            self.ticket_model._sire_request(
                "GET",
                "https://api-sire.sunat.gob.pe/v1/test",
                self.company,
            )
        self.assertEqual(mocked.call_count, SIRE_MAX_RETRIES)

    def test_request_4xx_mapped_error_code(self):
        payload = {"cod": "2293", "msg": "texto crudo de sunat"}
        with patch(MOCK_PATH, return_value=sire_mock_response(422, payload)):
            with self.assertRaises(SireApiError) as capture:
                self.ticket_model._sire_request(
                    "POST",
                    "https://api-sire.sunat.gob.pe/v1/test",
                    self.company,
                )
        self.assertEqual(capture.exception.error_code, "2293")
        self.assertIn("reemplazar la propuesta", capture.exception.args[0])

    def test_request_4xx_unmapped_falls_back_to_raw_message(self):
        payload = {"cod": "9999", "msg": "mensaje no catalogado"}
        with patch(MOCK_PATH, return_value=sire_mock_response(422, payload)):
            with self.assertRaises(SireApiError) as capture:
                self.ticket_model._sire_request(
                    "POST",
                    "https://api-sire.sunat.gob.pe/v1/test",
                    self.company,
                )
        self.assertIn("mensaje no catalogado", capture.exception.args[0])

    def test_request_4xx_does_not_retry(self):
        with (
            patch(
                MOCK_PATH,
                return_value=sire_mock_response(422, {"cod": "1001", "msg": "x"}),
            ) as mocked,
            self.assertRaises(SireApiError),
        ):
            self.ticket_model._sire_request(
                "POST",
                "https://api-sire.sunat.gob.pe/v1/test",
                self.company,
            )
        mocked.assert_called_once()
