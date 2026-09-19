# Resumen de implementación - Endurecimiento familia voucher (CUO)

**Cliente**: Tagre.pe
**Versión Odoo**: 18.0
**Fecha**: 2026-07-21
**Módulos**: l10n_pe_voucher, l10n_pe_voucher_pos, l10n_pe_voucher_reconcile

## 1. CRÍTICO - Carrera en `_l10n_pe_get_or_create`

**Archivo**: `l10n_pe_voucher/models/l10n_pe_voucher.py` (imports :1-21,
`origin_uniq` :75-93, `init()` :96-146, `_l10n_pe_create_or_recover` :162-199,
`_l10n_pe_get_or_create` :230-260)

Nueva constraint `origin_uniq` = `unique(company_id, l10n_pe_origin_model,
l10n_pe_origin_res_id)` + retry optimista en
`_l10n_pe_create_or_recover(records, vals, domain)`:
`with self.env.cr.savepoint():` -> `create` -> `self.env.flush_all()`. Ante
`psycopg2.IntegrityError` con `pgcode == errorcodes.UNIQUE_VIOLATION` se re-hace
el `search` y se devuelve el voucher ganador; si el search no devuelve nada se
re-lanza (la violación era de otra constraint). Sin advisory locks ni
`FOR UPDATE`, según lo decidido por el equipo.

**Decisión sobre NULLs**: se revisaron todos los puntos de creación de
`l10n.pe.voucher` del repo (`l10n_pe_voucher/models/account_move.py:105`,
`l10n_pe_voucher_pos/models/pos_session.py`,
`l10n_pe_voucher_reconcile/models/{account_move,account_move_line}.py`): todos
pasan por `_l10n_pe_get_or_create`, que siempre recibe model y res_id no nulos.
Por eso se usa UNIQUE normal en lugar de índice parcial. **Nota**: el
code-reviewer encontró después una excepción a esta premisa (creación manual
desde la UI, ver IMP-03 en `code-review.md`).

**Flush**: `savepoint()` ya es `_FlushingSavepoint`, pero el `flush_all()`
explícito garantiza que el INSERT llegue a la BD dentro del bloque; el rollback
llama a `cr.clear()`, así que el `search` posterior va realmente a disco.

**Efecto lateral positivo**: el rollback revierte el incremento `no_gap`
consumido al calcular `name`, de modo que perder la carrera no quema
correlativo. El índice compuesto de la constraint cubre además el
`l10n_pe_origin_res_id` que estaba sin indexar.

## 1b. CRÍTICO - Carrera en `_l10n_pe_get_sequence`

**Archivo**: `l10n_pe_voucher/models/l10n_pe_voucher.py:201-225`

Índice único **parcial** `ir_sequence_l10n_pe_voucher_company_uniq ON
ir_sequence (code, company_id) WHERE code = 'l10n_pe.voucher'`, creado desde
`init()` (idempotente vía `index_exists`). Nunca una constraint global sobre
`ir.sequence`. Mismo retry optimista. `init()` detecta primero secuencias
duplicadas preexistentes y aborta con mensaje legible en lugar de dejar
reventar el error crudo de PostgreSQL a mitad del update.

## 1c. Migración

**Archivos**: `l10n_pe_voucher/migrations/18.0.1.1.0/pre-migrate.py` (NUEVO),
`l10n_pe_voucher/__manifest__.py:3`

`version` bumpeada a `18.0.1.1.0` (excepción autorizada para esta tarea; sin
bump el script de migración no corre). `pre-migrate.py` agrupa por
`(company_id, l10n_pe_origin_model, l10n_pe_origin_res_id)` con `count(*) > 1`
y **aborta** listando cada grupo con ids y correlativos, indicando resolución
manual. **Nunca fusiona**: un correlativo puede haber sido reportado ya en un
PLE cerrado. Si no hay duplicados no hace nada. Además cuenta y loguea
(warning) los vouchers sin origen.

