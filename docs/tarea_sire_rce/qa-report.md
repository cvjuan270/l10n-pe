# QA de validación en vivo - SIRE Registro de Compras (RCE)

**Cliente**: Tagre.pe
**Versión Odoo**: 18.0
**BD de pruebas**: `o18_cms`
**Compañía validada**: CLINICA MALL SALUD PERU S.A.C.
**Módulos en alcance**: `tgr_sire_rce` (nuevo), ajuste puntual en `tgr_sire_mixin`
**Periodo tributario validado**: `202608` (agosto 2026)
**Fecha de ejecución**: 2026-09-21

---

## 1. Alcance de la validación

Se instaló `tgr_sire_rce` en `o18_cms` y se ejecutó el flujo desde la
interfaz web, contra la API real de SUNAT, con las credenciales SIRE ya
configuradas para esta compañía (las mismas usadas para validar RVIE
previamente).

**Deliberadamente NO se ejecutaron** `Aceptar propuesta` ni
`Registrar preliminar`: son acciones irreversibles y no idempotentes ante
SUNAT. El alcance se limitó al camino seguro:

1. Crear el periodo tributario `202608`.
2. `Consultar periodo`.
3. `Comparar propuesta` (descarga asíncrona vía ticket).
4. `Actualizar ticket` (importa el archivo de propuesta y corre el cruce
   contra el registro de compras de Odoo).
5. Revisión de la pestaña "Diferencias".

## 2. Resultado paso a paso

| Paso | Resultado |
|---|---|
| Instalación del módulo | OK, sin errores de carga. |
| Consultar periodo | SUNAT devolvió código de estado `01` ("Presentado"). `local_state` avanzó a "Periodo consultado". Endpoint compartido con RVIE (`padron/periodos`), sin incidentes. |
| Comparar propuesta | Se creó el ticket SUNAT real (`numTicket`), servicio propio de Compras nunca antes probado contra producción. La llamada se aceptó sin error. |
| Actualizar ticket (1er intento) | El ticket terminó ("Terminado") y descargó el archivo real (189 comprobantes), pero el parseo **falló** — ver incidencia 3.1. |
| Corrección de la incidencia 3.1 | Aplicada, reintentado. |
| Actualizar ticket (2do intento) | Parseo exitoso, 189 líneas de propuesta cargadas. El cruce contra el registro de compras de Odoo dio **0 coincidencias** — ver incidencia 3.2. |
| Corrección de la incidencia 3.2 | Aplicada, recruzado. |
| Resultado final del cruce | Ver sección 4. |

## 3. Incidencias encontradas y corregidas

### 3.1 Layout del archivo de propuesta de Compras distinto al de Ventas

El parser de la propuesta (`sire_rce_periodo._sire_rce_parse_proposal_line`)
se había construido por analogía con el archivo de Ventas (RVIE), asumiendo
la misma estructura de columnas. El archivo real de Compras tiene un layout
distinto:

- Las columnas 0/1 corresponden al RUC/razón social del propio declarante
  (la compañía compradora), no al proveedor — el proveedor está en las
  columnas 11/12/13.
- La base imponible viene partida en **tres buckets** según destino del
  crédito fiscal (BI Gravado DG / DGNG / DNG), cada uno con su propio IGV,
  en vez de una única columna "BI Gravada".
- No existen columnas separadas de "exonerado"/"inafecto" como en Ventas.

Se corrigió el mapeo de columnas con los índices reales, confirmados contra
el archivo descargado de producción (agosto 2026, 189 líneas).

### 3.2 Filtro `l10n_pe_edi_is_required` anulaba el 100% de las facturas de compra

`_sire_rce_get_compras_register` heredó de RVIE un filtro por el campo
`l10n_pe_edi_is_required` (módulo `l10n_pe_edi`), asumiendo que por defecto
sería `True` para facturas sin ese campo relevante. En la práctica, ese
campo se calcula como `move.is_sale_document() and ...` — es decir, es
**siempre `False`** para facturas de proveedor (`in_invoice`/`in_refund`),
porque mide la obligación de **emitir** el comprobante electrónicamente, no
de recibirlo. Esto hacía que el registro de compras generado desde Odoo
diera **0 filas**, pese a haber 189 facturas de proveedor posteadas ese mes.

Se eliminó el filtro para el registro de compras (no existe un campo
equivalente evaluable del lado del comprador).

## 4. Resultado final del cruce (periodo 202608)

| Estado | Cantidad | Base imponible | Impuestos | Total |
|---|---:|---:|---:|---:|
| Coincide | 172 | S/ 52,938.69 | S/ 9,264.23 | S/ 62,202.92 |
| Falta en SUNAT | 13 | S/ 276.01 | S/ 49.69 | S/ 8,265.20 |
| Falta en Odoo | 14 | — | — | S/ 19,242.90 |
| Monto no coincide | 2 | S/ 239.38 | S/ 43.08 | S/ 282.46 |

**"Falta en SUNAT" (13 líneas) revisado en detalle**: 9 de las 13
corresponden a Recibos por Honorarios (tipo de comprobante `02`) de
personas naturales — comprobantes que legítimamente no generan crédito
fiscal IGV y por lo tanto no aparecen en la propuesta RCE de SUNAT. Las
4 restantes sí tienen base/IGV y ameritan revisión del contador (comprobantes
de proveedores habituales que no llegaron a la propuesta SUNAT de este
periodo). Las 14 líneas "Falta en Odoo" y las 2 con "Monto no coincide" no
se revisaron línea por línea en esta sesión — quedan para que el contador
las valide antes de aceptar la propuesta o registrar el preliminar.

## 5. Estado en que quedó el periodo

El periodo `202608` quedó en estado local **"Propuesta comparada"**, con
las 189 líneas de propuesta y las 201 líneas de diferencias ya calculadas
en `o18_cms`, listo para que el contador revise la pestaña "Diferencias"
antes de decidir si se acepta la propuesta o se reemplaza.

## 6. Riesgos que siguen sin validar en vivo

No fueron parte del alcance de esta sesión (son irreversibles/no
idempotentes ante SUNAT):

- `Aceptar propuesta` (`aceptapropuesta`).
- `Registrar preliminar` (`registrapreliminares`).
- `Descargar resumen` (formato/signo de `tipoReporte`).
- El wizard de reemplazo de propuesta (`codProceso=61`, subida TUS).
- El mapeo de códigos de error `1005`/`1008`/`1009` a los guardas locales
  de `Registrar preliminar`.

Antes de operar estos pasos en un cierre real de un periodo, repetir el
mismo criterio de esta validación: probar contra un periodo de bajo
impacto e inspeccionar la respuesta real de SUNAT antes de confiar en el
código.
