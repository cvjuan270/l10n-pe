"""Credenciales y autenticacion SIRE, vividas en ``res.company``.

Siguen el mismo patron de ``l10n_pe_currency_rate_bcrp/models/res_company.py``:
credenciales/config a nivel de compania, expuestas en Ajustes via
``res.config.settings`` (ver ``res_config_settings.py``) -- no un modelo
propio con su propio menu/CRUD.
"""

import logging
from datetime import timedelta

import requests

from odoo import _, fields, models

from .sire_rest_client_mixin import SIRE_AUTH_URL, SIRE_REQUEST_TIMEOUT, SireApiError

_logger = logging.getLogger(__name__)

# Margen de seguridad antes de la expiracion real del token, para no usar un
# token que expire a mitad de la llamada REST siguiente.
SIRE_TOKEN_EXPIRY_MARGIN = 60  # segundos
SIRE_AUTH_SCOPE = "https://api-sire.sunat.gob.pe"


class ResCompany(models.Model):
    _inherit = "res.company"

    sire_client_id = fields.Char(string="SIRE Client ID")
    sire_client_secret = fields.Char(
        string="SIRE Client Secret",
        groups="account.group_account_manager",
    )
    sire_sol_username = fields.Char(string="Usuario SOL (SIRE)")
    sire_sol_password = fields.Char(
        string="Clave SOL (SIRE)",
        groups="account.group_account_manager",
    )
    sire_access_token = fields.Char(
        string="SIRE Access Token",
        copy=False,
        groups="account.group_account_manager",
    )
    sire_token_expires_at = fields.Datetime(string="SIRE Token expira", copy=False)
    sire_state = fields.Selection(
        selection=[
            ("not_configured", "Sin configurar"),
            ("valid", "Válida"),
            ("invalid", "Inválida"),
        ],
        string="Estado credenciales SIRE",
        default="not_configured",
        required=True,
        copy=False,
    )

    def _sire_get_valid_token(self):
        """Unico punto de lectura del token SIRE: retorna el cacheado si
        sigue vigente (con margen), o autentica de nuevo contra SUNAT."""
        self.ensure_one()
        now = fields.Datetime.now()
        if (
            self.sire_access_token
            and self.sire_token_expires_at
            and self.sire_token_expires_at
            > now + timedelta(seconds=SIRE_TOKEN_EXPIRY_MARGIN)
        ):
            return self.sire_access_token
        return self._sire_authenticate()

    def _sire_authenticate(self):
        """POST OAuth2 contra SUNAT (servicio 5.1, comun a RVIE y RCE).

        Ante cualquier falla (red o 4xx) propaga ``SireApiError`` de
        inmediato SIN intentar marcar ``sire_state = invalid`` -- Odoo
        revierte toda la transaccion en curso cuando un ``UserError``
        escapa hasta el controlador HTTP (el propio framework de tests lo
        simula: ``BaseCase.assertRaises`` envuelve el bloque en un
        ``cr.savepoint()`` que hace rollback al capturar la excepcion
        esperada), asi que cualquier write hecho justo antes de este
        ``raise`` no sobreviviria de todas formas. El feedback real al
        usuario es el mensaje de la excepcion, no este campo. ``sire_state``
        solo se actualiza en el camino de EXITO (mas abajo), donde no hay
        excepcion que dispare un rollback.
        """
        self.ensure_one()
        url = SIRE_AUTH_URL % self.sire_client_id
        body = {
            "grant_type": "password",
            "scope": SIRE_AUTH_SCOPE,
            "client_id": self.sire_client_id,
            "client_secret": self.sire_client_secret,
            "username": f"{self.vat or ''}{self.sire_sol_username or ''}",
            "password": self.sire_sol_password,
        }
        try:
            response = requests.post(url, data=body, timeout=SIRE_REQUEST_TIMEOUT)
        except (requests.ConnectionError, requests.Timeout) as error:
            _logger.error("SIRE auth %s: error de red: %s", self.vat, error)
            raise SireApiError(
                _(
                    "No se pudo conectar con el servicio de autenticación "
                    "de SUNAT: %s"
                )
                % error
            ) from error

        if not response.ok:
            error_code, error_description = self._sire_parse_auth_error(response)
            _logger.error(
                "SIRE auth %s rechazada (%s): %s",
                self.vat,
                error_code or response.status_code,
                error_description,
            )
            raise SireApiError(
                _("SUNAT rechazó la autenticación (%(code)s): %(description)s")
                % {
                    "code": error_code or response.status_code,
                    "description": error_description,
                },
                error_code=error_code,
                error_description=error_description,
            )

        data = response.json()
        access_token = data.get("access_token")
        expires_in = data.get("expires_in")
        if not access_token or not expires_in:
            raise SireApiError(
                _(
                    "La respuesta de autenticación de SUNAT no incluyó un "
                    "token válido."
                )
            )

        self.write(
            {
                "sire_access_token": access_token,
                "sire_token_expires_at": fields.Datetime.now()
                + timedelta(seconds=int(expires_in)),
                "sire_state": "valid",
            }
        )
        return access_token

    def _sire_parse_auth_error(self, response):
        try:
            data = response.json()
        except ValueError:
            return None, response.text
        if not isinstance(data, dict):
            return None, response.text
        error_code = data.get("cod") or data.get("error")
        error_description = (
            data.get("msg") or data.get("error_description") or response.text
        )
        return error_code, error_description

    def action_sire_test_connection(self):
        """Disparado por el boton "Probar conexión" de Ajustes.

        A diferencia de ``_sire_get_valid_token()``/``_sire_authenticate()``
        (pensados para usarse como paso previo de una llamada de negocio,
        donde una falla DEBE propagarse como excepcion), aqui la excepcion
        se atrapa y NO se relanza -- por eso, y solo aqui, el write a
        ``sire_state = invalid`` sobrevive: no hay excepcion escapando que
        dispare un rollback, la accion termina normalmente y su transaccion
        se commitea como cualquier otra.
        """
        self.ensure_one()
        try:
            self._sire_authenticate()
        except SireApiError as error:
            self.write({"sire_state": "invalid"})
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Conexión SIRE"),
                    "message": str(error),
                    "type": "danger",
                    "sticky": False,
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Conexión SIRE"),
                "message": _("Conexión exitosa."),
                "type": "success",
                "sticky": False,
            },
        }
