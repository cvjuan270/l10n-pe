# QA de pruebas unitarias - Endurecimiento familia voucher (CUO)

**Cliente**: Tagre.pe
**Version Odoo**: 18.0
**BD de pruebas**: `o18_cms` (usuario `odoo18`)
**Modulos en alcance**: `l10n_pe_voucher`, `l10n_pe_voucher_pos`, `l10n_pe_voucher_reconcile`
**Fecha de ejecucion**: 2026-07-21

---

## 1. Entorno real utilizado

La ruta de Odoo indicada en el pedido (`/opt/Odoo/odoo-18.0+e`) **no existe** en
esta maquina. El codigo base realmente instalado es:

| Elemento | Ruta real |
|---|---|
| Odoo community | `/home/juand/work/odoo/18.0/odoo` |
| Odoo enterprise | `/home/juand/work/odoo/18.0/enterprise` |
| Addons propios | `/home/juand/work/odoo/18.0/dev/l10n-pe` |
| Virtualenv | `/home/juand/work/odoo/18.0/.venv` |

El `addons_path` se derivo de `/home/juand/work/odoo/18.0/odoo-c.conf` (la
configuracion del proyecto CMS) mas `enterprise` (necesario para
`currency_rate_live`, dependencia de un modulo instalado en la BD). Se verifico
que los 183 modulos instalados en `o18_cms` resuelven en ese `addons_path`.

Se uso un fichero de configuracion propio, en scratchpad, sin tocar ninguno del
usuario:
`/tmp/claude-1000/.../scratchpad/qa.conf`

---

## 2. Comandos exactos ejecutados

### 2.1 Actualizacion del modulo (una sola vez, para aplicar el bump 18.0.1.1.0)

```bash
cd /home/juand/work/odoo/18.0/odoo
PYTHONPATH=/home/juand/work/odoo/18.0/odoo \
/home/juand/work/odoo/18.0/.venv/bin/python -m odoo \
  -c <scratchpad>/qa.conf \
  -d o18_cms --http-port=8199 --gevent-port=8172 \
  -u l10n_pe_voucher \
  --test-enable \
  --test-tags /l10n_pe_voucher,/l10n_pe_voucher_pos,/l10n_pe_voucher_reconcile \
  --stop-after-init
```

Nota: **no se modifico el campo `version` del manifest**. El bump a
`18.0.1.1.0` ya venia aplicado por el developer (excepcion autorizada en el
work-plan para que corriera la migracion).

### 2.2 Corrida de la suite (comando estandar, ya sin `-u`)

```bash
cd /home/juand/work/odoo/18.0/odoo
PYTHONPATH=/home/juand/work/odoo/18.0/odoo \
/home/juand/work/odoo/18.0/.venv/bin/python -m odoo \
  -c <scratchpad>/qa.conf \
  -d o18_cms --http-port=8199 --gevent-port=8172 \
  --test-enable \
  --test-tags /l10n_pe_voucher,/l10n_pe_voucher_pos,/l10n_pe_voucher_reconcile \
  --stop-after-init
```

---

## 3. Resultado real de la ultima corrida

Salida literal del log (`run_final2.log`):

```
2026-07-21 09:21:34,143 90754 INFO o18_cms odoo.modules.loading: Modules loaded.
2026-07-21 09:21:52,095 90754 INFO o18_cms odoo.service.server: 31 post-tests in 17.94s, 35402 queries
2026-07-21 09:21:52,095 90754 INFO o18_cms odoo.tests.stats: l10n_pe_voucher: 23 tests 6.99s 12563 queries
2026-07-21 09:21:52,095 90754 INFO o18_cms odoo.tests.stats: l10n_pe_voucher_pos: 7 tests 5.77s 12889 queries
2026-07-21 09:21:52,095 90754 INFO o18_cms odoo.tests.stats: l10n_pe_voucher_reconcile: 11 tests 5.14s 9950 queries
2026-07-21 09:21:52,095 90754 INFO o18_cms odoo.tests.result: 0 failed, 0 error(s) of 31 tests when loading database 'o18_cms'
```

