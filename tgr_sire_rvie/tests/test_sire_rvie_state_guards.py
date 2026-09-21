"""Guards de estado LOCAL de ``sire.rvie.periodo`` -- deben bloquear la
accion SIN llamar a SUNAT (``assert_not_called``), replicando los mensajes
2293/2294/2295 documentados en
``tgr_sire_mixin/models/sunat_sire_tables.py::SIRE_ERROR_MESSAGES``.
"""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.tgr_sire_mixin.models.sunat_sire_tables import SIRE_ERROR_MESSAGES

from .common import SireRvieTestMixin, sire_mock_response

MOCK_PATH = "odoo.addons.tgr_sire_mixin.models.sire_rest_client_mixin.requests.request"


@tagged("post_install", "-at_install")
class TestSireRvieStateGuards(SireRvieTestMixin, TransactionCase):
    def setUp(self):
        super().setUp()
        self._sire_set_company_token()

    def _create_periodo(self, **overrides):
        vals = {"company_id": self.env.company.id, "periodo_tributario": "202601"}
        vals.update(overrides)
        return self.env["sire.rvie.periodo"].create(vals)

    # -- registrar preliminar ---------------------------------------------------
    def test_register_preliminary_blocked_from_draft(self):
        periodo = self._create_periodo(local_state="draft")
        with patch(MOCK_PATH) as mocked, self.assertRaises(UserError) as ctx:
            periodo.action_register_preliminary()
        mocked.assert_not_called()
        self.assertEqual(str(ctx.exception), str(SIRE_ERROR_MESSAGES[2293]))
        self.assertEqual(periodo.local_state, "draft")

    def test_register_preliminary_blocked_from_checked(self):
        periodo = self._create_periodo(local_state="checked")
        with patch(MOCK_PATH) as mocked, self.assertRaises(UserError):
            periodo.action_register_preliminary()
        mocked.assert_not_called()

    def test_register_preliminary_blocked_from_compared(self):
        periodo = self._create_periodo(local_state="compared")
        with patch(MOCK_PATH) as mocked, self.assertRaises(UserError):
            periodo.action_register_preliminary()
        mocked.assert_not_called()

    def test_register_preliminary_blocked_when_already_registered(self):
        periodo = self._create_periodo(local_state="preliminary_registered")
        with patch(MOCK_PATH) as mocked, self.assertRaises(UserError) as ctx:
            periodo.action_register_preliminary()
        mocked.assert_not_called()
        self.assertEqual(str(ctx.exception), str(SIRE_ERROR_MESSAGES[2294]))
        self.assertEqual(periodo.local_state, "preliminary_registered")

    def test_register_preliminary_blocked_when_closed(self):
        periodo = self._create_periodo(local_state="closed")
        with patch(MOCK_PATH) as mocked, self.assertRaises(UserError) as ctx:
            periodo.action_register_preliminary()
        mocked.assert_not_called()
        self.assertEqual(str(ctx.exception), str(SIRE_ERROR_MESSAGES[2295]))

    def test_register_preliminary_allowed_from_proposal_accepted(self):
        periodo = self._create_periodo(local_state="proposal_accepted")
        with patch(MOCK_PATH, return_value=sire_mock_response(200, {})) as mocked:
            periodo.action_register_preliminary()
        mocked.assert_called_once()
        self.assertEqual(periodo.local_state, "preliminary_registered")

    def test_register_preliminary_allowed_from_replacement_uploaded(self):
        periodo = self._create_periodo(local_state="replacement_uploaded")
        with patch(MOCK_PATH, return_value=sire_mock_response(200, {})) as mocked:
            periodo.action_register_preliminary()
        mocked.assert_called_once()
        self.assertEqual(periodo.local_state, "preliminary_registered")

    # -- aceptar propuesta --------------------------------------------------------
    def test_accept_proposal_blocked_when_already_decided(self):
        periodo = self._create_periodo(local_state="preliminary_registered")
        with patch(MOCK_PATH) as mocked, self.assertRaises(UserError):
            periodo.action_accept_proposal()
        mocked.assert_not_called()

    def test_accept_proposal_blocked_when_closed(self):
        periodo = self._create_periodo(local_state="closed")
        with patch(MOCK_PATH) as mocked, self.assertRaises(UserError):
            periodo.action_accept_proposal()
        mocked.assert_not_called()
