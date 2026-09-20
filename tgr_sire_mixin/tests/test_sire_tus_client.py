import base64
from unittest.mock import patch

import requests

from odoo.tests.common import TransactionCase, tagged

from .common import SireMixinTestMixin, sire_mock_response

MOCK_PATH = "odoo.addons.tgr_sire_mixin.models.sire_tus_client_mixin.requests.request"
SLEEP_PATH = "odoo.addons.tgr_sire_mixin.models.sire_tus_client_mixin.time.sleep"


@tagged("post_install", "-at_install")
class TestSireTusClient(SireMixinTestMixin, TransactionCase):
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
        # Cualquier modelo que herede sire.tus.client.mixin sirve para
        # invocar sus metodos; sire.ticket lo hereda transitivamente via
        # sire.rest.client.mixin? No -- se usa directamente el mixin TUS a
        # traves de un modelo que lo herede. sire.ticket no lo hereda, asi
        # que se usa el propio AbstractModel registrado.
        cls.tus_model = cls.env["sire.tus.client.mixin"]
        cls.base_url = "https://api-sire.sunat.gob.pe/v1/.../upload"

    def test_encode_metadata_is_pure_and_ordered(self):
        metadata = {"filename": "abc.zip", "codLibro": "140000"}
        encoded = self.tus_model._tus_encode_metadata(metadata)
        filename_b64 = base64.b64encode(b"abc.zip").decode("ascii")
        codlibro_b64 = base64.b64encode(b"140000").decode("ascii")
        expected = f"filename {filename_b64},codLibro {codlibro_b64}"
        self.assertEqual(encoded, expected)

    def test_upload_single_chunk_ok(self):
        file_bytes = b"x" * 100
        create_response = sire_mock_response(
            201, headers={"Location": "/uploads/abc123"}
        )
        patch_response = sire_mock_response(204, headers={"Upload-Offset": "100"})
        with patch(MOCK_PATH, side_effect=[create_response, patch_response]) as mocked:
            progress = list(
                self.tus_model._tus_upload_file(
                    self.base_url,
                    file_bytes,
                    {"filename": "a.zip"},
                    self.company,
                )
            )
        self.assertEqual(progress[0]["offset"], 0)
        self.assertEqual(progress[-1]["offset"], 100)
        self.assertEqual(mocked.call_count, 2)
        self.assertTrue(progress[-1]["location"].endswith("/uploads/abc123"))

    def test_upload_multi_chunk(self):
        file_bytes = b"y" * 12
        create_response = sire_mock_response(
            201, headers={"Location": "/uploads/multi"}
        )
        patch_1 = sire_mock_response(204, headers={"Upload-Offset": "5"})
        patch_2 = sire_mock_response(204, headers={"Upload-Offset": "10"})
        patch_3 = sire_mock_response(204, headers={"Upload-Offset": "12"})
        with patch(MOCK_PATH, side_effect=[create_response, patch_1, patch_2, patch_3]):
            progress = list(
                self.tus_model._tus_upload_file(
                    self.base_url,
                    file_bytes,
                    {"filename": "a.zip"},
                    self.company,
                    chunk_size=5,
                )
            )
        self.assertEqual([p["offset"] for p in progress], [0, 5, 10, 12])

    def test_resume_from_location_uses_head_offset(self):
        file_bytes = b"z" * 10
        head_response = sire_mock_response(200, headers={"Upload-Offset": "4"})
        patch_response = sire_mock_response(204, headers={"Upload-Offset": "10"})
        with patch(MOCK_PATH, side_effect=[head_response, patch_response]) as mocked:
            progress = list(
                self.tus_model._tus_upload_file(
                    self.base_url,
                    file_bytes,
                    {"filename": "a.zip"},
                    self.company,
                    resume_location="https://api-sire.sunat.gob.pe/uploads/resume",
                )
            )
        self.assertEqual(progress[0]["offset"], 4)
        self.assertEqual(progress[-1]["offset"], 10)
        first_call_method = mocked.call_args_list[0][0][0]
        self.assertEqual(first_call_method, "head")

    def test_offset_desync_resyncs_with_head(self):
        file_bytes = b"a" * 10
        create_response = sire_mock_response(
            201, headers={"Location": "/uploads/desync"}
        )
        # El PATCH responde con un offset que no coincide con lo esperado.
        patch_wrong = sire_mock_response(204, headers={"Upload-Offset": "3"})
        head_resync = sire_mock_response(200, headers={"Upload-Offset": "10"})
        with patch(
            MOCK_PATH, side_effect=[create_response, patch_wrong, head_resync]
        ) as mocked:
            progress = list(
                self.tus_model._tus_upload_file(
                    self.base_url,
                    file_bytes,
                    {"filename": "a.zip"},
                    self.company,
                )
            )
        self.assertEqual(progress[-1]["offset"], 10)
        methods_called = [c[0][0] for c in mocked.call_args_list]
        self.assertEqual(methods_called, ["post", "patch", "head"])

    def test_network_error_retried_on_chunk(self):
        file_bytes = b"b" * 5
        create_response = sire_mock_response(
            201, headers={"Location": "/uploads/retry"}
        )
        patch_ok = sire_mock_response(204, headers={"Upload-Offset": "5"})
        with (
            patch(
                MOCK_PATH,
                side_effect=[
                    create_response,
                    requests.ConnectionError("boom"),
                    patch_ok,
                ],
            ) as mocked,
            patch(SLEEP_PATH),
        ):
            progress = list(
                self.tus_model._tus_upload_file(
                    self.base_url,
                    file_bytes,
                    {"filename": "a.zip"},
                    self.company,
                )
            )
        self.assertEqual(progress[-1]["offset"], 5)
        self.assertEqual(mocked.call_count, 3)