Codigo de salida del proceso: `0`.

**Resumen: 31 tests ejecutados / 31 PASS / 0 FAIL / 0 ERROR.**

(Las cifras `23 / 7 / 11` de `odoo.tests.stats` son tiempos y consultas
agregados por modulo, no el conteo de casos; el conteo real de casos unicos
ejecutados es 31, verificado sobre las lineas `Starting Test...` del log.)

### Detalle por test

| Test | Resultado | Notas |
|---|---|---|
| **l10n_pe_voucher / TestL10nPeVoucherHardening** (nuevo) | | |
| test_origin_uniq_constraint_exists | PASS | constraint + indices verificados en `pg_constraint` / `pg_indexes` |
| test_duplicate_origin_create_raises_integrity_error | PASS | (A) `IntegrityError` en el flush, cursor recuperado con savepoint |
| test_duplicate_origin_raw_insert_raises_unique_violation | PASS | (A) `psycopg2.errors.UniqueViolation` con INSERT crudo |
| test_different_company_same_origin_allowed | PASS | la unicidad es por compania |
| test_get_or_create_is_idempotent | PASS | (B) dos llamadas -> el mismo voucher |
| test_get_or_create_recovers_from_concurrent_twin | PASS | (B) carrera simulada; ademas verifica que NO se quema correlativo |
| test_create_or_recover_reraises_unrelated_unique_violation | PASS | (B) la violacion ajena si se propaga |
| test_get_sequence_recovers_from_concurrent_twin | PASS | (B) mismo retry sobre `ir.sequence`, 1 sola secuencia por compania |
| test_backfill_batch_size_zero_rejected_on_create | PASS | (C) ValidationError |
| test_backfill_batch_size_negative_rejected_on_create | PASS | (C) ValidationError |
| test_backfill_batch_size_rejected_on_write | PASS | (C) ValidationError en 0 y en -1 |
| test_backfill_run_batch_rejects_non_positive_size | PASS | (C) segunda linea de defensa en `_run_batch` |
| test_backfill_happy_path_processes_the_batch | PASS | (C) lote valido procesa y reasigna vouchers |
| **l10n_pe_voucher_pos / TestVoucherPosInvoiceTiming** (nuevo) | | |
| test_invoice_after_session_close_assigns_payment_voucher | PASS | (D) **el caso del fix**: sesion cerrada -> el asiento de pago SI recibe el CUO de la `pos.order` |
| test_invoice_with_open_session_defers_payment_voucher | PASS | (D) sesion abierta -> diferido; el cierre lo asigna |
| **l10n_pe_voucher / TestL10nPeVoucher** (preexistentes) | | |
| test_fallback_single_voucher_per_move | PASS | |
| test_sequence_is_gapless_per_company | PASS | |
| test_origin_dedup_reuses_voucher | PASS | |
| test_invoice_without_order_single_voucher | PASS | assert reforzado (ver 5.1) |
| test_payment_inherits_invoice_voucher | PASS | |
| test_payment_of_several_vouchers_keeps_own | PASS | |
| **l10n_pe_voucher_pos / TestVoucherPos** (preexistente) | | |
| test_pos_invoice_and_session_vouchers | PASS | |
| **l10n_pe_voucher_reconcile / TestVoucherReconcile** (preexistentes) | | |
| test_payment_shares_invoice_voucher_no_orphan | PASS | |
| test_reconciliation_does_not_skip_correlatives | PASS | |
| test_payment_anchors_on_reconciled_line_not_whole_invoice | PASS | |
| test_grouped_payment_of_several_vouchers_keeps_own | PASS | |
| test_statement_entry_is_deferred_no_voucher_on_post | PASS | |
| test_payment_is_deferred_no_voucher_until_reconcile | PASS | |
| test_ordering_invoice_first_shares_voucher | PASS | |
| test_ordering_statement_first_shares_voucher | PASS | |
| test_unanchored_advance_shares_one_voucher_at_backfill | PASS | |

---

## 4. Verificacion de sensibilidad de los tests (mutacion temporal)

