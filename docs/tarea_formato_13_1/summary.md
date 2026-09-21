# Resumen — Formato 13.1 SUNAT (l10n_pe_stock_ple)

## Estado: ✅ Implementado, instalado y probado en o18_cms (7 tests, 0 fallos)

## Qué se entregó
Módulo nuevo **`l10n_pe_stock_ple`** (Odoo 18, Community) que implementa el
**Formato 13.1 del PLE de SUNAT — Registro de Inventario Permanente Valorizado**.

### Componentes
- **Modelo de reporte SQL** `l10n.pe.stock.ple` (`_auto=False`) sobre
  `stock.valuation.layer`, con saldo acumulado vía window functions
  **particionado por producto, compañía y establecimiento** (kardex por almacén).
- **Vista lista + pivote** con búsqueda, filtros (período, almacén, producto,
  tipo de operación) y agrupaciones — estilo enterprise.
- **Export PDF** (QWeb A4 horizontal, layout oficial: cabecera + detalle por
  producto + totales).
- **Export Excel** (controller `/l10n_pe_stock_ple/export/xlsx` con xlsxwriter
  nativo, accesible desde el menú Acción; exporta por selección o por dominio
  filtrado).
- **Campos SUNAT editables en el traslado (`stock.picking`)**:
  - Tipo de documento (Tabla 10, Many2one con domain `internal_type=False`).
  - Serie y número (Char normalizado a `FFF1-000001`).
  - Tipo de operación (Tabla 12, Selection).
- **Catálogos SUNAT**: Tablas 5 (tipo existencia en producto), 6 (código UoM),
  12 (tipo operación), 14 (método valuación, mapeo automático).
- **Data**: tipos de documento **09 (Guía de remisión - Remitente)** y
  **31 (Transportista)** — no existían en l10n_pe.
- Seguridad: ACL read para stock/account users + ir.rule multi-company.

## Decisiones clave
- Fecha de emisión = `picking.date_done` (validación del traslado).
- Constantes SUNAT en `models/sunat_tables.py` para garantizar que la vista SQL
  se inicialice DESPUÉS de las columnas de `stock.picking` (orden de imports).
- Excel sin dependencia OCA (xlsxwriter nativo).

## Issues del code-review resueltos
- CRIT-001: saldo particionado por establecimiento.
- CRIT-003: división segura del costo unitario del saldo (tolerancia).
- CRIT-004: método de valuación leído con `with_company`.
- IMP-001/003: export por dominio (base64) en vez de IDs en URL; sin
  `search([])` abierto.
- IMP-002: clave de orden homogénea en el controller.
- IMP-007: placeholders nombrados en ValidationError.
- SUG-005: orden cronológico de líneas antes del total de saldo.

## Limitaciones conocidas
- SVL sin picking (ajustes de inventario, scrap, producción) no tienen campos
  SUNAT editables todavía → 2ª iteración: exponerlos a nivel `stock.move`.
- Textos de UI en español (términos oficiales SUNAT); sin `i18n/.po` aún.
