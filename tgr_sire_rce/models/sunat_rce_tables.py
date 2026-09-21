"""Catalogos propios de tgr_sire_rce (RCE, Registro de Compras Electronico).

Mismo patron que ``tgr_sire_rvie/models/sunat_rvie_tables.py``: listas de
tuplas / diccionarios simples, sin modelo propio.

Fuente: manual "Servicios Web Api - SIRE Compras v22" (05/03/2024, ver
``docs/Manual de servicios Web Api - SIRE_Compras v22.pdf`` de este repo).

IMPORTANTE (ver plan aprobado, decision de diseno 0.a): estos catalogos NO
se fusionan con ``tgr_sire_mixin/models/sunat_sire_tables.py`` -- ese modulo
documenta sus codigos de error (2293-2295) como provenientes del manual de
**Ventas**. Los codigos de Compras (1005-1009, 1518, 2244, 2267-2278) son de
otro manual y otro servicio; mezclarlos en un dict cuyo docstring dice
"manual v25 Ventas" rompe la trazabilidad. A diferencia de RVIE, ninguno de
estos codigos esta "PROBADO EN VIVO" -- son literales del manual v22, sin
una integracion previa en produccion que ya los haya validado/corregido.
"""

from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

# -- codTipoResumen / tipoReporte (descarga de resumen, servicio 5.35) ------
# Mismos 7 valores que RVIE (manual v22 Compras, seccion 5.35), pero con
# significado propio de Compras. Igual precaucion que dejo documentada RVIE
# (error 1056 por usar un digito con signo "-1" en vez de "1"): aqui NO esta
# confirmado en vivo, se asume el mismo formato positivo por analogia.
SIRE_RCE_COD_TIPO_RESUMEN = [
    ("1", "Propuesta"),
    ("2", "Preliminar"),
    ("3", "No incluidos / excluidos"),
    ("4", "Registro"),
    ("5", "Preliminar registrado"),
    ("6", "Ajustes posteriores"),
    ("7", "No domiciliados"),
]

# -- Errores SUNAT propios de RCE (respuestas 422 del manual v22 Compras) --
# Ver decision de diseno 0.a del plan aprobado: tabla propia, no fusionada
# con la del mixin. Códigos del servicio 5.4 "registrar preliminar".
SIRE_RCE_ERROR_MESSAGES = {
    1005: _lt('El campo "perTributario" no enviado o es vacío.'),
    1006: _lt('Formato de "perTributario" no cumple con el formato "yyyymm".'),
    1007: _lt("El perTributario de búsqueda no debe ser mayor a la fecha actual."),
    1008: _lt("El registro electrónico ya se encuentra en el módulo de preliminar."),
    1009: _lt("El registro electrónico ya ha sido generado."),
}

# Rangos de error documentados en el manual v22 Compras sin el texto exacto
# de cada codigo individual; fallback por categoria cuando el codigo
# recibido no esta en SIRE_RCE_ERROR_MESSAGES.
SIRE_RCE_ERROR_CODE_RANGES = [
    (1001, 1140, _lt("Error de validación de parámetros de la solicitud.")),
    (1518, 1518, _lt("No existen documentos para exportar.")),
    (2244, 2244, _lt("El archivo solicitado no existe.")),
    (
        2267,
        2278,
        _lt(
            "Error de validación de filtros o montos en la descarga de la "
            "propuesta."
        ),
    ),
]

# -- Clasificacion de bases imponibles por grupo de impuesto -----------------
# Mismo criterio que RVIE (ver sunat_rvie_tables.py): una linea de producto
# puede tener varios impuestos, se elige uno por prioridad para no duplicar
# la base imponible. Sin bucket "exportacion" (no aplica a compras).
SIRE_RCE_TAX_GROUP_PRIORITY = [
    "IGV",
    "IGV GyNG",
    "IGV NG",
    "IVAP",
    "GRA",
    "EXO",
    "INA",
]

# Grupos de impuesto -> bucket de base imponible del registro de compras.
SIRE_RCE_TAX_GROUP_BUCKET = {
    "IGV": "gravada",
    "IGV GyNG": "gravada",
    "IGV NG": "gravada",
    "GRA": "gravada",
    "IVAP": "gravada",
    "EXO": "exonerada",
    "INA": "inafecta",
}

# Grupos de impuesto (de las lineas tipo "tax") -> bucket de impuesto.
SIRE_RCE_TAX_LINE_BUCKET = {
    "IGV": "igv",
    "IGV GyNG": "igv",
    "IGV NG": "igv",
    "ISC": "isc",
}
