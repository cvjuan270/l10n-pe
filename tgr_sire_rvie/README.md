# SIRE Registro de Ventas (RVIE)

Integra el Registro de Ventas e Ingresos Electrónico (RVIE) del SIRE de SUNAT sobre
`tgr_sire_mixin` (cliente REST/TUS y `sire.ticket`). Menú: **SIRE > Registro de Ventas
(RVIE)**.

## Qué provee

- **`sire.rvie.periodo`**: un registro por periodo tributario (`AAAAMM`), con su propia
  máquina de estados local
  (`draft/checked/compared/proposal_accepted/ replacement_uploaded/preliminary_registered/closed/error`)
  que espeja el flujo real de SUNAT.
- **Consultar periodo** (`action_check_period`): consulta los periodos habilitados
  (servicio 5.2).
- **Comparar propuesta / descargar propuesta** (`action_compare_proposal`): dispara el
  servicio asíncrono 5.18 "descargar propuesta" -- crea un `sire.ticket`
  (`operation_type="export_proposal_detail"`). El cruce contra el registro de ventas
  generado desde `account.move` (`_sire_rvie_cross`/`_sire_rvie_map_proposal_item`)
  existe y tiene tests propios, pero **todavía no se invoca automáticamente**: el layout
  de columnas del archivo descargado no está documentado en el manual (remite a una
  Resolución de Superintendencia externa) -- queda pendiente calibrarlo contra un
  archivo real.
- **Camino A -- Aceptar propuesta** (`action_accept_proposal`): acepta la propuesta
  SUNAT tal cual, vía ticket asíncrono.
- **Camino B -- Reemplazar propuesta** (wizard + subida TUS): sube un `.zip` armado
  manualmente cuando hay diferencias que corregir.
- **Registrar preliminar** (`action_register_preliminary`): presenta oficialmente el
  periodo ante SUNAT. Solo alcanzable desde `proposal_accepted`/`replacement_uploaded`;
  bloqueado con los mensajes 2293/2294/2295 del manual si el estado no corresponde.
- **Excluir comprobante** (wizard, irreversible) y **descargar resumen**
  (`action_download_summary`, servicio 5.20 -- síncrono, sin ticket).

## Limitaciones conocidas

- Los servicios usados se confirmaron contra el manual "Servicios Web Api Ventas v22"
  (Partes I y II, en `tgr_sire_mixin`'s `docs/` del repo raíz). La versión vigente de
  SUNAT es v25 (ventas)/v26 (compras) -- podría haber diferencias no confirmadas.
- `action_compare_proposal` descarga el archivo real de la propuesta (visible como
  adjunto del ticket vía `sire.ticket.action_download_result`) pero no lo parsea a
  `proposal_line_ids` todavía -- ver arriba.
- El servicio 5.20 "descargar resumen" tiene la URL corregida contra el manual pero no
  se validó en vivo contra SUNAT.
- Camino B: el wizard NO genera el archivo oficial de reemplazo (37+ campos del Anexo 3)
  -- solo sube el que el usuario adjunta a mano.
