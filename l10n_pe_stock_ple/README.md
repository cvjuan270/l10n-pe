# Peru - Stock PLE: Inventario Permanente Valorizado (Formato 13.1)

[![Licencia: AGPL-3](https://img.shields.io/badge/licencia-AGPL--3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0-standalone.html)

Registro de Inventario Permanente Valorizado (Formato 13.1) del PLE de SUNAT Perú,
construido a partir de las capas de valoración de inventario de Odoo, con
exportación a PDF (layout oficial) y Excel.

## Tabla de contenido

- [Descripción](#descripción)
- [Características](#características)
- [Dependencias](#dependencias)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Uso](#uso)
- [Notas y limitaciones conocidas](#notas-y-limitaciones-conocidas)
- [Créditos](#créditos)

## Descripción

El **Formato 13.1 - Registro de Inventario Permanente Valorizado (Detalle del
Inventario Valorizado)** es uno de los registros obligatorios del Programa de
Libros Electrónicos (PLE) de SUNAT. Funciona como un kardex valorizado por
establecimiento: detalla, producto por producto y en orden cronológico, las
entradas, salidas y el saldo acumulado de existencias, junto con sus costos
unitarios y totales.

Este módulo genera dicho registro de forma automática a partir de las **capas de
valoración de inventario** (`stock.valuation.layer`), que son la fuente fiable de
cantidades y costos valorizados en Odoo. Cada línea del reporte corresponde a una
capa de valoración con su saldo acumulado calculado mediante funciones de ventana
(`SUM() OVER (...)`), particionado por producto, compañía y establecimiento, de
manera que cada almacén lleva su propio saldo.

Para completar las columnas que SUNAT exige y que Odoo no provee de forma nativa
(tipo de documento, serie-número, tipo de operación, código de unidad de medida,
tipo de existencia), el módulo agrega campos SUNAT editables y catálogos oficiales
en los puntos adecuados (traslado, unidad de medida y producto).

## Características

- **Vista lista estilo enterprise**: reporte de solo lectura con todas las columnas
  del Formato 13.1, totales por columna (entradas, salidas), columnas opcionales
  mostrables/ocultables, y una vista pivote complementaria.
- **Filtrado y agrupación**: búsqueda por producto, establecimiento, tipo y número
  de documento; filtros rápidos de período (este mes / este año) y de entradas /
  salidas; agrupación por producto, establecimiento, tipo de operación, tipo de
  documento y fecha. El período por defecto es el **mes actual**.
- **Exportación a PDF** con layout oficial (QWeb, A4 horizontal): cabecera con
  denominación, período, RUC y razón social, detalle valorizado y totales.
- **Exportación a Excel** mediante `xlsxwriter` nativo (sin dependencias externas
  de servidor de reportes): cabecera, detalle y formato numérico, disponible desde
  el menú **Acción** de la lista. Respeta la selección de filas o, en su defecto,
  el dominio filtrado en pantalla; respeta también las reglas de acceso (`ir.model.access`
  e `ir.rule`).
- **Campos SUNAT editables en el traslado** (`stock.picking`):
  - **Tipo de documento (Tabla 10)**: `Many2one` a `l10n_latam.document.type`,
    limitado a documentos peruanos sin tipo interno (no aparecen en facturas de
    compra/venta).
  - **Serie y número**: un solo campo con formato `FFF1-000001` (4 alfanuméricos +
    guion + numérico). La serie se normaliza a mayúsculas y la parte numérica se
    completa a 6 dígitos con ceros a la izquierda, con validación por constraint y
    normalización en `onchange`, `create` y `write`.
  - **Tipo de operación (Tabla 12)**: campo `Selection` con el catálogo completo
    (01-38, 91-99).
- **Catálogos SUNAT integrados**:
  - **Tabla 5 - Tipo de existencia**: campo en el producto (`product.template`),
    por defecto `01 Mercaderías`.
  - **Tabla 6 - Código de unidad de medida**: campo en la unidad de medida (`uom.uom`).
  - **Tabla 12 - Tipo de operación**: en el traslado.
  - **Tabla 14 - Método de valuación**: derivado del método de costo de la
    categoría del producto (`average` → 1 Promedio ponderado, `fifo` → 2 PEPS,
    `standard` → 5 Identificación específica, resto → 9 Otros).
- **Carga de tipos de documento 09 y 31** (guías de remisión): se incorporan al
  catálogo `l10n_latam.document.type` los tipos **09 Guía de Remisión - Remitente**
  y **31 Guía de Remisión - Transportista**, que no existen en `l10n_pe`. Se cargan
  sin tipo interno para que solo se usen en traslados y no contaminen facturas.
- **Seguridad multicompañía**: acceso de lectura para usuarios de inventario /
  contabilidad y reglas de registro por compañía.

## Dependencias

- `l10n_pe` (Localización peruana)
- `stock_account` (Valoración de inventario)

## Instalación

1. Asegúrese de tener instalados los módulos `l10n_pe` y `stock_account`.
2. Copie el módulo en su ruta de addons.
3. Active el modo desarrollador, actualice la lista de aplicaciones e instale
   **Peru - Stock PLE: Inventario Permanente Valorizado (Formato 13.1)**.

> Para la exportación a Excel, el servidor debe tener instalada la librería
> Python `xlsxwriter`.

## Configuración

Antes de generar el reporte conviene completar los datos SUNAT necesarios.

### 1. Código SUNAT en las unidades de medida (Tabla 6)

En **Inventario → Configuración → Unidades de medida**, abra cada unidad y
complete el campo **Código SUNAT (T6)** (por ejemplo `NIU`, `KGM`, `LTR`, `MTR`,
`ZZ`). Aparece en la sección de detalles de la unidad de medida.

### 2. Tipo de existencia en los productos (Tabla 5)

En la ficha del producto, junto al campo de categoría, complete **Tipo de
existencia (T5)**. El valor por defecto es `01 Mercaderías`.

### 3. Método de valuación (Tabla 14)

No requiere configuración adicional: se deriva automáticamente del método de costo
configurado en la categoría del producto.

### 4. Tipos de documento (Tabla 10)

Los tipos **09 Guía de Remisión - Remitente** y **31 Guía de Remisión -
Transportista** se cargan automáticamente al instalar el módulo.

## Uso

### Completar los campos SUNAT en el traslado

1. Abra un traslado en **Inventario → Operaciones** (recepción, entrega o
   transferencia interna).
2. Vaya a la pestaña **Información adicional** y ubique el grupo
   **SUNAT - Inventario (Formato 13.1)**.
3. Complete:
   - **Tipo de documento (T10)**: por ejemplo, la guía de remisión correspondiente.
   - **Serie y número**: en formato `FFF1-000001`. El sistema normaliza la serie a
     mayúsculas y rellena el número a 6 dígitos automáticamente.
   - **Tipo de operación (T12)**: el tipo de movimiento según el catálogo SUNAT.

> La **fecha de emisión** del reporte se toma de la fecha de validación del
> traslado (`date_done`), con respaldo en la fecha del movimiento o de la capa de
> valoración.

### Consultar y exportar el reporte

1. Vaya a **Inventario → Informes → Inventario Permanente Valorizado (13.1)**.
2. El reporte se abre filtrado por el **mes actual**. Ajuste el período, almacén,
   producto u operación con los filtros y agrupaciones disponibles.
3. Para **exportar a PDF**: use el botón **Imprimir → Formato 13.1 - Inventario
   Valorizado**.
4. Para **exportar a Excel**: (opcionalmente) marque las filas a exportar y use el
   menú **Acción → Exportar a Excel (Formato 13.1)**. Si no marca filas, se exporta
   el conjunto filtrado en pantalla.

## Notas y limitaciones conocidas

- **Capas de valoración sin traslado**: los movimientos de valoración que no
  provienen de un `stock.picking` (ajustes de inventario, mermas/`scrap`, órdenes
  de producción) aparecen en el reporte, pero **aún no exponen campos SUNAT
  editables** (tipo de documento, serie-número, tipo de operación). En una segunda
  iteración se prevé exponer estos campos a nivel de `stock.move`.
- **Fecha de emisión**: se utiliza la fecha de validación del traslado
  (`date_done`). Si en algún flujo se requiere usar la fecha planificada
  (`scheduled_date`), debe revisarse con el usuario funcional.

## Créditos

- **Autor**: Tagre.pe, Juan D. Collado Vasquez
- **Licencia**: [AGPL-3](https://www.gnu.org/licenses/agpl-3.0-standalone.html)
- **Repositorio**: <https://github.com/cvjuan270/l10n-pe>
