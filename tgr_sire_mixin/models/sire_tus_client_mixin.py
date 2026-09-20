"""Cliente del protocolo de subida resumable TUS.io, en Python puro.

Ver decision de diseno 3 del plan aprobado: la advertencia del manual SUNAT
sobre "debe implementarse en Java" apunta al error de CORS de un cliente
Web (navegador); Odoo es server-side y TUS es HTTP abierto, implementable en
cualquier lenguaje -- se evita asi una JVM/microservicio adicional.
"""

import base64
import logging
import time
from urllib.parse import urljoin

import requests

from odoo import _, models

from .sire_rest_client_mixin import SIRE_REQUEST_TIMEOUT, SireApiError

_logger = logging.getLogger(__name__)

TUS_RESUMABLE_VERSION = "1.0.0"
TUS_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MiB
TUS_MAX_RETRIES = 3
TUS_RETRY_BACKOFF = 2


class SireTusClientMixin(models.AbstractModel):
    _name = "sire.tus.client.mixin"
    _description = "SIRE TUS (resumable upload) Client Mixin"

    # -- metadata (funcion pura, sin I/O) --------------------------------
    def _tus_encode_metadata(self, metadata_dict):
        """Arma el header ``Upload-Metadata`` del protocolo TUS.io.

        Pares ``campo valor_base64`` separados por coma, en el orden de
        insercion de ``metadata_dict`` (Python 3.7+ preserva el orden de un
        dict). Funcion pura: testeable byte a byte sin mockear HTTP.
        """
        pairs = []
        for key, value in metadata_dict.items():
            encoded = base64.b64encode(str(value).encode("utf-8")).decode("ascii")
            pairs.append(f"{key} {encoded}")
        return ",".join(pairs)

    def _tus_headers(self, company, extra=None):
        headers = {
            "Tus-Resumable": TUS_RESUMABLE_VERSION,
            "Authorization": f"Bearer {company._sire_get_valid_token()}",
        }
        if extra:
            headers.update(extra)
        return headers

    def _tus_request_with_retry(self, method, url, headers=None, data=None):
        """Igual politica de reintento que ``sire.rest.client.mixin``:
        solo ante error de red/timeout, nunca ante una respuesta 4xx/5xx."""
        attempt = 0
        while True:
            attempt += 1
            try:
                response = requests.request(
                    method,
                    url,
                    headers=headers,
                    data=data,
                    timeout=SIRE_REQUEST_TIMEOUT,
                )
            except (requests.ConnectionError, requests.Timeout) as error:
                if attempt >= TUS_MAX_RETRIES:
                    raise SireApiError(
                        _(
                            "No se pudo conectar con el servicio de subida "
                            "TUS de SUNAT (%(url)s) tras %(attempts)s "
                            "intentos: %(error)s"
                        )
                        % {"url": url, "attempts": attempt, "error": error}
                    ) from error
                _logger.warning(
                    "SIRE TUS %s %s: error de red (intento %s/%s), " "reintentando: %s",
                    method,
                    url,
                    attempt,
                    TUS_MAX_RETRIES,
                    error,
                )
                time.sleep(TUS_RETRY_BACKOFF)
                continue

            if response.status_code >= 400:
                raise SireApiError(
                    _(
                        "SUNAT devolvió un error (%(code)s) durante la "
                        "subida TUS: %(text)s"
                    )
                    % {"code": response.status_code, "text": response.text}
                )
            return response

    # -- protocolo TUS ----------------------------------------------------
    def _tus_create_upload(self, base_url, file_size, metadata_dict, company):
        company.ensure_one()
        headers = self._tus_headers(
            company,
            {
                "Upload-Length": str(file_size),
                "Upload-Metadata": self._tus_encode_metadata(metadata_dict),
                "Content-Length": "0",
            },
        )
        response = self._tus_request_with_retry("post", base_url, headers=headers)
        location = response.headers.get("Location")
        if not location:
            raise SireApiError(
                _(
                    "SUNAT no devolvió la URL de la subida (Location) al "
                    "crear el upload TUS."
                )
            )
        return urljoin(base_url, location)

    def _tus_get_offset(self, location, company):
        company.ensure_one()
        headers = self._tus_headers(company)
        response = self._tus_request_with_retry("head", location, headers=headers)
        offset = response.headers.get("Upload-Offset")
        if offset is None:
            raise SireApiError(
                _(
                    "SUNAT no devolvió el offset actual (Upload-Offset) de "
                    "la subida TUS."
                )
            )
        return int(offset)

    def _tus_upload_chunk(self, location, chunk_bytes, offset, company):
        company.ensure_one()
        headers = self._tus_headers(
            company,
            {
                "Content-Type": "application/offset+octet-stream",
                "Upload-Offset": str(offset),
            },
        )
        response = self._tus_request_with_retry(
            "patch",
            location,
            headers=headers,
            data=chunk_bytes,
        )
        expected_offset = offset + len(chunk_bytes)
        new_offset = response.headers.get("Upload-Offset")
        if new_offset is None or int(new_offset) != expected_offset:
            _logger.warning(
                "SIRE TUS: offset inesperado tras subir chunk (esperado "
                "%s, recibido %s); resincronizando con HEAD.",
                expected_offset,
                new_offset,
            )
            return self._tus_get_offset(location, company)
        return int(new_offset)

    def _tus_upload_file(
        self,
        base_url,
        file_bytes,
        metadata_dict,
        company,
        resume_location=None,
        chunk_size=None,
    ):
        """Orquesta la subida completa de ``file_bytes`` via TUS, por chunks.

        Generador: produce un dict ``{"location": ..., "offset": ...}``
        DESPUES de cada paso exitoso (creacion del upload y cada chunk
        subido), para que el LLAMADOR (``sire.ticket`` o el wizard que
        orquesta la subida) persista el progreso (``tus_location``/
        ``tus_offset``) entre iteraciones.

        Este mixin es deliberadamente agnostico de persistencia: nunca
        escribe en ``sire.ticket`` ni en ningun otro modelo, solo habla el
        protocolo TUS sobre HTTP. Si el proceso se corta a mitad de camino,
        quien orquesta puede retomar pasando ``resume_location`` (el mixin
        hace un ``HEAD`` para obtener el offset real antes de continuar, sin
        confiar en el ultimo offset localmente persistido).
        """
        company.ensure_one()
        chunk_size = chunk_size or TUS_CHUNK_SIZE
        file_size = len(file_bytes)

        if resume_location:
            location = resume_location
            offset = self._tus_get_offset(location, company)
        else:
            location = self._tus_create_upload(
                base_url,
                file_size,
                metadata_dict,
                company,
            )
            offset = 0

        yield {"location": location, "offset": offset}

        while offset < file_size:
            chunk = file_bytes[offset : offset + chunk_size]
            offset = self._tus_upload_chunk(location, chunk, offset, company)
            yield {"location": location, "offset": offset}
