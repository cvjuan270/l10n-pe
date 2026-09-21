# Plan de trabajo - Endurecimiento familia voucher (CUO)

**Cliente**: Tagre.pe
**Versión Odoo**: 18.0
**Módulos afectados**: l10n_pe_voucher, l10n_pe_voucher_pos, l10n_pe_voucher_reconcile
**Rama**: develop/18.0
**Fecha de inicio**: 2026-07-21

## Objetivo

Aplicar las correcciones del informe de revisión previo que bloquean la
liberación de la funcionalidad de vouchers (CUO).

## Alcance

SOLO la familia voucher. Fuera de alcance: l10n_pe_stock_ple,
l10n_pe_purchase_stock y cualquier otro módulo del repo.

## Hallazgos verificados contra el código actual (2026-07-21)

| # | Sev | Ubicación | Estado verificación |
|---|-----|-----------|---------------------|
| 1 | CRÍTICO | `l10n_pe_voucher/models/l10n_pe_voucher.py:112-130` | Confirmado: search-then-create sin constraint; único `_sql_constraints` es `unique(name, company_id)` (:55-61) |
| 1b | CRÍTICO | `l10n_pe_voucher.py:77-99` | Confirmado: misma carrera en `_l10n_pe_get_sequence` |
| 2 | CRÍTICO | `l10n_pe_voucher_pos/models/pos_order.py:31-37` | Confirmado: contexto `skip=True` heredado por los moves choca con el guard de `account_move.py:82-83`; además `closed` se usa como booleano y asigna a TODOS los payment_moves |
| 3a | IMPORTANTE | `wizard/l10n_pe_voucher_backfill.py:62-65` | Confirmado: `batch_size` sin validar |
| 3b | IMPORTANTE | `models/account_move_line.py:11` | Confirmado: `btree_not_null` excluye los NULL del dominio de backfill |
| 3c | IMPORTANTE | `l10n_pe_voucher_pos/models/pos_session.py:60-94` | Confirmado: N+1 sin cache |
| 3d | IMPORTANTE | `l10n_pe_voucher_pos/__manifest__.py:9` | Confirmado: no declara `account` |
| 3e | IMPORTANTE | `l10n_pe_voucher_reconcile/data/ir_cron.xml` | Confirmado: falta `noupdate="1"` |

## Fases

- [x] Verificación de hallazgos contra el código actual (tech lead)
- [x] Implementación (odoo-senior-developer) → `summary.md`
- [x] Tests unitarios (odoo-qa-unit) en BD o18_cms → `qa-unit-report.md` (31/31 PASS)
- [x] Code review final (odoo-code-reviewer) → `code-review.md` (0 bloqueantes, aprobado)
- [x] Regresión de módulos dependientes (IMP-06) → `qa-regression-dependents.md` (4/4 PASS)
- [x] Delivery summary + mensaje de commit propuesto → `delivery-summary.md`

## Decisiones de diseño ya cerradas por el equipo

- Unicidad por constraint SQL `unique(company_id, l10n_pe_origin_model,
  l10n_pe_origin_res_id)` + retry optimista sobre `UniqueViolation` dentro de
  `cr.savepoint()`. Se descartaron advisory lock y `SELECT FOR UPDATE`.
- El índice compuesto cubre de paso el índice faltante en
  `l10n_pe_origin_res_id`.
- En `ir.sequence` NO se pone constraint global: índice único parcial por `code`.
- `pre-migrate.py` DETECTA Y ABORTA ante CUOs duplicados preexistentes. Nunca
  fusiona automáticamente: un correlativo puede haber sido reportado ya en un
  PLE cerrado.

## Notas

- Excepción autorizada: se bumpea `version` a `18.0.1.1.0` en `l10n_pe_voucher`
  porque el script de migración no corre sin bump. Autorizado explícitamente
  para esta tarea.
- No se ejecuta ninguna operación git. Los cambios quedan en el working tree.
