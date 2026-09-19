# Delivery Summary - Endurecimiento familia voucher (CUO)

**Cliente**: Tagre.pe
**Versión Odoo**: 18.0
**Rama**: develop/18.0
**Fecha de cierre**: 2026-07-21

## Estado de cada fase

| Fase | Estado | Archivo | Notas |
|------|--------|---------|-------|
| Verificación de hallazgos | Completado | `work-plan.md` | Los 8 hallazgos confirmados contra el código actual antes de tocar nada |
| Implementación | Completado | `summary.md` | 2 críticos + 5 importantes + migración |
| Tests unitarios | Completado | `qa-unit-report.md` | 31/31 PASS en o18_cms |
| Code review | Completado con observaciones | `code-review.md` | 0 bloqueantes, 6 importantes, 7 sugerencias |
| Regresión dependientes | Completado | `qa-regression-dependents.md` | 4/4 PASS, sin regresión |

## Archivos modificados / creados

### Producción

- `l10n_pe_voucher/models/l10n_pe_voucher.py` (imports :1-21, `origin_uniq`
  :75-93, `init()` :96-146, `_l10n_pe_create_or_recover` :162-199,
  `_l10n_pe_get_sequence` :201-225, `_l10n_pe_get_or_create` :230-260)
- `l10n_pe_voucher/migrations/18.0.1.1.0/pre-migrate.py` (NUEVO)
- `l10n_pe_voucher/__manifest__.py:3` (version -> `18.0.1.1.0`, bump autorizado)
- `l10n_pe_voucher/models/account_move_line.py` (campo :12-27, `init()` :29-59)
- `l10n_pe_voucher/wizard/l10n_pe_voucher_backfill.py` (`_check_batch_size`
  :32-45, `_run_batch` :76-82)
- `l10n_pe_voucher_pos/models/pos_order.py` (`_apply_invoice_payments` :21-62)
- `l10n_pe_voucher_pos/models/pos_session.py`
  (`_l10n_pe_route_settlement_vouchers` :60-101)
- `l10n_pe_voucher_pos/__manifest__.py:9` (+ `account` en depends)
- `l10n_pe_voucher_reconcile/data/ir_cron.xml` (`<data noupdate="1">`)

### Tests

- `l10n_pe_voucher/tests/common.py` (NUEVO, mixin de fixtures para o18_cms)
- `l10n_pe_voucher/tests/test_voucher_hardening.py` (NUEVO, 13 tests)
- `l10n_pe_voucher_pos/tests/test_voucher_pos_invoice_timing.py` (NUEVO, 2 tests)
- `l10n_pe_voucher/tests/__init__.py`, `l10n_pe_voucher_pos/tests/__init__.py`
- `l10n_pe_voucher/tests/test_voucher.py` (assert vacuo corregido :86-89)
- `l10n_pe_voucher_pos/tests/test_voucher_pos.py`,
  `l10n_pe_voucher_reconcile/tests/test_voucher_reconcile.py` (solo fixtures)

## Resultados reales de test

**Suite principal (o18_cms)** - 31 tests, 31 PASS, 0 FAIL, 0 error:

```
odoo.service.server: 31 post-tests in 17.94s, 35402 queries
odoo.tests.stats: l10n_pe_voucher: 23 tests 6.99s 12563 queries
odoo.tests.stats: l10n_pe_voucher_pos: 7 tests 5.77s 12889 queries
odoo.tests.stats: l10n_pe_voucher_reconcile: 11 tests 5.14s 9950 queries
odoo.tests.result: 0 failed, 0 error(s) of 31 tests when loading database 'o18_cms'
```

**Regresión de dependientes (BD limpia `qa_dep_regr`)** - 4 tests, 4 PASS:

```
4 post-tests in 2.92s, 7327 queries
l10n_pe_voucher_analytic_target: 4 tests 1.54s 3581 queries
l10n_pe_voucher_sale_purchase: 4 tests 1.36s 3746 queries
0 failed, 0 error(s) of 4 tests when loading database 'qa_dep_regr'
```

**Verificación de sensibilidad (mutación temporal, luego restaurada con md5)**:
revertir el fix de `_apply_invoice_payments` produce
`FAIL: test_invoice_after_session_close_assigns_payment_voucher`; desactivar la
validación de `batch_size` produce 4 FAIL. Los tests detectan realmente los bugs.

## Riesgos identificados