Un test verde no sirve si tambien pasaria con el bug presente. Se comprobo
revirtiendo temporalmente el fix, corriendo, y **restaurando el fichero
original** (md5 verificado en ambos casos).

### 4.1 Fix del POS (`pos_order._apply_invoice_payments`)

Mutacion: quitar `with_context(l10n_pe_skip_voucher_assign=False)` de la
asignacion, o sea la version previa al fix.

```
FAIL: TestVoucherPosInvoiceTiming.test_invoice_after_session_close_assigns_payment_voucher
AssertionError: l10n.pe.voucher() != l10n.pe.voucher(15349,) : the invoice-payment entry shares the pos.order voucher
1 failed, 0 error(s) of 2 tests
```

Confirmado: el test detecta exactamente el bug reportado (los apuntes del
asiento de pago quedaban en `l10n_pe_voucher_id = False`).

Fichero restaurado: md5 `376dcf2abaaa7918c4e32290e58c3118` (identico al original).

### 4.2 Validacion de `batch_size` del wizard

Mutacion: desactivar el `@api.constrains` y el guard de `_run_batch`.

```
FAIL: TestL10nPeVoucherHardening.test_backfill_batch_size_negative_rejected_on_create
FAIL: TestL10nPeVoucherHardening.test_backfill_batch_size_rejected_on_write
FAIL: TestL10nPeVoucherHardening.test_backfill_batch_size_zero_rejected_on_create
FAIL: TestL10nPeVoucherHardening.test_backfill_run_batch_rejects_non_positive_size
4 failed, 0 error(s) of 13 tests
```

Fichero restaurado: md5 `e4b65d8b70aa089856c101c2962e781e` (identico al original).

Los tests A y B son sensibles por construccion: sin la constraint `origin_uniq`
no hay `IntegrityError` que capturar, y sin el retry optimista la excepcion se
propagaria en vez de devolver el voucher ganador.

---

## 5. Hallazgos

### 5.1 (Menor, en el codigo de tests) Aserciones vacuas `all(recordset.mapped(m2o))`

Detectado durante la mutacion 4.1: la asercion

```python
self.assertTrue(all(payment_lines.mapped("l10n_pe_voucher_id")))
```

**pasa incluso cuando ningun apunte tiene voucher**. `mapped` sobre un
`many2one` devuelve el recordset *union*, no una lista por registro, y
`all(recordset_vacio)` es `True`. El patron ya existia en
`l10n_pe_voucher/tests/test_voucher.py:82`. Corregido en los tres sitios por:

```python
self.assertFalse(lines.filtered(lambda line: not line.l10n_pe_voucher_id), "...")
```

No es un bug de produccion, pero dejaba un hueco de cobertura.

### 5.2 (Informativo) Limitacion de core POS que afecta a cualquier BD con POS

`point_of_sale/models/pos_order.py:1822` (`AccountCashRounding._check_session_state`)
hace `self.env['pos.session'].search(...)` **sin `sudo()`**. Consecuencia: crear
un `account.cash.rounding` con un usuario sin el grupo *Point of Sale / User*
revienta con `AccessError`. Es codigo de Odoo core, fuera del alcance de esta
tarea; solo se documenta porque obligo a ajustar el fixture.

### 5.3 Sin bugs encontrados en el codigo bajo prueba

Los seis cambios del work-plan quedaron cubiertos y verdes. No se encontro
ningun defecto en `l10n_pe_voucher`, `l10n_pe_voucher_pos` ni
`l10n_pe_voucher_reconcile`.

Cobertura por punto del work-plan:

