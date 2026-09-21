# SIRE Mixin (SUNAT)

Infraestructura compartida para integrar el SIRE (Sistema Integrado de Registros
Electrónicos) de SUNAT. No implementa ningún flujo funcional propio -- lo consumen
`tgr_sire_rvie` (Registro de Ventas e Ingresos) y, a futuro, `tgr_sire_rce` (Registro de
Compras).

## Qué provee

- **Credenciales SIRE en `res.company`** (`sire_client_id`/`sire_client_secret`,
  `sire_sol_username`/`sire_sol_password`, `sire_access_token` cacheado con su
  expiración), expuestas en Ajustes vía `res.config.settings` -- no un modelo propio con
  su propio menú/CRUD. Los campos sensibles solo son visibles para el grupo
  `account.group_account_manager` (Administrador de contabilidad). El botón "Probar
  conexión" (Ajustes > Contabilidad > SIRE) es la única vía que persiste
  `sire_state = invalid` de forma confiable: atrapa la excepción en vez de relanzarla
  (ver "Limitaciones conocidas").
- **`sire.rest.client.mixin`**: cliente REST genérico (`_sire_request`) para los
  servicios de negocio del SIRE. Reintenta automáticamente ante error de red/timeout
  (2-3 intentos), nunca ante un error 4xx de negocio -- esos se propagan como
  `SireApiError` con el código y mensaje de SUNAT (mapeado contra un catálogo local, con
  fallback al texto crudo).
- **`sire.tus.client.mixin`**: cliente del protocolo de subida resumable TUS.io,
  implementado en Python puro sobre `requests` (creación, subida por chunks, reanudación
  tras corte, resincronización de offset). No persiste nada por sí mismo: quien orquesta
  la subida (`sire.ticket` o un wizard) decide qué persistir en cada paso.
- **`sire.ticket`**: modelo genérico de operación asíncrona SUNAT (`numTicket`), con
  máquina de estados (`draft/sent/pending/done/error/cancelled`), `action_poll()` para
  consultar el estado y `action_download_result()` para descargar el archivo de
  resultado como adjunto.

## Limitaciones conocidas

- El catálogo de errores SUNAT (`models/sunat_sire_tables.py`) solo cubre los códigos
  confirmados contra las páginas 1-35 del manual v25; el resto usa un mensaje genérico
  por categoría/rango.
- El catálogo `codProceso` (Anexo I) está parcial (4 de 97 códigos); completar contra el
  manual v25 completo.
- Las URLs de "consultar estado de ticket" y "descargar archivo de resultado"
  (`sire.ticket._sire_ticket_status_url`/`_sire_ticket_download_url`) ya están
  confirmadas contra el manual "Servicios Web Api Ventas v22 Parte II" y validadas en
  vivo contra SUNAT. Sigue pendiente: la versión de manual con la que se confirmaron es
  v22 (la vigente es v25 ventas/v26 compras), y el layout de columnas del archivo
  descargado por "descargar propuesta" no está documentado -- `action_compare_proposal`
  solo descarga el archivo, todavía no lo parsea a `proposal_line_ids`.
- Ningún método propaga una excepción DESPUÉS de escribir un campo de estado: Odoo
  revierte toda la transacción cuando un `UserError` (o subclase, como `SireApiError`)
  escapa hasta el controlador HTTP, así que ese write nunca sobreviviría (verificado
  empíricamente durante el desarrollo). El feedback real de un fallo interactivo es el
  mensaje de la excepción, no un campo persistido -- salvo en acciones dedicadas que
  atrapan la excepción sin relanzarla (ver `res.company.action_sire_test_connection()`).
