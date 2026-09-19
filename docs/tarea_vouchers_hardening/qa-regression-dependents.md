# QA de regresion - modulos dependientes de `l10n_pe_voucher`

Tarea acotada: verificar que el endurecimiento de `l10n_pe_voucher`
(constraint SQL `origin_uniq`, retry optimista con savepoint, indices nuevos,
version 18.0.1.1.0 con pre-migrate) no rompe los modulos que dependen de el y
que no entraron en la corrida de QA anterior.

Alcance: **solo ejecucion**. No se escribieron tests nuevos ni se modifico
codigo de produccion ni de tests.

## 1. Inventario

| Modulo | Existe en repo | Estado en o18_cms | Version | Suite propia |
|---|---|---|---|---|
| `l10n_pe_voucher_sale_purchase` | si | installed | 18.0.1.0.0 | si (`tests/test_voucher_sale_purchase.py`, 2 tests) |
| `l10n_pe_voucher_analytic_target` | si | installed | 18.0.1.0.0 | si (`tests/test_voucher_analytic_target.py`, 2 tests) |
| `l10n_pe_voucher` (base endurecido) | si | installed | **18.0.1.1.0** | si (ya cubierta en la corrida previa) |

Tests existentes (4 en total):

- `TestVoucherSalePurchase.test_purchase_valuation_and_bill_share_voucher`
- `TestVoucherSalePurchase.test_sale_invoice_line_resolves_to_order`
- `TestVoucherAnalyticTarget.test_destination_inherits_origin_voucher`
- `TestVoucherAnalyticTarget.test_destination_without_origin_voucher_falls_back`

Estado del esquema en o18_cms (el hardening ya esta aplicado):

```
Indexes:
    "l10n_pe_voucher_name_company_uniq" UNIQUE CONSTRAINT, btree (name, company_id)
    "l10n_pe_voucher_origin_uniq" UNIQUE CONSTRAINT, btree (company_id, l10n_pe_origin_model, l10n_pe_origin_res_id)
    "l10n_pe_voucher__l10n_pe_origin_model_index" btree (l10n_pe_origin_model)
    "l10n_pe_voucher__company_id_index" btree (company_id)
    "l10n_pe_voucher__name_index" btree (name)
```

## 2. Corrida A - o18_cms (BD del cliente)

Comando exacto:

```bash
cd /home/juand/work/odoo/18.0/odoo && PYTHONPATH=/home/juand/work/odoo/18.0/odoo \
/home/juand/work/odoo/18.0/.venv/bin/python -m odoo \
  -c <scratchpad>/qa.conf \
  -d o18_cms \
  --http-port=8199 --gevent-port=8172 \
  -u l10n_pe_voucher_sale_purchase,l10n_pe_voucher_analytic_target \
  --test-enable \
  --test-tags '/l10n_pe_voucher_sale_purchase,/l10n_pe_voucher_analytic_target' \
  --stop-after-init \
  --log-level=test
```

(`--http-port=8199` porque el servidor de desarrollo del usuario ocupa el 8069;
no se toco ningun conf del usuario, se reuso el conf de scratchpad de la
corrida previa, con addons_path derivado de `odoo-c.conf` + `enterprise`.)

### Resultado real

Fase de carga / actualizacion: **limpia**.

```
2026-07-21 09:55:14,180 INFO o18_cms odoo.modules.loading: loading 183 modules...
2026-07-21 09:55:14,826 INFO o18_cms odoo.modules.loading: Loading module l10n_pe_voucher_analytic_target (171/183)
2026-07-21 09:55:15,544 INFO o18_cms odoo.modules.loading: Module l10n_pe_voucher_analytic_target loaded in 0.72s, 98 queries (+98 other)
2026-07-21 09:55:15,546 INFO o18_cms odoo.modules.loading: Loading module l10n_pe_voucher_sale_purchase (174/183)
2026-07-21 09:55:16,036 INFO o18_cms odoo.modules.loading: Module l10n_pe_voucher_sale_purchase loaded in 0.49s, 132 queries (+132 other)
2026-07-21 09:55:16,051 INFO o18_cms odoo.modules.loading: 183 modules loaded in 1.87s, 230 queries (+230 extra)
2026-07-21 09:55:17,235 INFO o18_cms odoo.modules.loading: Modules loaded.
2026-07-21 09:55:17,250 INFO o18_cms odoo.modules.registry: Registry loaded in 5.267s
```