1. **`init()` puede abortar un update (IMP-01)**. La detección de secuencias
   duplicadas vive en `init()`, que corre en toda instalación/actualización. Una
   BD con datos sucios queda inactualizable hasta resolver por SQL manual.
   *Mitigación*: escribir runbook de recuperación y probar la rama de aborto en
   un clon desechable antes de desplegar.
2. **Bloqueo de tabla al crear el índice (IMP-02)**. `CREATE INDEX` no
   concurrente sobre `account_move_line`; en el momento del `-u` el predicado
   matchea el 100% de las filas. *Mitigación*: medir `count(*)` en producción y,
   si supera unos pocos millones, crear el índice con `CONCURRENTLY` antes del
   `-u` (el `index_exists()` hará que `init()` lo salte).
3. **Rama de aborto del `pre-migrate.py` sin cobertura**. Nunca se ejecutó; es
   la única ruta crítica no probada y la que más duele si falla en Odoo.sh.
   *Mitigación*: probarla una vez en un clon desechable.
4. **Concurrencia simultánea exacta (IMP-04)**. El retry cubre "la ganadora ya
   commiteó", no el solape exacto (`LockNotAvailable` de `FOR UPDATE NOWAIT`).
   Odoo reintenta 5 veces solo en RPC; un `ir.cron` falla el job y reintenta en
   la siguiente pasada. *Mitigación*: documentar, no vender el fix como
   cobertura total de concurrencia.
5. **Creación manual de vouchers desde la UI (IMP-03)**. Escapa a `origin_uniq`
   (los NULL no colisionan en un UNIQUE) y quema correlativo.
   *Mitigación*: `perm_create=0` o `context="{'create': False}"`.

## Pendientes / fuera de alcance

- **IMP-03** cerrar la creación manual desde la UI.
- **IMP-05** `pos_session.py:100` borra vouchers ya numerados, abriendo huecos en
  un correlativo declarado gap-less. **Preexistente**, no introducido aquí, pero
  con impacto contable en el Libro Diario. Merece tarea propia.
- **SUG-04** el asiento de reversión (`reversed_pos_order_id`) cae al fallback y
  se lleva un CUO propio, separado del de la `pos.order`. Decisión contable.
- **Traducciones**: los tres módulos carecen de `i18n/`. Los mensajes llegan en
  inglés a un usuario peruano.
- Las suites de `l10n_pe_voucher_sale_purchase` y
  `l10n_pe_voucher_analytic_target` no heredan `L10nPeVoucherTestMixin` y por eso
  no son ejecutables en o18_cms (fallan en `setUpClass` por la regla de DNI).
  Brecha **preexistente**; requiere autorización para corregirse.
- No se tocó `l10n_pe_stock_ple` ni `l10n_pe_purchase_stock`.

## Mensaje de commit propuesto

Se sugiere separar producción y tests en dos commits:

```
[FIX] l10n_pe_voucher,l10n_pe_voucher_pos,l10n_pe_voucher_reconcile: endurecer la asignacion del CUO

- Constraint unica por (compania, modelo de origen, id de origen) con reintento
  optimista, evitando dos CUOs para la misma operacion bajo concurrencia.
- Indice unico parcial sobre la secuencia de voucher por compania.
- Script de migracion 18.0.1.1.0 que aborta ante CUOs duplicados preexistentes.
- POS: las ordenes facturadas despues del cierre de sesion vuelven a recibir CUO.
- POS: la asignacion se limita a las ordenes con sesion cerrada.
- Validacion de tamano de lote en el asistente de asignacion historica.
- Indice parcial para acelerar la busqueda de apuntes sin CUO.
- Cache de vouchers al enrutar las liquidaciones de sesion.
- Declarada la dependencia de account y protegido el cron ante actualizaciones.
```

```
[ADD] l10n_pe_voucher,l10n_pe_voucher_pos: tests del endurecimiento del CUO

- Cobertura de la constraint de unicidad y del reintento optimista.
- Cobertura de la validacion del tamano de lote.
- Cobertura de la orden facturada tras el cierre de sesion.
```

## Aviso final

Este trabajo está listo para revisión. **No se ejecutó ningún `git commit` ni
`push`**; todos los cambios quedan en el working tree. Por favor validar antes
de commitear.

**Corrección de entorno detectada**: la ruta `/opt/Odoo/odoo-18.0+e` registrada
en la documentación del proyecto **no existe**. El core real es
`/home/juand/work/odoo/18.0/odoo` (+ `enterprise/`). Conviene actualizar
`CLAUDE.md`.

**Limpieza**: la BD desechable `qa_dep_regr` quedó creada. Se elimina con
`dropdb -U odoo18 -h localhost qa_dep_regr`.
