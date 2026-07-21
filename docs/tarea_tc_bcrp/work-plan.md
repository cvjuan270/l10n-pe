# Módulo `l10n_pe_currency_rate_bcrp` — Tipo de cambio diario desde API BCRP

## Contexto

El cliente (Tagre.pe, Odoo 18 enterprise) necesita actualizar diariamente el tipo de
cambio PEN/USD para Perú usando la API oficial del BCRP
(https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/api). Odoo enterprise ya
trae un proveedor `bcrp` en `currency_rate_live`, pero descarga un TXT de SUNAT, solo
trae la tasa del día actual (si el cron falla un día, esa fecha queda sin tasa) y no usa
la API del BCRP.

**API verificada en vivo**:
`https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{series}/json/{fecha_ini}/{fecha_fin}`
responde JSON con `periods: [{name: "08.Jul.26", values: ["3.412"]}]`. Días sin
publicación traen `"n.d."`.

**Decisiones cerradas con el usuario**:

- Solo tasa **venta SBS** (serie `PD04640PD`) como tasa estándar de Odoo.
- Cada corrida consulta los **últimos 7 días** y hace upsert (cubre feriados y caídas
  del cron); días `n.d.` se omiten.
- Solo **USD** (más PEN=1.0 como base).

**Estrategia**: módulo nuevo que extiende `currency_rate_live` con un proveedor
`bcrp_api`, reutilizando el cron (`ir_cron_currency_update`), el flujo
`update_currency_rates()` y el upsert `_generate_currency_rates` existentes. Para el
multi-fecha (7 días), el parser hace el upsert de los días previos él mismo y retorna al
framework solo la fecha más reciente en el contrato estándar `{moneda: (tasa, fecha)}` —
evita override de `_generate_currency_rates`, que es compartido por ~27 proveedores.

**Hechos verificados en código enterprise**
(`~/work/odoo/18.0/enterprise/currency_rate_live/models/res_config_settings.py`):

- El framework resuelve `getattr(companies, '_parse_' + provider + '_data')` (L231) →
  código `bcrp_api` requiere método `_parse_bcrp_api_data`.
- `res.config.settings.currency_provider` es `related="company_id.currency_provider"`
  (L1344) → **solo hace falta `selection_add` en `res.company`**; la vista de settings
  muestra la opción sin cambios.
- `_compute_currency_provider` (L198) mapea PE→`'bcrp'`, store=True → hay que hacer
  override + post_init_hook para compañías existentes.
- `_generate_currency_rates` (L260) hace upsert por
  `(currency_id, name=fecha, company_id)` con una sola fecha por moneda, normalizando
  por la tasa base.

## Estructura del módulo

```
l10n_pe_currency_rate_bcrp/
├── __init__.py                  # from . import models + post_init_hook
├── __manifest__.py              # depends: ["currency_rate_live"], post_init_hook
├── README.md
├── models/
│   ├── __init__.py
│   └── res_company.py           # todo el código
└── tests/
    ├── __init__.py
    └── test_currency_rate_bcrp.py
```

Manifest según convención del repo (ver `l10n_pe_stock_ple/__manifest__.py`): versión
`18.0.1.0.0`, author `Tagre.pe,Juan D. Collado Vasquez`, categoría
`Accounting/Financials/Localizations`, licencia AGPL-3.

## `models/res_company.py`

1. **Registro del proveedor**:

```python
currency_provider = fields.Selection(
    selection_add=[("bcrp_api", "[PE] BCRP (API oficial)")],
    ondelete={"bcrp_api": "set null"},
)
```

2. **Override del compute** para que PE tome el nuevo proveedor por defecto:

```python
@api.depends("country_id")
def _compute_currency_provider(self):
    super()._compute_currency_provider()
    for company in self:
        if company.country_id.code == "PE":
            company.currency_provider = "bcrp_api"
```

3. **post_init_hook** (`__init__.py`, firma Odoo 18 recibe `env`): migrar compañías PE
   con provider `'bcrp'` → `'bcrp_api'`.

