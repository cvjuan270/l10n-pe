"""Catalogos SIRE (SUNAT) compartidos por sire.rest.client.mixin y
sire.tus.client.mixin.

Se mantienen como listas de tuplas / diccionarios simples, sin modelo propio
(mismo patron que l10n_pe_stock_ple/models/sunat_tables.py), porque son datos
estaticos consultados solo en memoria -- no hay necesidad de persistirlos ni
de exponerlos en una vista.

Fuente: Manual de servicios Web API SIRE Ventas v25 (05/06/2025), paginas
1-35 revisadas (ver plan aprobado). Los catalogos marcados como PARCIAL
deben completarse cuando se disponga del manual completo.
"""

from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

# -- Errores SUNAT (respuestas 4xx/422 de los servicios REST/TUS) ----------
#
# Codigos puntuales confirmados contra el manual v25, con el texto EXACTO
# citado en el analisis del ticket (servicio "registrar preliminar", 422).
# El resto de los rangos documentados (1001-1050 validacion generica de
# parametros, 1346/1348/1350/1351 de archivo TUS) solo se conoce la
# CATEGORIA en el plan aprobado, no el texto exacto de cada codigo
# individual -- se usa un mensaje generico de esa categoria como fallback
# (ver SIRE_ERROR_CODE_RANGES) y se deja para completar contra el manual v25
# completo.
#
# _lt (lazy translate) en vez de _(): este dict se evalua a nivel de modulo,
# antes de que exista ningun Environment/request -- _() normal fallaria o no
# marcaria el string para el extractor de .pot. _lt lo marca para traduccion
# y difiere la resolucion real al momento en que se renderiza (p.ej. dentro
# de un UserError).
SIRE_ERROR_MESSAGES = {
    # -- Estado del periodo/propuesta (servicio "registrar preliminar") --
    2293: _lt("Debe reemplazar la propuesta antes de registrar el preliminar."),
    2294: _lt("El preliminar ya se encuentra registrado."),
    2295: _lt("Ya se generó el registro del periodo desde el portal SUNAT."),
}

# Rangos de error documentados en el manual v25 sin el texto exacto de cada
# codigo individual; se usan como fallback por categoria cuando el codigo
# recibido no esta en SIRE_ERROR_MESSAGES.
SIRE_ERROR_CODE_RANGES = [
    (1001, 1050, _lt("Error de validación de parámetros de la solicitud.")),
    (
        1346,
        1346,
        _lt(
            "Error de archivo: el archivo enviado no cumple el formato o la "
            "estructura esperada por SUNAT."
        ),
    ),
    (
        1348,
        1348,
        _lt(
            "Error de archivo: el archivo enviado no cumple el formato o la "
            "estructura esperada por SUNAT."
        ),
    ),
    (
        1350,
        1350,
        _lt(
            "Error de archivo: el archivo enviado no cumple el formato o la "
            "estructura esperada por SUNAT."
        ),
    ),
    (
        1351,
        1351,
        _lt(
            "Error de archivo: el archivo enviado no cumple el formato o la "
            "estructura esperada por SUNAT."
        ),
    ),
    (
        2293,
        2300,
        _lt(
            "Error de estado: la operación solicitada no es válida para el "
            "estado actual del periodo/ticket."
        ),
    ),
]

# -- Anexo I: codProceso (subida TUS) ---------------------------------
# PARCIAL: solo los codigos confirmados contra el manual v25 (paginas
# 1-35). El Anexo I completo tiene 97 codigos; completar cuando se
# disponga del manual completo.
SIRE_COD_PROCESO = [
    ("1", "Importar comprobantes de pago - Propuesta"),
    ("3", "Reemplazo de la Propuesta"),
    ("4", "Importa comprobantes de pago - Preliminar"),
    ("6", "Cargar ajustes posteriores"),
]

# -- codTipoCorrelativo (subida TUS) -----------------------------------
SIRE_COD_TIPO_CORRELATIVO = [
    ("01", "Envíos masivos"),
]

# -- codLibro -----------------------------------------------------------
# 080000 (RCE) se agregara cuando exista tgr_sire_rce.
SIRE_COD_LIBRO = [
    ("140000", "Registro de Ventas e Ingresos (RVIE)"),
]

# -- Anexo IV: extension del archivo a descargar (confirmado contra el
# manual "Servicios Web Api Ventas v22 Parte II") -----------------------
SIRE_COD_TIPO_ARCHIVO = [
    ("0", "txt"),
    ("1", "excel"),
    ("2", "csv"),
]
