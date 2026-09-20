"""Fixtures compartidos para los tests de tgr_sire_mixin.

No importado por ``tests/__init__.py`` a propósito: no contiene ningún
``TestCase``, solo helpers reusados por los test modules de este addon.
"""

from unittest.mock import Mock


def sire_mock_response(
    status_code=200, json_data=None, headers=None, text="", content=b""
):
    """Construye un ``Mock`` de ``requests.Response`` listo para usar como
    ``return_value``/elemento de ``side_effect`` de los patches de
    ``requests``."""
    response = Mock()
    response.status_code = status_code
    response.ok = status_code < 400
    response.headers = headers or {}
    response.text = text
    response.content = content
    if json_data is not None:
        response.json.return_value = json_data
    else:
        response.json.side_effect = ValueError("no JSON body")
    return response


class SireMixinTestMixin:
    """Helper para dejar la compañía activa con credenciales SIRE listas
    para usar en los tests (ver models/res_company.py)."""

    def _sire_set_company_token(self, **overrides):
        vals = {
            "sire_client_id": "test-client-id",
            "sire_client_secret": "test-client-secret",
            "sire_sol_username": "MODDATOS",
            "sire_sol_password": "moddatos",
            "sire_access_token": "cached-token",
            "sire_token_expires_at": "2999-01-01 00:00:00",
            "sire_state": "valid",
        }
        vals.update(overrides)
        self.env.company.write(vals)
        return self.env.company