| # | Cambio | Cubierto por |
|---|---|---|
| 1 | constraint `origin_uniq` + `_l10n_pe_create_or_recover` + indice parcial en `ir_sequence` | A y B (8 tests) |
| 2 | `pos_order._apply_invoice_payments` (timing del CUO) | D (2 tests) + mutacion 4.1 |
| 3 | `batch_size` validado en el wizard de backfill | C (5 tests) + mutacion 4.2 |
| 4 | indice parcial en `account_move_line.init()` | test_origin_uniq_constraint_exists (indice verificado en `pg_indexes`) + happy path del backfill |
| 5 | cache en `_l10n_pe_route_settlement_vouchers` | `TestVoucherPos.test_pos_invoice_and_session_vouchers` (comportamiento identico al previo) |
| 6 | `pre-migrate.py` que aborta ante duplicados | Ejecutado realmente en la migracion 18.0.1.1.0 sobre `o18_cms` (0 duplicados preexistentes -> no aborto). **La rama de aborto no se probo**: exigiria insertar duplicados en la BD antes de la migracion, lo que solo se puede hacer commiteando datos invalidos en `o18_cms`. Queda como brecha declarada. |

---

## 6. Ajustes de fixture necesarios por particularidades de `o18_cms`

La BD `o18_cms` trae personalizaciones que rompen los *fixtures* de los helpers
estandar de Odoo (no el codigo bajo prueba). Se agrupan en el mixin
`l10n_pe_voucher/tests/common.py::L10nPeVoucherTestMixin`, aplicado a las cinco
clases de test:

1. **Regla `base.automation` sobre `res.partner`** (server action id 989):
   `raise UserError("No se puede guardar el contacto sin un ID.")` si el
   contacto no tiene `vat`. Se dispara al crear *cualquier* partner, incluidos
   los que `AccountTestInvoicingCommon` / `TestPoSCommon` crean internamente
   para sus propios usuarios y companias, dentro de `super().setUpClass()`.
   Se neutraliza el motor de automatizaciones durante la clase de test
   (`patch` sobre `BaseAutomation._get_actions`, retirado por `addClassCleanup`).
   Adicionalmente, los partners creados por nuestros propios tests llevan una
   identificacion peruana coherente (`l10n_pe.it_DNI` + `vat` de 8 digitos).

2. **ACL restringidas**: `res.partner` (create limitado a *Contact Creation* y
   grupos Hospital), `pos.session`, `pos.config` y `stock.location`. Se amplian
   los grupos del usuario de test via `get_default_groups()`.

3. **Vista `tgr_hms_base.view_move_form`**: hace obligatorio `physician_id` a
   nivel de *vista* en facturas de cliente, lo que rompe
   `AccountTestInvoicingCommon.init_invoice` (que usa `Form`). El campo no es
   obligatorio a nivel de modelo. Se desactiva la vista dentro de la
   transaccion del test.

Estos ajustes no tocan ni ablandan el codigo bajo prueba: solo neutralizan
personalizaciones de la BD ajenas a la familia voucher.

---

## 7. Ficheros de test

| Fichero | Estado |
|---|---|
| `l10n_pe_voucher/tests/common.py` | NUEVO (mixin de fixtures, sin casos de test) |
| `l10n_pe_voucher/tests/test_voucher_hardening.py` | NUEVO (13 tests: A, B, C) |
| `l10n_pe_voucher/tests/__init__.py` | MODIFICADO (import del nuevo fichero) |
| `l10n_pe_voucher/tests/test_voucher.py` | MODIFICADO (mixin + assert reforzado) |
| `l10n_pe_voucher_pos/tests/test_voucher_pos_invoice_timing.py` | NUEVO (2 tests: D) |
| `l10n_pe_voucher_pos/tests/__init__.py` | MODIFICADO (import del nuevo fichero) |
| `l10n_pe_voucher_pos/tests/test_voucher_pos.py` | MODIFICADO (mixin + DNI del cliente POS) |
| `l10n_pe_voucher_reconcile/tests/test_voucher_reconcile.py` | MODIFICADO (mixin) |

Ningun fichero de produccion fue modificado por QA (verificado por md5 tras las
mutaciones temporales). No se ejecuto ninguna operacion de git.

---

## 8. Commit sugerido (a ejecutar por el desarrollador, tras revisar)

```
[ADD] l10n_pe_voucher, l10n_pe_voucher_pos: tests del endurecimiento del CUO
```

Los cambios de produccion de esta tarea van en su propio commit `[FIX]`.
