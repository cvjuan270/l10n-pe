# QA Report — l10n_pe_stock_ple

**Fecha:** 2026-06-15 · **BD:** o18_cms · **Odoo:** 18.0 Community

## Validaciones automáticas

| Prueba | Resultado |
|---|---|
| Compilación Python (`py_compile`) | ✅ OK |
| XML well-formed (todas las vistas/data/report) | ✅ OK |
| Instalación del módulo (`-i`) | ✅ Sin errores; vista SQL creada |
| Actualización (`-u`) con addons-path completo | ✅ Sin errores |
| Suite de tests (`--test-tags=/l10n_pe_stock_ple`) | ✅ 7 tests, 0 failed, 0 error(s) |

## Cobertura de tests
- `test_ple_balance_accumulates` — saldo acumulado de 2 entradas (10→20, costo 100, CU 5).
- `test_ple_in_and_out` — entrada + salida; qty_out y saldo descendente (6).
- `test_document_ref_normalization` — `AB12-1`→`AB12-000001`, `ab12-123`→`AB12-000123`.
- `test_document_ref_invalid` — `ABC-1`, `AB12-1234567`, `AB12_000001` lanzan ValidationError.
- `test_valuation_method_label` — average → "1 Promedio ponderado".
- `test_pdf_report_renders` — render QWeb HTML sin error de plantilla.
- `test_xlsx_export_controller` (HttpCase) — GET export devuelve 200, content-type
  xlsx y firma de archivo `PK`.

## Pendiente de QA funcional manual (UI)
- Verificar visualmente el layout del PDF con datos reales (paperformat landscape).
- Probar filtros/agrupaciones en la vista lista y el botón de export desde el menú Acción.
- Validar el llenado de campos SUNAT en un traslado real y su reflejo en el reporte.

## Conclusión
Módulo estable, instala y pasa todos los tests automatizados. Listo para QA
funcional en UI y revisión del cliente.