4. **Parser de fecha de periodo**
   `_l10n_pe_parse_bcrp_period_date("08.Jul.26") -> date`: split por `.`, mapping propio
   de meses que cubre abreviaturas en inglés y español (incluye `set`/`sep` para
   septiembre, `ene`/`jan`, `ago`/`aug`, `dic`/`dec`); retorna None con warning si no
   parsea.

5. **Parser principal** `_parse_bcrp_api_data(self, available_currencies)` — espejo del
   estilo de `_parse_bcrp_data` (L786):

   - Guard: requiere PEN y USD en monedas activas.
   - `today = fields.Date.context_today(self.with_context(tz="America/Lima"))`; rango
     `[today-6, today]`.
   - URL:
     `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04640PD/json/{from}/{to}`.
   - `requests.get(timeout=10)` + `raise_for_status()` + `.json()` en try/except → log
     error y retorno parcial `{'PEN': (1.0, today)}` (no lanza; el cron corre con
     `suppress_errors`).
   - Por periodo: parsear fecha; `float(values[0])` — `"n.d."` lanza ValueError → se
     omite el día; tasa USD = `1.0 / venta`.
   - Días previos al más reciente → `_l10n_pe_upsert_historical_usd_rates()`; el más
     reciente se retorna como `{'PEN': (1.0, last_date), 'USD': (1/venta, last_date)}`
     para que lo procese el framework.

6. **Helper** `_l10n_pe_upsert_historical_usd_rates(rates_by_date)`: réplica de la
   semántica de upsert de `_generate_currency_rates` (search por currency/date/company →
   write o create en `res.currency.rate`). Guard: solo compañías con base PEN (warning
   si no), porque las tasas se escriben sin normalizar respecto a otra base.

## Tests (`tests/test_currency_rate_bcrp.py`)

`@tagged("post_install", "-at_install")`, `TransactionCase`. Mock:
`patch("odoo.addons.l10n_pe_currency_rate_bcrp.models.res_company.requests.get")` +
`freeze_time` (freezegun viene con Odoo 18). setUpClass: activar PEN/USD, compañía con
base PEN, país PE, provider `bcrp_api`.

Casos:

1. Parsing básico + inversión: payload real de ejemplo →
   `result["USD"] == (1/3.406, date(2026,7,9))`, PEN con la misma fecha.
2. Solo `n.d.` → result solo con PEN.
3. Fechas de periodo: `08.Jul.26`, `05.Ago.26`, `15.Set.26`, `01.Aug.26`, valor inválido
   → None.
4. Flujo completo `update_currency_rates()`: crea filas para todas las fechas
   publicadas; correr dos veces → sin duplicados (idempotente) y re-corrige valores
   modificados.
5. Error de red (`ConnectionError`) → retorno parcial, no lanza.
6. Compañía nueva país PE → provider `bcrp_api`; país distinto → no interfiere.
7. Compañía base ≠ PEN → helper histórico no escribe (solo el último día vía framework).

Ejecución: BD **o18_cms** (no o18_pe),
`--test-tags /l10n_pe_currency_rate_bcrp -i l10n_pe_currency_rate_bcrp --stop-after-init`.

## Verificación E2E (o18_cms)

1. Instalar el módulo.
2. Ajustes > Contabilidad > Monedas: aparece "[PE] BCRP (API oficial)" seleccionado;
   intervalo Diario; botón "Update now" (corrida real contra la API).
3. Monedas > USD > tasas: filas para los días hábiles de los últimos 7 días;
   `company_rate` ≈ venta SBS (~3.4xx).
4. Re-ejecutar "Update now" → sin duplicados.

## Documentación

- `docs/tarea_tc_bcrp/work-plan.md` (este plan) y `summary.md` al cerrar.
- `README.md` del módulo: serie usada, configuración, comportamiento con días `n.d.`,
  nota de que desinstalar revierte al proveedor SUNAT de enterprise.

## Secuencia

1. Esqueleto (manifest, inits, hook).
2. `res_company.py`: selection_add → compute → date parser → helper → parser principal.
3. Tests + corrida en o18_cms.
4. E2E manual con corrida real contra la API.
5. README + docs de tarea.
