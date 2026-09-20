"""Cliente REST generico para los servicios de negocio del SIRE (SUNAT).

Ver decision de diseno 4 del plan aprobado: a diferencia del patron de
``l10n_pe_currency_rate_bcrp`` (cron en background que absorbe errores en
silencio), las acciones SIRE las dispara un usuario de forma interactiva y
necesitan feedback legible -- ninguna llamada de este mixin falla en
silencio, toda falla de comunicacion o de negocio se propaga como
``SireApiError``.
"""

import logging
import time

import requests

from odoo import _, models
from odoo.exceptions import UserError

from .sunat_sire_tables import SIRE_ERROR_CODE_RANGES, SIRE_ERROR_MESSAGES

_logger = logging.getLogger(__name__)

# Base de los servicios REST de negocio (padron, propuesta, gestion de
# libro, TUS). La autenticacion OAuth2 vive en un dominio distinto -- ver
# ``SIRE_AUTH_URL`` -- confirmado contra el manual v25, seccion B del plan
# aprobado.
SIRE_API_BASE_URL = "https://api-sire.sunat.gob.pe"

# Servicio de autenticacion (comun a RVIE y RCE, manual v25 servicio 5.1).
SIRE_AUTH_URL = "https://api-seguridad.sunat.gob.pe/v1/clientessol/%s/oauth2/token/"

SIRE_REQUEST_TIMEOUT = 30
SIRE_MAX_RETRIES = 3
# Backoff simple (no exponencial) entre reintentos de red: los servicios
# SIRE no documentan un ``Retry-After`` y el volumen de llamadas de este
# modulo es bajo (acciones interactivas, no scraping masivo).
SIRE_RETRY_BACKOFF = 2


class SireApiError(UserError):
    """Error de negocio o de comunicacion con el SIRE de SUNAT.

    Se dispara ante cualquier respuesta HTTP >= 400 (una vez agotados los
    reintentos de red, si aplica) o ante una respuesta de autenticacion
    invalida. ``error_code``/``error_description`` conservan el codigo y
    mensaje crudos que entrego SUNAT (cuando los hubo) para quien necesite
    inspeccionarlos mas alla del mensaje legible ya mapeado.
    """

    def __init__(self, message, error_code=None, error_description=None):
        super().__init__(message)
        self.error_code = error_code
        self.error_description = error_description


def sire_lookup_error_message(error_code, fallback):
    """Mapea un ``codigo`` de error SUNAT a un mensaje legible en espanol.

    Ante un codigo no mapeado (catalogo local incompleto) retorna el
    mensaje crudo que entrego SUNAT como fallback -- nunca se oculta
    informacion al usuario por un catalogo local incompleto.
    """
    code_int = None
    try:
        code_int = int(error_code)
    except (TypeError, ValueError):
        code_int = None
    if code_int is not None:
        if code_int in SIRE_ERROR_MESSAGES:
            return SIRE_ERROR_MESSAGES[code_int]
        for start, end, label in SIRE_ERROR_CODE_RANGES:
            if start <= code_int <= end:
                return label
    return fallback or _("Error desconocido de SUNAT.")


class SireRestClientMixin(models.AbstractModel):
    _name = "sire.rest.client.mixin"
    _description = "SIRE REST Client Mixin"

    def _sire_request(
        self,
        method,
        url,
        company,
        json_body=None,
        headers=None,
        timeout=SIRE_REQUEST_TIMEOUT,
    ):
        """Ejecuta una llamada REST autenticada contra el SIRE.

        ``company`` es el ``res.company`` cuyas credenciales SIRE
        (``sire_client_id``/``sire_client_secret``/... , ver
        ``models/res_company.py``) se usan para obtener el token.

        Reintenta (``SIRE_MAX_RETRIES`` intentos) UNICAMENTE ante
        ``requests.ConnectionError``/``requests.Timeout``; una respuesta
        4xx/5xx de SUNAT se propaga de inmediato como ``SireApiError``, sin
        reintentar (es un error de negocio/validacion, reintentar no lo
        resuelve).
        """
        company.ensure_one()
        request_headers = {"Authorization": f"Bearer {company._sire_get_valid_token()}"}
        if headers:
            request_headers.update(headers)

        attempt = 0
        while True:
            attempt += 1
            try:
                response = requests.request(
                    method,
                    url,
                    json=json_body,
                    headers=request_headers,
                    timeout=timeout,
                )
            except (requests.ConnectionError, requests.Timeout) as error:
                if attempt >= SIRE_MAX_RETRIES:
                    _logger.error(
                        "SIRE %s %s: error de red tras %s intentos: %s",
                        method,
                        url,
                        attempt,
                        error,
                    )
                    raise SireApiError(
                        _(
                            "No se pudo conectar con SUNAT (%(url)s) tras "
                            "%(attempts)s intentos: %(error)s"
                        )
                        % {"url": url, "attempts": attempt, "error": error}
                    ) from error
                _logger.warning(
                    "SIRE %s %s: error de red (intento %s/%s), reintentando: %s",
                    method,
                    url,
                    attempt,
                    SIRE_MAX_RETRIES,
                    error,
                )
                time.sleep(SIRE_RETRY_BACKOFF)
                continue

            if response.status_code >= 400:
                raise self._sire_build_error(response)
            return response

    def _sire_build_error(self, response):
        error_code = None
        error_description = response.text
        try:
            data = response.json()
        except ValueError:
            data = {}
        if isinstance(data, dict):
            error_code = data.get("cod")
            error_description = data.get("msg") or error_description
        message = sire_lookup_error_message(error_code, error_description)
        _logger.error(
            "SIRE error %s: %s", error_code or response.status_code, error_description
        )
        return SireApiError(
            _("SUNAT devolvió un error (%(code)s): %(message)s")
            % {"code": error_code or response.status_code, "message": message},
            error_code=error_code,
            error_description=error_description,
        )
