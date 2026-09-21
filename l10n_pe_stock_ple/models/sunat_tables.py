# -*- coding: utf-8 -*-
"""Catalogos SUNAT (Anexo 3, RS 169-2015) compartidos por los modelos.

Se mantienen en un modulo propio sin clases de modelo para que importarlos
desde stock.picking/product.template NO arrastre el registro del modelo de
vista SQL (l10n.pe.stock.ple) antes de tiempo: la vista SQL debe inicializarse
DESPUES de que stock.picking tenga sus columnas creadas.
"""

# Tabla 12 SUNAT - Tipo de operacion.
TABLA_12 = [
    ("01", "01 Venta nacional"),
    ("02", "02 Compra nacional"),
    ("03", "03 Consignación recibida"),
    ("04", "04 Consignación entregada"),
    ("05", "05 Devolución recibida"),
    ("06", "06 Devolución entregada"),
    ("07", "07 Bonificación"),
    ("08", "08 Premio"),
    ("09", "09 Donación"),
    ("10", "10 Salida a producción"),
    ("11", "11 Salida por transferencia entre almacenes"),
    ("12", "12 Retiro"),
    ("13", "13 Mermas"),
    ("14", "14 Desmedros"),
    ("15", "15 Destrucción"),
    ("16", "16 Saldo inicial"),
    ("17", "17 Exportación"),
    ("18", "18 Importación"),
    ("19", "19 Entrada de producción"),
    ("20", "20 Entrada por devolución de producción"),
    ("21", "21 Entrada por transferencia entre almacenes"),
    ("22", "22 Entrada por identificación errónea"),
    ("23", "23 Salida por identificación errónea"),
    ("24", "24 Entrada por devolución del cliente"),
    ("25", "25 Salida por devolución al proveedor"),
    ("26", "26 Entrada para servicio de producción"),
    ("27", "27 Salida por servicio de producción"),
    ("28", "28 Ajuste por diferencia de inventario"),
    ("29", "29 Entrada de bienes en préstamo"),
    ("30", "30 Salida de bienes en préstamo"),
    ("31", "31 Entrada de bienes en custodia"),
    ("32", "32 Salida de bienes en custodia"),
    ("33", "33 Muestras médicas"),
    ("34", "34 Publicidad"),
    ("35", "35 Gastos de representación"),
    ("36", "36 Retiro para entrega a trabajadores"),
    ("37", "37 Retiro por convenio colectivo"),
    ("38", "38 Retiro por sustitución de bien siniestrado"),
    ("91", "91 Otros 1"),
    ("92", "92 Otros 2"),
    ("93", "93 Otros 3"),
    ("94", "94 Otros 4"),
    ("95", "95 Otros 5"),
    ("96", "96 Otros 6"),
    ("97", "97 Otros 7"),
    ("98", "98 Otros 8"),
    ("99", "99 Otros"),
]

# Tabla 5 SUNAT - Tipo de existencia.
TABLA_5 = [
    ("01", "01 Mercaderías"),
    ("02", "02 Productos terminados"),
    ("03", "03 Materias primas"),
    ("04", "04 Envases"),
    ("05", "05 Materiales auxiliares"),
    ("06", "06 Suministros"),
    ("07", "07 Repuestos"),
    ("08", "08 Embalajes"),
    ("09", "09 Subproductos"),
    ("10", "10 Desechos y desperdicios"),
    ("91", "91 Otros 1"),
    ("92", "92 Otros 2"),
    ("93", "93 Otros 3"),
    ("94", "94 Otros 4"),
    ("95", "95 Otros 5"),
    ("96", "96 Otros 6"),
    ("97", "97 Otros 7"),
    ("98", "98 Otros 8"),
    ("99", "99 Otros"),
]

# Tabla 14 SUNAT - Metodo de valuacion mapeado desde property_cost_method.
VALUATION_METHOD_MAP = {
    "average": "1 Promedio ponderado",
    "fifo": "2 PEPS",
    "standard": "5 Identificación específica",
}
