# SIRE Registro de Ventas (RVIE)

Integra el Registro de Ventas e Ingresos Electrónico (RVIE) del SIRE de SUNAT sobre
`tgr_sire_mixin` (cliente REST/TUS y `sire.ticket`). Menú: **SIRE > Registro de Ventas
(RVIE)**.

## Qué provee

- **`sire.rvie.periodo`**: un registro por periodo tributario (`AAAAMM`), con su propia
  máquina de estados local (ver más abajo) que espeja el flujo real de SUNAT.
- **Consultar periodo** (`action_check_period`): consulta los periodos habilitados
  (servicio 5.2) y actualiza el espejo textual del estado SUNAT.
- **Comparar propuesta** (`action_compare_proposal`): dispara el servicio asíncrono 5.18
  "descargar propuesta" -- crea un `sire.ticket`
  (`operation_type="export_proposal_detail"`). Al actualizar ese ticket
  (**Actualizar ticket**, `action_poll_ticket`) y que SUNAT lo marque terminado, se
  descarga el archivo real (servicio 5.17; layout de columnas confirmado en vivo, no es
  JSON ni el "Anexo IV" genérico), se puebla `proposal_line_ids` y se cruza
  automáticamente contra el registro de ventas generado desde `account.move`
  (`_sire_rvie_cross`), avanzando `local_state` a `compared`.
- Cruce Odoo vs. SUNAT: clave de negocio `(tipo CP, serie, número)`. La serie se obtiene
  concatenando el prefijo del tipo de documento con el código de la secuencia
  (`l10n_latam_invoice_document` los separa con un espacio) y tomando los últimos 4
  caracteres; el número se normaliza quitando ceros a la izquierda antes de comparar.
  Solo se comparan comprobantes con `l10n_pe_edi_is_required = True` cuando ese campo
  existe (módulo externo `l10n_pe_edi`, no es dependencia de este módulo).
- Pestaña **Diferencias**: resumen por cantidad, base imponible, impuestos y total,
  desglosado en tres bloques (`Coincide` / `Falta en SUNAT` / `Falta en Odoo`), más el
  detalle línea por línea.
- **Camino A -- Aceptar propuesta** (`action_accept_proposal`): acepta la propuesta
  SUNAT tal cual, vía ticket asíncrono.
- **Camino B -- Reemplazar propuesta** (wizard + subida TUS): sube un `.zip` armado
  manualmente cuando hay diferencias que corregir.
- **Registrar preliminar** (`action_register_preliminary`): presenta oficialmente el
  periodo ante SUNAT. Solo alcanzable desde `proposal_accepted`/`replacement_uploaded`;
  bloqueado con los mensajes 2293/2294/2295 del manual si el estado no corresponde.
- **Excluir comprobante** (wizard, irreversible) y **descargar resumen**
  (`action_download_summary`, servicio 5.20 -- síncrono, sin ticket).

## Proceso del contador

Secuencia regular para declarar un periodo tributario con este módulo:

1. Crear (o abrir) el registro del periodo `AAAAMM` en **SIRE > Registro de Ventas
   (RVIE)**.
2. **Consultar periodo**: trae el estado oficial de SUNAT
   (`sunat_periodo_state_label`: "Presentado" / "No Presentado") y pasa `local_state`
   de `draft` a `checked`.
3. Verificar que todos los comprobantes de venta del periodo ya se transmitieron
   electrónicamente a SUNAT antes de comparar. Un comprobante contabilizado pero aún
   "por enviar" (`edi_state = to_send`) aparece como diferencia real ("Falta en SUNAT")
   hasta que se envíe -- es el comportamiento esperado, no un error de la comparación.
4. **Comparar propuesta**: crea el ticket de descarga de la propuesta SUNAT.
5. **Actualizar ticket** (una o más veces, hasta `state = done`): al terminar, descarga
   y parsea el archivo real, puebla `proposal_line_ids`, cruza contra Odoo y llena la
   pestaña Diferencias. `local_state` pasa a `compared`.
6. Revisar la pestaña **Diferencias**:
   - `Coincide`: sin acción.
   - `Falta en SUNAT`: comprobante en Odoo sin contraparte en la propuesta SUNAT --
     verificar envío electrónico pendiente, rechazo, o registro faltante.
   - `Falta en Odoo`: comprobante en la propuesta SUNAT sin contraparte en Odoo --
     verificar comprobantes emitidos fuera de Odoo o pendientes de contabilizar.
7. Según el resultado de la revisión:
   - Propuesta correcta: **Aceptar propuesta** (camino A) -- crea ticket asíncrono;
     actualizar hasta `state = done`. `local_state` pasa a `proposal_accepted`.
   - Propuesta con diferencias a corregir: **Reemplazar propuesta** (camino B) -- sube
     el `.zip` de reemplazo vía el wizard; actualizar el ticket hasta `state = done`.
     `local_state` pasa a `replacement_uploaded`.
8. **Registrar preliminar**: solo habilitado desde
   `proposal_accepted`/`replacement_uploaded`. Presenta el registro de ventas del
   periodo ante SUNAT. `local_state` pasa a `preliminary_registered`.

Acciones auxiliares, disponibles en cualquier punto del flujo:

- **Excluir comprobante**: retira definitivamente un comprobante del registro
  (irreversible en SUNAT; requiere el grupo de gestor contable).
- **Descargar resumen**: descarga reportes de resumen (propuesta, preliminar, registro,
  etc.) para archivo o respaldo.

## Máquina de estados (`local_state`)

```
draft -> checked -> compared -+-> proposal_accepted    -+-> preliminary_registered
                               +-> replacement_uploaded -+
```

`error` es un estado terminal alcanzable desde cualquier punto ante una falla de
comunicación o de negocio no atrapada por los guards locales.

## Limitaciones conocidas

- Los servicios usados se confirmaron contra el manual "Servicios Web Api Ventas v22"
  (Partes I y II, en el `docs/` del repo raíz). La versión vigente de SUNAT es v25
  (ventas)/v26 (compras) -- podría haber diferencias no confirmadas.
- El servicio 5.20 "descargar resumen" tiene la URL corregida contra el manual pero no
  se validó en vivo contra todos sus tipos de archivo (excel/csv).
- Camino B: el wizard NO genera el archivo oficial de reemplazo (37+ campos del Anexo 3)
  -- solo sube el que el usuario adjunta a mano.
- El cruce depende de que `account.move.name` siga el formato
  `"{prefijo} {serie}-{numero}"`; un formato de secuencia distinto puede requerir
  ajustar `_sire_rvie_parse_document_number`.
