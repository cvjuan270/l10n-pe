# Peru - Tipo de cambio BCRP (API oficial)

Actualización diaria del tipo de cambio **PEN/USD** desde la API oficial de series
estadísticas del BCRP (Banco Central de Reserva del Perú).

Funciona en **Community y Enterprise**: este módulo solo depende de `account` y trae su
propio cron diario. Si `currency_rate_live` (enterprise) está instalado, el módulo
puente `l10n_pe_currency_rate_bcrp_enterprise` se instala automáticamente, registra el
proveedor en el selector estándar de Ajustes y el cron propio se vuelve un no-op (manda
el cron de enterprise).

## Qué hace

- Consulta la serie **`PD04640PD`** — \*Tipo de cambio - TC Sistema bancario SBS (S/ por
  US$) - **Venta\*** — que es la tasa que SUNAT exige para la conversión contable.
- Cada corrida pide el rango de los **últimos 7 días** y hace _upsert_ de
  `res.currency.rate` por fecha: cubre feriados y caídas del cron sin dejar huecos ni
  duplicar filas.
- **Todos los días tienen tasa, sin excepción**: los días sin publicación (`"n.d."`,
  fines de semana y feriados) se completan con la última tasa anterior más cercana
  (regla SUNAT: usar el último TC publicado). Si el rango empieza sin publicaciones, la
  semilla es la última tasa ya registrada en la BD. Cuando el BCRP publica el dato real
  de un día que fue rellenado, la siguiente corrida lo corrige (upsert de 7 días).
- La tasa se guarda como `1 / venta` (base PEN = 1.0), igual que el proveedor SUNAT
  estándar. En la ficha de la tasa, `company_rate` muestra la venta SBS directa
  (~3.4xx).

## Configuración

### Community

Instalar y listo: el cron **"BCRP: actualizar tipo de cambio"** (diario, activo por
defecto) actualiza todas las compañías con moneda base PEN.

### Enterprise (con `currency_rate_live`)

El módulo puente `l10n_pe_currency_rate_bcrp_enterprise` se auto-instala:

1. Ajustes > Contabilidad > sección **Monedas**:
   - Proveedor: _[PE] BCRP (API oficial)_ (queda por defecto en compañías PE; las que
     usaban el proveedor SUNAT de enterprise se migran al instalar).
   - Intervalo: **Diario**.
2. Botón **Actualizar ahora** para la primera corrida; después lo ejecuta el cron
   estándar _Currency: rate update_. El cron propio de este módulo detecta enterprise y
   no hace nada (sin doble actualización).

## Notas

- Solo actualiza USD (más PEN como base), únicamente en compañías con moneda base PEN.
- API:
  `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04640PD/json/{desde}/{hasta}`
  (documentación: https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/api).
- Al desinstalar el módulo puente, las compañías PE vuelven al proveedor SUNAT de
  enterprise (`bcrp`).
