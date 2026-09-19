# Plan de trabajo — Formato 13.1 SUNAT (Registro de Inventario Permanente Valorizado)

## Módulo
- **Nombre técnico:** `l10n_pe_stock_ple`
- **Nombre visible:** Peru - Stock PLE: Inventario Permanente Valorizado (Formato 13.1)
- **Categoría:** Accounting/Financials/Localizations · **Licencia:** AGPL-3
- **Autor:** Tagre.pe, Juan D. Collado Vasquez
- **Depends:** `l10n_pe`, `stock_account`

## Objetivo
Formato 13.1 del PLE de SUNAT con: vista lista estilo enterprise (filtrar/agrupar),
export PDF (layout oficial) y export Excel (xlsxwriter nativo).

## Ajustes del usuario (definitivos)
Los datos del documento son **editables en el traslado (stock.picking)**, no auto-derivados:
- **a) Fecha de emisión** = fecha en que se confirma el traslado → `picking.date_done`
  (fallback `scheduled_date`).
- **b) Tipo de documento** = Many2one a `l10n_latam.document.type`, domain que excluye
  compras/ventas (`internal_type = False`, país PE). Cargar **09 Guía de remisión -
  Remitente** y **31 Guía de remisión - Transportista** (no existen en l10n_pe).
- **c,d) Serie y número** = **un solo** campo Char, formato `FFF1-000001`:
  4 alfanuméricos + `-` + numérico; autocompletar la parte numérica a 6 dígitos con
  ceros a la izquierda. Validación por constraint + normalización onchange.
- **e) Tipo de operación** = Selection con **Tabla 12** de SUNAT (01–38, 91–99).

## Catálogos SUNAT (datos exactos verificados del Anexo 3, RS 169-2015)

### Tabla 12 — Tipo de operación (Selection)
01 Venta nacional · 02 Compra nacional · 03 Consignación recibida · 04 Consignación
entregada · 05 Devolución recibida · 06 Devolución entregada · 07 Bonificación ·
08 Premio · 09 Donación · 10 Salida a producción · 11 Salida por transferencia entre
almacenes · 12 Retiro · 13 Mermas · 14 Desmedros · 15 Destrucción · 16 Saldo inicial ·
17 Exportación · 18 Importación · 19 Entrada de producción · 20 Entrada por devolución
de producción · 21 Entrada por transferencia entre almacenes · 22 Entrada por
identificación errónea · 23 Salida por identificación errónea · 24 Entrada por
devolución del cliente · 25 Salida por devolución al proveedor · 26 Entrada para
servicio de producción · 27 Salida por servicio de producción · 28 Ajuste por
diferencia de inventario · 29 Entrada de bienes en préstamo · 30 Salida de bienes en
préstamo · 31 Entrada de bienes en custodia · 32 Salida de bienes en custodia ·
33 Muestras médicas · 34 Publicidad · 35 Gastos de representación · 36 Retiro para
entrega a trabajadores · 37 Retiro por convenio colectivo · 38 Retiro por sustitución
de bien siniestrado · 91–98 Otros 1–8 · 99 Otros

### Tabla 14 — Método de valuación (mapeo desde categoría de producto)
1 Promedio ponderado (AVCO) · 2 PEPS (FIFO) · 3 Existencias básicas · 4 Detallista ·
5 Identificación específica (standard) · 9 Otros

### Tabla 5 — Tipo de existencia (campo en producto/categoría, default 01)
01 Mercaderías · 02 Productos terminados · 03 Materias primas · 04 Envases ·
05 Materiales auxiliares · 06 Suministros · 07 Repuestos · 08 Embalajes ·
09 Subproductos · 10 Desechos y desperdicios · 91–98 Otros · 99 Otros

### Tabla 6 — Código de unidad de medida (campo en uom.uom)
Catálogo SUNAT (NIU, ZZ, KGM, LTR, MTR, BX, etc.). Campo `l10n_pe_sunat_code`.

