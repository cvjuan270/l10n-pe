"""Catalogos propios de tgr_sire_rvie (RVIE, Registro de Ventas e Ingresos).

Mismo patron que ``tgr_sire_mixin/models/sunat_sire_tables.py``: listas de
tuplas / diccionarios simples, sin modelo propio, porque son datos estaticos
consultados solo en memoria.

Fuente: Manual de servicios Web API SIRE Ventas v25 (05/06/2025), paginas
1-35 revisadas (ver plan aprobado), mas el criterio de mapeo de
``docs/tarea_registro_compras_ventas/formato_14_1_registro_ventas.sql``
(reporte SQL puntual, NO reusado como SQL -- ver ``models/account_move.py``).
"""

# -- codTipoResumen (descarga de propuesta/resumenes) -----------------------
# Confirmado contra el manual "Servicios Web Api Ventas v22 Parte II",
# seccion 5.20 "descargar resumen": el ejemplo de "Evidencias" del propio
# servicio usa un digito numerico positivo (".../202301/1/0/exporta"), y el
# servicio hermano 5.21 (mismo campo) es explicito: "El valor enviado debe
# ser numerico de un caracter (1, 2, 3 o 4)". Un valor previo con signo
# negativo ("-1".."-7", supuestamente "confirmado contra el manual v25" --
# PDF que no existe en este repo) causaba el error SUNAT 1056 "Solo se
# permite dato numerico de 1 digito para el codTipoResumen" (422).
SIRE_COD_TIPO_RESUMEN = [
    ("1", "Propuesta"),
    ("2", "Preliminar"),
    ("3", "No incluidos / excluidos"),
    ("4", "Registro"),
    ("5", "Preliminar registrado"),
    ("6", "Ajustes posteriores"),
    ("7", "No domiciliados"),
]

# -- codEstado de periodo (servicio "consultar periodos habilitados") -------
# PARCIAL/VACIO A PROPOSITO: el plan aprobado solo confirmo la FORMA de la
# respuesta (`[{numEjercicio, desEstado, lisPeriodos:[{perTributario,
# codEstado, desEstado}]}]`), no el catalogo de valores concretos de
# `codEstado`/`desEstado` -- por eso `sire.rvie.periodo.sunat_periodo_state`
# se modela como Char (espejo textual de lo que entrega SUNAT), no como
# Selection: un Selection con un catalogo incompleto rechazaria cualquier
# valor no listado aqui. Completar esta lista (solo a título de referencia
# para vistas/decoraciones) cuando se disponga del manual v25 completo.
SIRE_RVIE_PERIODO_STATE = []

# -- Clasificacion de bases imponibles por grupo de impuesto -----------------
# Porta el CRITERIO (no el SQL) de
# docs/tarea_registro_compras_ventas/formato_14_1_registro_ventas.sql:
# una linea de producto puede tener varios impuestos (p.ej. IGV + ISC); se
# elige uno solo por prioridad para no duplicar la base imponible. El nombre
# del grupo de impuesto (`account.tax.group.name`) es el que trae el plan de
# cuentas peruano estandar de `l10n_pe` -- si el cliente uso nombres propios
# para sus grupos de impuesto, esta clasificacion no los reconocera (fallback:
# "sin_clasificar", ver `_SIRE_RVIE_UNCLASSIFIED_BUCKET`).
SIRE_RVIE_TAX_GROUP_PRIORITY = [
    "IGV",
    "IGV GyNG",
    "IGV NG",
    "IVAP",
    "EXP",
    "GRA",
    "EXO",
    "INA",
]

# Grupos de impuesto -> bucket de base imponible del registro de ventas.
SIRE_RVIE_TAX_GROUP_BUCKET = {
    "IGV": "gravada",
    "IGV GyNG": "gravada",
    "IGV NG": "gravada",
    "GRA": "gravada",
    "IVAP": "gravada",
    "EXP": "exportacion",
    "EXO": "exonerada",
    "INA": "inafecta",
}

# Grupos de impuesto (de las lineas tipo "tax") -> bucket de impuesto.
SIRE_RVIE_TAX_LINE_BUCKET = {
    "IGV": "igv",
    "IGV GyNG": "igv",
    "IGV NG": "igv",
    "ISC": "isc",
}