Sin errores de migracion, sin violacion de la constraint nueva, sin warnings
atribuibles a los modulos bajo prueba (los WARNING presentes son de terceros:
`base_accounting_kit`, `account.account.type`, licencias faltantes en modulos
`tgr_*`).

Fase de tests: **bloqueada por el entorno**.

```
2026-07-21 09:55:17,281 ERROR o18_cms odoo.tests.suite: ERROR: setUpClass (odoo.addons.l10n_pe_voucher_analytic_target.tests.test_voucher_analytic_target.TestVoucherAnalyticTarget)
Traceback (most recent call last):
  File ".../addons/account/tests/common.py", line 79, in setUpClass
  File ".../addons/product/tests/common.py", line 16, in setUpClass
  File ".../addons/base/tests/common.py", line 31, in setUpClass
  ...
  File ".../addons/base_automation/models/base_automation.py", line 792, in create
    automation._process(automation._filter_post(records, feedback=True))
  ...
odoo.exceptions.UserError: No se puede guardar el contacto sin un ID.

2026-07-21 09:55:17,311 ERROR o18_cms odoo.tests.suite: ERROR: setUpClass (odoo.addons.l10n_pe_voucher_sale_purchase.tests.test_voucher_sale_purchase.TestVoucherSalePurchase)
   (mismo traceback, mismo UserError)

2026-07-21 09:55:17,319 INFO  o18_cms odoo.tests.stats: l10n_pe_voucher_analytic_target: 2 tests 0.04s 57 queries
2026-07-21 09:55:17,320 INFO  o18_cms odoo.tests.stats: l10n_pe_voucher_sale_purchase: 2 tests 0.03s 64 queries
2026-07-21 09:55:17,320 ERROR o18_cms odoo.tests.result: 0 failed, 2 error(s) of 0 tests when loading database 'o18_cms'
```

**Diagnostico: NO es regresion.** Es un problema **preexistente de entorno**.
Ambas clases revientan en `setUpClass`, antes de tocar una sola linea de codigo
de voucher, por la `base.automation` de o18_cms que exige documento de
identidad en cada `res.partner` creado (incluidos los que crean los helpers
estandar de Odoo para sus propios usuarios y compañias).

Es exactamente el escenario que resuelve
`l10n_pe_voucher/tests/common.py::L10nPeVoucherTestMixin`, pero **estas dos
suites no heredan ese mixin**: usan `AccountTestInvoicingCommon` directo. La
brecha es anterior al hardening y no tiene relacion con el.

Nota: no se corrigio (fuera de alcance, y la tarea prohibe modificar tests).

## 3. Corrida B - BD limpia `qa_dep_regr` (para obtener senal funcional real)

Como la corrida A no pudo ejecutar ni un test, se levanto una BD desechable
para obtener senal funcional real, sin tocar o18_cms, ni el repo, ni los conf
del usuario.

```bash
PGPASSWORD=odoo18 psql -U odoo18 -h localhost -d postgres \
  -c "DROP DATABASE IF EXISTS qa_dep_regr;" \
  -c "CREATE DATABASE qa_dep_regr TEMPLATE template0 ENCODING 'UTF8';"

cd /home/juand/work/odoo/18.0/odoo && PYTHONPATH=/home/juand/work/odoo/18.0/odoo \
/home/juand/work/odoo/18.0/.venv/bin/python -m odoo \
  -c <scratchpad>/qa.conf \
  -d qa_dep_regr \
  --http-port=8199 --gevent-port=8172 \
  -i l10n_pe_voucher_sale_purchase,l10n_pe_voucher_analytic_target \
  --test-enable \
  --test-tags '/l10n_pe_voucher_sale_purchase,/l10n_pe_voucher_analytic_target' \
  --stop-after-init \
  --log-level=test
```

Se verifico que la BD limpia efectivamente lleva el voucher endurecido:

```
l10n_pe_voucher|installed|18.0.1.1.0
l10n_pe_voucher_analytic_target|installed|18.0.1.0.0
l10n_pe_voucher_sale_purchase|installed|18.0.1.0.0
l10n_pe_voucher_origin_uniq        <- constraint nueva presente
```

### Resultado real (exit code 0)

