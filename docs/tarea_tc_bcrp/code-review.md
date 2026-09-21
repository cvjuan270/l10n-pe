# Code Review - Tarea TC BCRP (`l10n_pe_currency_rate_bcrp`)

**Fecha**: 2026-07-12 · **Revisor**: odoo-code-reviewer · **Veredicto**: APROBADO CON
OBSERVACIONES

## Hallazgos y disposición

### Medios

- **[MED-001] APLICADO** — `ondelete={"bcrp_api": "set null"}` dejaba las compañías sin
  proveedor al desinstalar (el compute store=True no se re-dispara) y la actualización
  de tasas se detenía en silencio. Corregido con callable:
  `ondelete={"bcrp_api": lambda recs: recs.write({"currency_provider": "bcrp"})}` →
  vuelve al proveedor SUNAT de enterprise, consistente con el README.
- **[MED-002] DIFERIDO** — Idioma español en label del selection, logs y docstrings
  (convención workspace: código en inglés + i18n/es.po). El repo hoy es mixto (varios
  manifests en español, ningún módulo tiene `i18n/`). Queda como deuda/decisión de
  convención a nivel de repo.

### Sugerencias

- **[SUG-003] APLICADO** — guard `if not usd: return` en
  `_l10n_pe_upsert_historical_usd_rates`.
- **[SUG-001] SIN CAMBIO** — `except Exception` amplio: consistente con el parser SUNAT
  de enterprise; error logueado + retorno parcial.
- **[SUG-002] SIN CAMBIO** — search en loop (máx. 7 fechas), espejo del patrón de
  `_generate_currency_rates` upstream.
- **[SUG-004] SIN CAMBIO** — claves `price`/`currency` en manifest: convención de los
  demás módulos del repo.
- **[SUG-005/006]** — notas menores (siglo 21 asumido en años de 2 dígitos, líneas
  largas).

## Validaciones OK

selection*add+ondelete, firma post_init_hook Odoo 18, @api.depends del compute override,
contrato `\_parse*<provider>\_data`, timeout de red, manejo de "n.d." y división por
cero, ACL (sin modelos nuevos, hereda las estándar), idempotencia del upsert verificada
por test.

Tras aplicar MED-001 y SUG-003: **0 failed, 0 error(s) of 7 tests** en o18_cms.