`l10n_pe_voucher_pos` y `l10n_pe_voucher_reconcile` NO se versionaron.

## 2. CRÍTICO - POS perdía el CUO en órdenes facturadas tras cierre de sesión

**Archivo**: `l10n_pe_voucher_pos/models/pos_order.py:21-62`

Dos fixes que van juntos:
a) La asignación se hace con `with_context(l10n_pe_skip_voucher_assign=False)`.
   Antes el contexto `skip=True` se heredaba en los moves devueltos por
   `super()` y chocaba con el guard de `account_move.py:82-83`, de modo que
   `_l10n_pe_assign_vouchers()` no hacía absolutamente nada.
b) Se asignan SOLO los payment moves de órdenes con sesión cerrada. Antes
   `closed` se usaba como booleano pero la asignación se aplicaba a todos.

**Decisión de correlación move -> orden**: se itera por orden llamando al
`super()` una vez por orden. Razón: el core
(`addons/point_of_sale/models/pos_order.py:1067`) devuelve los moves de
`self.payment_ids._create_payment_moves()` sin back-link a la orden, y
reconstruir la relación sería frágil. Además el core es single-record por
construcción (lee `self.partner_id` y `self.account_move`) y su único llamador
`_generate_pos_order_invoice` (:1034) ya invoca `_apply_invoice_payments` orden
por orden. Iterar no cambia comportamiento y hace el override seguro en multi.
Efecto lateral positivo: el recordset retornado se reconstruye en el entorno del
llamador, así el flag ya no se filtra a `_create_misc_reversal_move`.

## 3a. Validación de `batch_size`

**Archivo**: `l10n_pe_voucher/wizard/l10n_pe_voucher_backfill.py`
(`_check_batch_size` :32-45, `_run_batch` :76-82)

`@api.constrains` + chequeo en `_run_batch`, ambos con `ValidationError`. `0` es
falsy (procesaba todo de una vez -> riesgo de timeout) y negativo daba
`ordered[:-N]`, saltándose silenciosamente los últimos N asientos.

## 3b. Índice para el backfill

**Archivo**: `l10n_pe_voucher/models/account_move_line.py` (campo :12-27,
`init()` :29-59)

Se **mantiene** `index="btree_not_null"` y se añade índice parcial
`account_move_line_l10n_pe_voucher_pending_idx ON account_move_line (move_id)
WHERE l10n_pe_voucher_id IS NULL`.

Trade-off documentado: el uso corriente busca por voucher (nunca por NULL), así
que `btree_not_null` es correcto ahí; el backfill busca exactamente lo que ese
índice excluye, y el wizard repite esa query tras **cada** lote. Se descartó
`index=True` (btree completo) porque indexaría para siempre millones de filas
que nadie consulta por NULL. El parcial es la imagen espejo: máximo justo tras
instalar (cuando se necesita) y se encoge hasta desaparecer. Va sobre `move_id`
porque es la columna del subquery generado.

## 3c/3d/3e

- `l10n_pe_voucher_pos/models/pos_session.py:60-101`: cache dict
  `(origin_model, origin_res_id) -> voucher` en
  `_l10n_pe_route_settlement_vouchers`, mismo patrón que
  `account_move.py:88-96`. Resuelve el N+1.
- `l10n_pe_voucher_pos/__manifest__.py:9`: `account` agregado a `depends`.
- `l10n_pe_voucher_reconcile/data/ir_cron.xml`: cron envuelto en
  `<data noupdate="1">`, de modo que un `-u` ya no revierte la activación hecha
  por el cliente. Verificado por el reviewer: el xmlid no cambia.

## Verificación

`py_compile` OK sobre los 8 `.py` tocados (incluido el pre-migrate); el XML del
cron parsea. La ejecución de la suite quedó a cargo de QA
(ver `qa-unit-report.md`).

## Fuera de alcance

No se tocó `l10n_pe_stock_ple`, `l10n_pe_purchase_stock` ni ningún otro módulo.
No se ejecutó ninguna operación git.