### Tabla 10 — Tipo de documento (cargar en data, faltan en l10n_pe)
09 Guía de remisión - Remitente · 31 Guía de remisión - Transportista
(internal_type vacío para que NO aparezcan en facturas de compra/venta)

## Mapeo cabecera Formato 13.1
| Campo SUNAT | Fuente |
|---|---|
| Denominación | Fijo: "REGISTRO DE INVENTARIO PERMANENTE VALORIZADO - DETALLE DEL INVENTARIO VALORIZADO" |
| Período / ejercicio | Rango de fechas del filtro |
| RUC + Razón Social | `company_id.vat`, `company_id.name` |
| Establecimiento | almacén / ubicación |
| Código de existencia | `product.default_code` |
| Tipo de existencia (T5) | campo producto/categoría |
| Descripción | `product.name` |
| Unidad de medida (T6) | `uom.l10n_pe_sunat_code` |
| Método de valuación (T14) | mapeo desde `categ_id.property_cost_method` |

## Arquitectura
1. **Extensión `stock.picking`**: campos `l10n_pe_ple_document_type_id`,
   `l10n_pe_ple_document_ref` (Char validado/normalizado), `l10n_pe_ple_operation_type`
   (Selection T12). Helper para default de operation_type según picking_type.
2. **Extensión `uom.uom`**: `l10n_pe_sunat_code` (T6) + data de mapeo de UoM estándar.
3. **Extensión `product.template`/`product.category`**: `l10n_pe_existence_type` (T5).
4. **Modelo reporte SQL** `l10n.pe.stock.ple` (`_auto=False`): join
   `stock_valuation_layer` + `stock_move` + `stock_picking` + `stock_location` +
   `product`. Columnas: fecha doc, tipo doc, serie-número, tipo operación,
   entradas (cant/cu/ct si qty>0), salidas (qty<0), saldo acumulado (window
   `SUM() OVER (PARTITION BY product, company ORDER BY date,id)`), costo unit saldo.
5. **Vistas**: list (todas las columnas), search (filtros período/almacén/producto/
   operación + group by), action list,pivot. Default período = mes actual.
6. **Reporte PDF QWeb** (`ir.actions.report` qweb-pdf, landscape, bound al modelo):
   cabecera + detalle agrupado por producto + totales.
7. **Export Excel** (controller `/l10n_pe_stock_ple/export/xlsx` + server action
   binding sobre el modelo, xlsxwriter): cabecera + detalle + totales con formato.
8. **Seguridad**: `ir.model.access.csv` (read para `stock.group_stock_user` /
   `account.group_account_user`); `ir.rule` multi-company.

## Estructura de carpetas
```
l10n_pe_stock_ple/
├── __manifest__.py · __init__.py
├── controllers/__init__.py · main.py
├── models/__init__.py · l10n_pe_stock_ple.py · stock_picking.py ·
│   uom_uom.py · product_template.py · product_category.py
├── data/l10n_latam_document_type_data.xml · uom_sunat_code_data.xml
├── report/l10n_pe_stock_ple_report.xml · l10n_pe_stock_ple_templates.xml
├── views/l10n_pe_stock_ple_views.xml · stock_picking_views.xml ·
│   uom_views.xml · product_views.xml · menuitems.xml
├── security/ir.model.access.csv · l10n_pe_stock_ple_security.xml
└── tests/__init__.py · test_stock_ple.py
```

## Fases (agentes)
1. Implementación — odoo-senior-developer (scaffolding completo).
2. Revisión — odoo-code-reviewer.
3. Fixes — main.
4. QA unit — odoo-qa-unit.
5. Validación de carga — instalar en BD o18_pe sin errores.
6. Docs — odoo-docs-writer (README + summary + qa-report).

## Pendientes/known gaps
- SVL sin picking (ajustes de inventario, scrap, producción) no tienen campos SUNAT
  editables vía picking → 2ª iteración: exponer campos a nivel `stock.move`.
- `date_done` vs fecha de confirmación: usar `date_done`, revisar con usuario si
  prefiere `scheduled_date`.
