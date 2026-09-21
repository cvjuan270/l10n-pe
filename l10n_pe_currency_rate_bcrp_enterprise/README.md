# Peru - Tipo de cambio BCRP (integración Enterprise)

Módulo puente entre `l10n_pe_currency_rate_bcrp` (community) y `currency_rate_live`
(enterprise). **Se instala automáticamente** cuando ambos están presentes
(`auto_install`).

## Qué hace

- Registra el proveedor **"[PE] BCRP (API oficial)"** (`bcrp_api`) en el selector de
  tasas automáticas de Ajustes > Contabilidad > Monedas.
- Las compañías con país Perú lo toman por defecto; al instalar, las que estaban en el
  proveedor SUNAT de enterprise (`bcrp`) se migran.
- El parser `_parse_bcrp_api_data` adapta la lógica del módulo base al contrato de
  `currency_rate_live`: los días previos al último publicado se upsertean directamente
  (el framework solo soporta una fecha por moneda) y el más reciente lo procesa
  `_generate_currency_rates` estándar.
- Con este módulo instalado, el cron propio del módulo base es un no-op: la
  actualización corre por el cron estándar _Currency: rate update_.
- Al desinstalar, las compañías PE vuelven al proveedor SUNAT (`bcrp`).