```
2026-07-21 09:58:49,291 INFO qa_dep_regr odoo.modules.loading: 125 modules loaded in 45.05s, 77959 queries (+77966 extra)
2026-07-21 09:58:50,071 INFO qa_dep_regr odoo.modules.registry: Registry loaded in 51.899s
2026-07-21 09:58:50,071 INFO qa_dep_regr odoo.service.server: Starting post tests
2026-07-21 09:58:51,026 INFO qa_dep_regr ...test_voucher_analytic_target: Starting TestVoucherAnalyticTarget.test_destination_inherits_origin_voucher ...
2026-07-21 09:58:51,515 INFO qa_dep_regr ...test_voucher_analytic_target: Starting TestVoucherAnalyticTarget.test_destination_without_origin_voucher_falls_back ...
2026-07-21 09:58:52,565 INFO qa_dep_regr ...test_voucher_sale_purchase: Starting TestVoucherSalePurchase.test_purchase_valuation_and_bill_share_voucher ...
2026-07-21 09:58:52,823 INFO qa_dep_regr ...test_voucher_sale_purchase: Starting TestVoucherSalePurchase.test_sale_invoice_line_resolves_to_order ...
2026-07-21 09:58:52,990 INFO qa_dep_regr odoo.service.server: 4 post-tests in 2.92s, 7327 queries
2026-07-21 09:58:52,990 INFO qa_dep_regr odoo.tests.stats: l10n_pe_voucher_analytic_target: 4 tests 1.54s 3581 queries
2026-07-21 09:58:52,990 INFO qa_dep_regr odoo.tests.stats: l10n_pe_voucher_sale_purchase: 4 tests 1.36s 3746 queries
2026-07-21 09:58:52,990 INFO qa_dep_regr odoo.tests.result: 0 failed, 0 error(s) of 4 tests when loading database 'qa_dep_regr'
```

Se verifico ademas que ningun test quedo *skipped* (el guard
`_enough_accounts` / `skipTest("chart of accounts cannot configure real-time
valuation")` no se disparo): no hay ninguna linea con "skip" en el log, o sea
que la ruta de valorizacion en tiempo real se ejecuto de verdad.

## 4. Resumen

```
Modulos: l10n_pe_voucher_sale_purchase + l10n_pe_voucher_analytic_target
Tests ejecutados: 4
Tests pasados:    4
Tests fallados:   0
Tests con error:  0
Tests salteados:  0
```

| Test | Resultado | Notas |
|---|---|---|
| `TestVoucherSalePurchase.test_purchase_valuation_and_bill_share_voucher` | PASS | recepcion + factura de proveedor comparten CUO con origen `purchase.order` |
| `TestVoucherSalePurchase.test_sale_invoice_line_resolves_to_order` | PASS | factura de cliente resuelve a `sale.order` |
| `TestVoucherAnalyticTarget.test_destination_inherits_origin_voucher` | PASS | el asiento destino hereda el CUO del origen y no crea uno propio |
| `TestVoucherAnalyticTarget.test_destination_without_origin_voucher_falls_back` | PASS | fallback a CUO propio cuando el origen no tiene |

Los dos tests que dependen del `origin_uniq` de forma indirecta (varios asientos
apuntando al mismo `(company, model, res_id)`: valorizacion + factura de la
misma PO; asiento destino + asiento origen) pasan, que era justamente el riesgo
mayor del hardening: que la constraint nueva rechazara el segundo asiento en
vez de reutilizar el voucher del primero. No ocurre.

## 5. Veredicto

**NO hay regresion** en `l10n_pe_voucher_sale_purchase` ni en
`l10n_pe_voucher_analytic_target` por el endurecimiento de `l10n_pe_voucher`.

- Ambos modulos **actualizan y cargan sin error** contra `l10n_pe_voucher`
  18.0.1.1.0 en la BD real del cliente (o18_cms): sin fallo de migracion y sin
  violacion de `origin_uniq`.
- Sus 4 tests **pasan al 100%** contra el voucher endurecido (BD limpia).

### Hallazgo colateral (no bloqueante, preexistente)

Las suites de estos dos modulos **no son ejecutables en o18_cms**: no heredan
`L10nPeVoucherTestMixin` y mueren en `setUpClass` por la automatizacion de
"contacto sin ID" de esa BD. Es deuda de infraestructura de tests anterior al
hardening. Recomendacion (fuera del alcance de esta tarea, requiere
autorizacion): hacer que ambas clases hereden el mixin, igual que las suites de
`l10n_pe_voucher`. Seria un commit `[IMP]` de tests, sin bump de version.

### Limpieza

La BD `qa_dep_regr` quedo creada y es desechable; se puede borrar con
`dropdb -U odoo18 -h localhost qa_dep_regr`. No se modifico o18_cms mas alla
del `-u` de los dos modulos dependientes (solicitado por la tarea). No se
ejecuto ningun comando git.
