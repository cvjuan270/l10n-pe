# Resumen — Tipo de cambio diario BCRP (API oficial)

**Fecha**: 2026-07-12 · **Actualizado**: 2026-07-21 (relleno de días sin publicación)

## Cambio 2026-07-21 — TC para todos los días (v18.0.2.1.0)

Requerimiento: debe existir TC para **cada día sin excepción**. Ahora
`_l10n_pe_bcrp_upsert_usd_rates(rates, date_from, date_to)` acepta un rango: cada día
sin tasa publicada se completa con la última anterior más cercana (regla SUNAT); si el
rango empieza sin publicaciones, la semilla es la última tasa previa en BD. Aplica a
ambos flujos (cron community y parser enterprise). Los rellenos se corrigen solos cuando
el BCRP publica el dato real (upsert de 7 días). Verificado en o18_pe: sáb/dom/lun/mar
rellenados con la venta del viernes (3.408). 13 tests verdes (10 core + 3 nuevos de
relleno incluidos). **Módulos**: `l10n_pe_currency_rate_bcrp` (core, community) +
`l10n_pe_currency_rate_bcrp_enterprise` (puente, auto_install)

## Reestructura 2026-07-20 — compatibilidad Community

Requerimiento: el módulo debe funcionar también en versiones Community, donde
`currency_rate_live` no existe. Se dividió en dos:

- **`l10n_pe_currency_rate_bcrp`** (v18.0.2.0.0): depende solo de `account`. Contiene la
  lógica BCRP (`_l10n_pe_bcrp_fetch_rates`, `_l10n_pe_bcrp_upsert_usd_rates`, parseo de
  fechas) y un **cron propio diario** (`data/ir_cron.xml`, activo por defecto) que
  actualiza todas las compañías con base PEN. Si detecta el campo `currency_provider`
  (es decir, `currency_rate_live` instalado), el cron es un **no-op** para no duplicar
  ni pisar la elección de proveedor.
- **`l10n_pe_currency_rate_bcrp_enterprise`**: `auto_install` con [core
  - currency_rate_live]. Contiene el `selection_add` del proveedor `bcrp_api`, el
    override de `_compute_currency_provider`, el parser `_parse_bcrp_api_data` (que
    reutiliza el fetch/upsert del core) y el `post_init_hook` de migración `bcrp` →
    `bcrp_api`.

Verificación de la reestructura:

- o18_cms (enterprise): 11 tests verdes (core + puente); el test del cron verificó el
  no-op con enterprise instalado.
- BD fresca community (addons path sin enterprise): instala OK, 6 tests verdes (cron en
  rama community), y **E2E real** contra la API: creó tasas 14–17 jul 2026 (venta
  3.397/3.391/3.396/3.408), idempotente. BD eliminada tras la prueba.

## Qué se implementó

Proveedor `bcrp_api` ("[PE] BCRP (API oficial)") que extiende `currency_rate_live`
(enterprise) para actualizar el tipo de cambio PEN/USD desde la API de series
estadísticas del BCRP:

- Serie `PD04640PD` (TC SBS **venta**, S/ por US$) — la tasa SUNAT contable.
- Cada corrida consulta los **últimos 7 días** y hace upsert por fecha en
  `res.currency.rate`; días `"n.d."` (feriados/fines de semana) se omiten.
- Tasa guardada como `1/venta` (base PEN=1.0), contrato estándar del framework. Los días
  previos al último publicado se upsertean con un helper propio
  (`_l10n_pe_upsert_historical_usd_rates`, solo compañías base PEN); el último día lo
  procesa `_generate_currency_rates` estándar.
- Compañías PE toman el proveedor por defecto (override de
  `_compute_currency_provider` + `post_init_hook` que migra las que estaban en el
  proveedor SUNAT `bcrp` de enterprise).
- Reutiliza el cron estándar `ir_cron_currency_update`; no hay cron propio, ni vistas,
  ni modelos nuevos. Todo el código en `models/res_company.py`.

## Decisiones (cerradas con el usuario)

| Decisión    | Elección                                                                                                |
| ----------- | ------------------------------------------------------------------------------------------------------- |
| Tasa        | Solo venta SBS (PD04640PD)                                                                              |
| Cobertura   | Últimos 7 días con upsert                                                                               |
| Monedas     | Solo USD (+ PEN base)                                                                                   |
| Multi-fecha | Upsert propio en el parser; sin override de `_generate_currency_rates` (compartido por ~27 proveedores) |

## Pruebas

- **Unitarias**: 7 tests en `tests/test_currency_rate_bcrp.py`, todos verdes en o18_cms
  (`0 failed, 0 error(s) of 7 tests`). Cubren: parsing e inversión, omisión de `n.d.`,
  fechas de periodo (meses español/inglés, `Set`), idempotencia del upsert multi-fecha,
  error de red con retorno parcial, default por país PE, y guard de base ≠ PEN.
  - Nota: `setUpClass` archiva las automatizaciones sobre `res.partner` (constraint de
    ID de contacto en o18_cms) dentro de la transacción.
  - `freeze_time` debe fijarse a mediodía UTC: medianoche UTC aún es el día anterior en
    Lima (UTC-5).
- **E2E real** (odoo shell en o18_cms, llamada real a la API): creó las tasas de los
  días hábiles 06–09 jul 2026 (venta 3.411/3.409/3.412/3.406, verificadas contra la
  API), segunda corrida idempotente (8 → 8 filas).

## Cómo ejecutar los tests

```bash
cd ~/work/odoo/18.0
.venv/bin/python odoo/odoo-bin -d o18_cms --db_user=odoo18 --db_password=odoo18 \
  --addons-path="odoo/addons,enterprise,dev/l10n-pe" \
  -u l10n_pe_currency_rate_bcrp --test-tags /l10n_pe_currency_rate_bcrp \
  --stop-after-init --log-level=warn --log-handler=odoo.tests:INFO
```

## Pendientes / notas de deploy

- El servidor destino debe tener `currency_rate_live` (enterprise) en el addons_path.
  `odoo-pe.conf` local tiene enterprise comentado.
- Configurar Intervalo = Diario en Ajustes > Contabilidad > Monedas.
