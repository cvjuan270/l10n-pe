# Registro de Compras y Registro de Ventas — estructuras oficiales SUNAT

Documento de referencia para validar los encabezados del reporte contra la norma.
Fuentes primarias descargadas de sunat.gob.pe (ver "Fuentes" al final).

---

## 0. Antes de comparar: definir CUÁL de los tres artefactos se está construyendo

"El reporte de compras y ventas de SUNAT" son en realidad tres cosas distintas, con
encabezados distintos. Un mismo módulo suele necesitar las tres, pero no se validan
contra la misma lista de campos:

| # | Artefacto | Uso | Norma | Nº campos |
|---|-----------|-----|-------|-----------|
| A | **Formato 8.1 / 14.1 impreso** (Excel/PDF) | Reporte legible, columnas agrupadas, para el contador y para exhibir en fiscalización | RS 234-2006/SUNAT, Anexo 2 | 28 col. (compras) / 22 col. (ventas) |
| B | **PLE — archivo TXT** `080100` / `140100` | Carga en el Programa de Libros Electrónicos | RS 361-2015/SUNAT, Anexos 1 y 2 | 41 + libres (compras) / 34 + libres (ventas) |
| C | **SIRE — archivo plano RCE / RVIE** | Reemplazo o comparación con la propuesta de SUNAT | RS 112-2021 mod. por RS 040-2022, Anexos 3 y 11 | 37 + libres (RCE) / 33 + libres (RVIE) |

**Situación normativa vigente (agosto 2026):** el **SIRE reemplazó al PLE** para el
Registro de Ventas e Ingresos (RVIE) y el Registro de Compras (RCE). La obligación se
completó para PRICOS en **enero de 2026** (RS 000217-2025/SUNAT postergó de julio 2025
a enero 2026, con discrecionalidad para no sancionar hasta el 31/01/2026). El PLE sigue
vigente **solo para los demás libros** (Diario, Mayor, Inventarios, Formato 13.1, etc.).

> **Consecuencia práctica:** si el objetivo es "cumplir con la ley" hoy, el entregable
> obligatorio es **C (SIRE)**. B (PLE 8.1/14.1) queda como histórico/contingencia y A
> como reporte de gestión y de exhibición. Conviene confirmar con el cliente contra cuál
> de los tres se generaron los encabezados que nos pasaron antes de dar por buena la
> comparación.

---

## A. Formato 8.1 — "REGISTRO DE COMPRAS" (layout impreso, 28 columnas)

Cabecera del documento: `PERIODO:` / `RUC:` / `APELLIDOS Y NOMBRES, DENOMINACIÓN O RAZÓN SOCIAL:`

| # | Encabezado oficial (texto literal) | Grupo |
|---|------------------------------------|-------|
| 1 | NÚMERO CORRELATIVO DEL REGISTRO O CÓDIGO ÚNICO DE LA OPERACIÓN | — |
| 2 | FECHA DE EMISIÓN DEL COMPROBANTE DE PAGO O DOCUMENTO | — |
| 3 | FECHA DE VENCIMIENTO O FECHA DE PAGO (1) | — |
| 4 | TIPO (TABLA 10) | COMPROBANTE DE PAGO O DOCUMENTO |
| 5 | N° SERIE O CÓDIGO DE LA DEPENDENCIA ADUANERA (TABLA 11) | COMPROBANTE DE PAGO O DOCUMENTO |
| 6 | AÑO DE EMISIÓN DE LA DUA O DSI | COMPROBANTE DE PAGO O DOCUMENTO |
| 7 | N° DEL COMPROBANTE DE PAGO, DOCUMENTO, N° DE ORDEN DEL FORMULARIO FÍSICO O VIRTUAL, N° DE DUA, DSI O LIQUIDACIÓN DE COBRANZA U OTROS DOCUMENTOS EMITIDOS POR SUNAT PARA ACREDITAR EL CRÉDITO FISCAL EN LA IMPORTACIÓN | — |
| 8 | TIPO (TABLA 2) | INFORMACIÓN DEL PROVEEDOR › DOCUMENTO DE IDENTIDAD |
| 9 | NÚMERO | INFORMACIÓN DEL PROVEEDOR › DOCUMENTO DE IDENTIDAD |
| 10 | APELLIDOS Y NOMBRES, DENOMINACIÓN O RAZÓN SOCIAL | INFORMACIÓN DEL PROVEEDOR |
| 11 | BASE IMPONIBLE | ADQUISICIONES GRAVADAS DESTINADAS A OPERACIONES **GRAVADAS Y/O DE EXPORTACIÓN** |
| 12 | IGV | ADQUISICIONES GRAVADAS DESTINADAS A OPERACIONES **GRAVADAS Y/O DE EXPORTACIÓN** |
| 13 | BASE IMPONIBLE | ADQUISICIONES GRAVADAS DESTINADAS A OPERACIONES **GRAVADAS Y/O DE EXPORTACIÓN Y A OPERACIONES NO GRAVADAS** |
| 14 | IGV | ADQUISICIONES GRAVADAS DESTINADAS A OPERACIONES **GRAVADAS Y/O DE EXPORTACIÓN Y A OPERACIONES NO GRAVADAS** |
| 15 | BASE IMPONIBLE | ADQUISICIONES GRAVADAS DESTINADAS A OPERACIONES **NO GRAVADAS** |
| 16 | IGV | ADQUISICIONES GRAVADAS DESTINADAS A OPERACIONES **NO GRAVADAS** |
| 17 | VALOR DE LAS ADQUISICIONES NO GRAVADAS | — |
| 18 | ISC | — |
| 19 | OTROS TRIBUTOS Y CARGOS | — |
| 20 | IMPORTE TOTAL | — |
| 21 | N° DE COMPROBANTE DE PAGO EMITIDO POR SUJETO NO DOMICILIADO (2) | — |
| 22 | NÚMERO | CONSTANCIA DE DEPÓSITO DE DETRACCIÓN (3) |
| 23 | FECHA DE EMISIÓN | CONSTANCIA DE DEPÓSITO DE DETRACCIÓN (3) |
| 24 | TIPO DE CAMBIO | — |
| 25 | FECHA | REFERENCIA DEL COMPROBANTE DE PAGO O DOCUMENTO ORIGINAL QUE SE MODIFICA |
| 26 | TIPO (TABLA 10) | REFERENCIA DEL COMPROBANTE ORIGINAL QUE SE MODIFICA |
| 27 | SERIE | REFERENCIA DEL COMPROBANTE ORIGINAL QUE SE MODIFICA |
| 28 | N° DEL COMPROBANTE DE PAGO O DOCUMENTO | REFERENCIA DEL COMPROBANTE ORIGINAL QUE SE MODIFICA |

Fila de **TOTALES** al pie. Notas al pie obligatorias:

1. Señalar la fecha correspondiente, de acuerdo a lo establecido en el literal b) del inciso II del numeral 1 del Artículo 10 del Reglamento de la Ley del IGV.
2. Sólo para los casos de utilización de servicios o adquisiciones de intangibles provenientes del exterior.
3. Sólo para los casos de detracciones. Es optativo el llenado cuando exista un sistema de enlace que mantenga dicha información y se pueda identificar los comprobantes de pago respecto de los cuales se efectuó el depósito.

---

## B. Formato 14.1 — "REGISTRO DE VENTAS E INGRESOS" (layout impreso, 22 columnas)

Cabecera: `PERIODO:` / `RUC:` / `APELLIDOS Y NOMBRES, DENOMINACIÓN O RAZÓN SOCIAL:`

| # | Encabezado oficial | Grupo |
|---|--------------------|-------|
| 1 | NÚMERO CORRELATIVO DEL REGISTRO O CÓDIGO ÚNICO DE LA OPERACIÓN | — |
| 2 | FECHA DE EMISIÓN DEL COMPROBANTE DE PAGO O DOCUMENTO | — |
| 3 | FECHA DE VENCIMIENTO Y/O PAGO | — |
| 4 | TIPO (TABLA 10) | COMPROBANTE DE PAGO O DOCUMENTO |
| 5 | N° SERIE O N° DE SERIE DE LA MÁQUINA REGISTRADORA | COMPROBANTE DE PAGO O DOCUMENTO |
| 6 | NÚMERO | COMPROBANTE DE PAGO O DOCUMENTO |
| 7 | TIPO (TABLA 2) | INFORMACIÓN DEL CLIENTE › DOCUMENTO DE IDENTIDAD |
| 8 | NÚMERO | INFORMACIÓN DEL CLIENTE › DOCUMENTO DE IDENTIDAD |
| 9 | APELLIDOS Y NOMBRES, DENOMINACIÓN O RAZÓN SOCIAL | INFORMACIÓN DEL CLIENTE |
| 10 | VALOR FACTURADO DE LA EXPORTACIÓN | — |
| 11 | BASE IMPONIBLE DE LA OPERACIÓN GRAVADA | — |
| 12 | EXONERADA | IMPORTE TOTAL DE LA OPERACIÓN EXONERADA O INAFECTA |
| 13 | INAFECTA | IMPORTE TOTAL DE LA OPERACIÓN EXONERADA O INAFECTA |
| 14 | ISC | — |
| 15 | IGV Y/O IPM | — |
| 16 | OTROS TRIBUTOS Y CARGOS QUE NO FORMAN PARTE DE LA BASE IMPONIBLE | — |
| 17 | IMPORTE TOTAL DEL COMPROBANTE DE PAGO | — |
| 18 | TIPO DE CAMBIO | — |
| 19 | FECHA | REFERENCIA DEL COMPROBANTE DE PAGO O DOCUMENTO ORIGINAL QUE SE MODIFICA |
| 20 | TIPO (TABLA 10) | REFERENCIA DEL COMPROBANTE ORIGINAL QUE SE MODIFICA |
| 21 | SERIE | REFERENCIA DEL COMPROBANTE ORIGINAL QUE SE MODIFICA |
| 22 | N° DEL COMPROBANTE DE PAGO O DOCUMENTO | REFERENCIA DEL COMPROBANTE ORIGINAL QUE SE MODIFICA |

Fila de **TOTALES** al pie.

> Ojo: el formato impreso de ventas **no** tiene columnas de IVAP ni de descuentos; el TXT del PLE sí.

---

## C. PLE — Formato 8.1 "REGISTRO DE COMPRAS" (archivo TXT `080100`)

Campos separados por `|`, uno por línea, cada línea termina en `|`.
Obl. = obligatorio · LU = llave única.

| Campo | Descripción | Long. | Formato | Obl. | LU |
|---|---|---|---|---|---|
| 1 | Periodo (AAAAMM00) | 8 | Numérico | Sí | Sí |
| 2 | CUO — Código Único de la Operación / correlativo del mes | hasta 40 | Texto | Sí | Sí |
| 3 | Número correlativo del asiento contable (1er dígito A, M u C) | 2–10 | Alfanum. | Sí | Sí |
| 4 | Fecha de emisión del comprobante de pago o documento | 10 | DD/MM/AAAA | Sí | No |
| 5 | Fecha de vencimiento o fecha de pago (1) | 10 | DD/MM/AAAA | No | No |
| 6 | Tipo de comprobante de pago o documento (Tabla 10) | 2 | Numérico | Sí | No |
| 7 | Serie del CP / código de la dependencia aduanera (DUA/DSI) | hasta 20 | Alfanum. | No | No |
| 8 | Año de emisión de la DUA o DSI | 4 | Numérico | No | No |
| 9 | Número del CP o documento / N° inicial del rango (2) | hasta 20 | Alfanum. | Sí | No |
| 10 | N° final del rango (2) | hasta 20 | Numérico | No | No |
| 11 | Tipo de documento de identidad del proveedor (Tabla 2) | 1 | Alfanum. | No | No |
| 12 | N° de RUC del proveedor o n° de documento de identidad | hasta 15 | Alfanum. | No | No |
| 13 | Apellidos y nombres, denominación o razón social del proveedor | hasta 100 | Texto | No | No |
| 14 | **BI** adquisiciones gravadas destinadas **exclusivamente a gravadas y/o exportación** | 12,2 | Numérico | No | No |
| 15 | IGV / IPM del campo 14 | 12,2 | Numérico | No | No |
| 16 | **BI** adquisiciones gravadas destinadas a **gravadas y/o exportación Y a no gravadas** | 12,2 | Numérico | No | No |
| 17 | IGV / IPM del campo 16 | 12,2 | Numérico | No | No |
| 18 | **BI** adquisiciones gravadas destinadas a **no gravadas** | 12,2 | Numérico | No | No |
| 19 | IGV / IPM del campo 18 | 12,2 | Numérico | No | No |
| 20 | Valor de las adquisiciones no gravadas | 12,2 | Numérico | No | No |
| 21 | ISC (cuando el sujeto puede utilizarlo como deducción) | 12,2 | Numérico | No | No |
| 22 | Otros conceptos, tributos y cargos que no forman parte de la BI | 12,2 | Numérico | No | No |
| 23 | **Importe total** según comprobante de pago (= suma campos 14 al 22) | 12,2 | Numérico | **Sí** | No |
| 24 | Código de la moneda (Tabla 4) | 3 | Alfanum. | No | No |
| 25 | Tipo de cambio (3) | 1 ent + 3 dec | Numérico | No | No |
| 26 | Fecha de emisión del CP que se modifica (4) | 10 | DD/MM/AAAA | No | No |
| 27 | Tipo del CP que se modifica (4) | 2 | Numérico | No | No |
| 28 | N° de serie del CP que se modifica (4) | hasta 20 | Alfanum. | No | No |
| 29 | Código de la dependencia aduanera de la DUA/DSI (4) | 3 | Alfanum. | No | No |
| 30 | Número del CP que se modifica (4) | hasta 20 | Alfanum. | No | No |
| 31 | Fecha de emisión de la Constancia de Depósito de Detracción (6) | 10 | DD/MM/AAAA | No | No |
| 32 | N° de la Constancia de Depósito de Detracción (6) | hasta 24 | Alfanum. | No | No |
| 33 | Marca del CP sujeto a retención (`1` si aplica, si no vacío) | 1 | Numérico | No | No |
| 34 | Clasificación de los bienes y servicios adquiridos (Tabla 30) — **solo ingresos > 1,500 UIT en el ejercicio anterior** | 1 | Numérico | No | No |
| 35 | Identificación del contrato o proyecto (operadores de consorcios / joint ventures sin contabilidad independiente) | 12 | Texto | No | No |
| 36 | Error tipo 1: inconsistencia en el tipo de cambio | 1 | Numérico | No | No |
| 37 | Error tipo 2: inconsistencia por proveedores no habidos | 1 | Numérico | No | No |
| 38 | Error tipo 3: inconsistencia por proveedores que renuncian a la exoneración del Apéndice I del IGV | 1 | Numérico | No | No |
| 39 | Error tipo 4: inconsistencia por DNIs usados en Liquidaciones de Compra que sí cuentan con RUC | 1 | Numérico | No | No |
| 40 | Indicador de comprobantes de pago cancelados con medios de pago (Tabla 1) | 1 | Numérico | No | No |
| 41 | **Estado** que identifica la oportunidad de la anotación o si corresponde a un ajuste (`0`,`1`,`6`,`7`,`9`) | 1 | Numérico | **Sí** | No |
| 42–82 | Campos de libre utilización | hasta 200 | Texto | No | No |

Notas de la norma:
1. Fecha según literal b), inciso II, numeral 1, Art. 10 del Reglamento de la Ley del IGV.
2. Aplica cuando se anota el importe total de operaciones diarias que no otorgan derecho a crédito fiscal en forma consolidada.
3. Conforme a las normas sobre la materia.
4. Notas de crédito/débito: el monto del ajuste va en las mismas columnas que se usarían para registrar la base imponible o el impuesto, con signo.
6. Detracciones: optativo si existe sistema de enlace que mantenga la información.

**Valores del campo 41 (Estado):**
- `0` — el CP no da derecho a crédito fiscal
- `1` — CP anotado en el período de emisión y que da derecho a crédito fiscal
- `6` — CP con derecho a crédito fiscal, emisión anterior al período de anotación, dentro de los 12 meses siguientes
- `7` — CP sin derecho a crédito fiscal, emisión anterior al período de anotación, posterior a 12 meses
- `9` — ajuste o rectificación de una operación registrada en un período anterior

### Formatos hermanos
- **8.2** — Registro de Compras · Información de operaciones con sujetos no domiciliados (`080200`): 36 campos + libres 37–72. Incluye renta bruta, deducción/costo, renta neta, tasa de retención, impuesto retenido, convenio de doble imposición, tipo de renta, modalidad del servicio, país de residencia y beneficiario efectivo.
- **8.3** — Registro de Compras Simplificado (`080300`): 31 campos + libres 32–62 (para RER / sujetos sin las tres columnas de destino de adquisiciones).

---

## D. PLE — Formato 14.1 "REGISTRO DE VENTAS E INGRESOS" (archivo TXT `140100`)

| Campo | Descripción | Long. | Formato | Obl. | LU |
|---|---|---|---|---|---|
| 1 | Periodo (AAAAMM00) | 8 | Numérico | Sí | Sí |
| 2 | CUO — Código Único de la Operación / correlativo del mes | hasta 40 | Texto | Sí | Sí |
| 3 | Número correlativo del asiento contable (1er dígito A, M u C) | 2–10 | Alfanum. | Sí | Sí |
| 4 | Fecha de emisión del comprobante de pago | 10 | DD/MM/AAAA | No¹ | No |
| 5 | Fecha de vencimiento o fecha de pago (1) | 10 | DD/MM/AAAA | No | No |
| 6 | Tipo de comprobante de pago o documento (Tabla 10) | 2 | Numérico | Sí | No |
| 7 | N° serie del CP o n° de serie de la máquina registradora | hasta 20 | Alfanum. | Sí | No |
| 8 | Número del comprobante de pago / n° inicial del rango (2) | hasta 20 | Alfanum. | Sí | No |
| 9 | N° final del rango (2) | hasta 20 | Numérico | No | No |
| 10 | Tipo de documento de identidad del cliente (Tabla 2) | 1 | Alfanum. | No | No |
| 11 | Número de documento de identidad del cliente | hasta 15 | Alfanum. | No | No |
| 12 | Apellidos y nombres, denominación o razón social del cliente | hasta 100 | Texto | No | No |
| 13 | Valor facturado de la exportación | 12,2 | Numérico | No | No |
| 14 | Base imponible de la operación gravada (4) | 12,2 | Numérico | No | No |
| 15 | Descuento de la base imponible | 12,2 | Numérico | No | No |
| 16 | IGV y/o IPM | 12,2 | Numérico | No | No |
| 17 | Descuento del IGV y/o IPM | 12,2 | Numérico | No | No |
| 18 | Importe total de la operación exonerada | 12,2 | Numérico | No | No |
| 19 | Importe total de la operación inafecta | 12,2 | Numérico | No | No |
| 20 | ISC, de ser el caso | 12,2 | Numérico | No | No |
| 21 | Base imponible de la operación gravada con el IVAP (oblig. si campo 6 = `49`) | 12,2 | Numérico | No | No |
| 22 | Impuesto a las Ventas del Arroz Pilado (oblig. si campo 6 = `49`) | 12,2 | Numérico | No | No |
| 23 | Otros conceptos, tributos y cargos que no forman parte de la BI | 12,2 | Numérico | No | No |
| 24 | Importe total del comprobante de pago | 12,2 | Numérico | No | No |
| 25 | Código de la moneda (Tabla 4) | 3 | Alfanum. | No | No |
| 26 | Tipo de cambio (5) — oblig. si campo 25 tiene dato | 1 ent + 3 dec | Numérico | No | No |
| 27 | Fecha de emisión del CP original que se modifica (6) | 10 | DD/MM/AAAA | No | No |
| 28 | Tipo del CP que se modifica (6) | 2 | Numérico | No | No |
| 29 | N° de serie del CP que se modifica / código de la dependencia aduanera (6) | hasta 20 | Alfanum. | No | No |
| 30 | Número del CP que se modifica / N° de la DUA (6) | hasta 20 | Alfanum. | No | No |
| 31 | Identificación del contrato o proyecto (consorcios / joint ventures) | 12 | Texto | No | No |
| 32 | Error tipo 1: inconsistencia en el tipo de cambio | 1 | Numérico | No | No |
| 33 | Indicador de comprobantes de pago cancelados con medios de pago (Tabla 1) | 1 | Numérico | No | No |
| 34 | **Estado** que identifica la oportunidad de la anotación (`0`,`1`,`2`,`8`,`9`) | 1 | Numérico | **Sí** | No |
| 35–68 | Campos de libre utilización | hasta 200 | Texto | No | No |

¹ Obligatorio excepto cuando campo 34 = `2` (documento inutilizado).

**Valores del campo 34 (Estado):**
- `0` — anotación optativa sin efecto en el IGV del período
- `1` — operación (ventas gravadas, exoneradas, inafectas y/o exportaciones), NC y ND del período
- `2` — documento inutilizado durante el período (previamente emitido y NO entregado, o durante su emisión)
- `8` — operación de un período anterior, NO anotada en dicho período
- `9` — operación de un período anterior, SÍ anotada en dicho período (ajuste/rectificación)

**Formato 14.2** — Registro de Ventas Simplificado (`140200`): 25 campos + libres 26–50.

### Reglas transversales del PLE (aplican a 8.1 y 14.1)
- Separador de campos: `|` (pipe/palote). Cada línea termina con `|`.
- Notas de crédito (tipo `07`) se registran con **valor negativo**.
- No se acepta el carácter `&` en los campos 2 y 3.
- Campos numéricos: hasta 12 enteros y hasta 2 decimales, **sin comas de miles**.
- Tablas de parámetros: son las del **Anexo N.º 3 de la RS 286-2009/SUNAT** y modificatorias
  (Tabla 2 = tipo de documento de identidad; Tabla 4 = moneda; Tabla 10 = tipo de comprobante;
  Tabla 11 = código de aduana; Tabla 30 = clasificación de bienes y servicios).
- **Nombre del archivo:**
  `LE` + `RUC(11)` + `AAAA` + `MM` + `DD` + `CódigoLibro(6)` + `CodOportunidad(2)` + `IndOperaciones(1)` + `IndContenido(1)` + `IndMonedaExtranjera(1)` + `IndLibroElectrónico(1)` + `.TXT`
  - Código de libro: `080100` compras · `080200` compras no domiciliados · `080300` compras simplificado · `140100` ventas · `140200` ventas simplificado.
  - Ejemplo: `LE2012345678920260800080100001111.TXT`

---

## E. SIRE — RCE, archivo plano de reemplazo/comparación (Anexo N.º 11)

Este es el **entregable vigente para compras**. Nemotécnico = nombre corto de la columna en el
archivo del SIRE.

| Campo | Nemotécnico | Descripción | Long. | Formato |
|---|---|---|---|---|
| 1 | RUC | RUC del generador u obligado a llevar el Registro de Compras | 11 | Numérico |
| 2 | ID | Apellidos y nombres / razón social del generador | hasta 1500 | Alfanum. |
| 3 | Periodo | Periodo (AAAAMM) | 6 | Numérico |
| 4 | CAR SUNAT | Código de Anotación de Registro (Tabla 7) — *se completa automáticamente* | 27 | Alfanum. |
| 5 | Fecha de emisión | Fecha de emisión del CP o documento | 10 | DD/MM/AAAA |
| 6 | Fecha Vcto/Pago | Fecha de vencimiento o fecha de pago (5) | 10 | DD/MM/AAAA |
| 7 | Tipo CP/Doc. | Tipo de comprobante de pago o documento (Tabla 11) | 2 | Alfanum. |
| 8 | Serie del CDP | Serie del CP / n° de máquina registradora / dependencia aduanera | hasta 20 | Alfanum. |
| 9 | Año | Año de emisión de la DAM o DSI o Liquidación de Cobranza | 4 | Numérico |
| 10 | Nro CP o Doc. Nro Inicial (Rango) | Número del CP o n° inicial del rango consolidado (9) | hasta 20 | Alfanum. |
| 11 | Nro Final (Rango) | N° final del rango consolidado (9) | hasta 20 | Alfanum. |
| 12 | Tipo Doc Identidad | Tipo de documento de identidad del proveedor / operador / partícipe | 1 | Alfanum. |
| 13 | Nro Doc Identidad | N° de RUC o documento de identidad del proveedor / operador / partícipe | hasta 15 | Alfanum. |
| 14 | Apellidos Nombres/ Razon Social | Nombre o razón social del proveedor / operador / partícipe | hasta 1500 | Alfanum. |
| 15 | BI Gravado DG | BI de adquisiciones gravadas **destinadas exclusivamente a gravadas y/o exportación** | 12,2 | Numérico |
| 16 | IGV / IPM DG | IGV/IPM del campo 15 | 12,2 | Numérico |
| 17 | BI Gravado DGNG | BI de adquisiciones gravadas destinadas a **gravadas y/o exportación Y a no gravadas** | 12,2 | Numérico |
| 18 | IGV / IPM DGNG | IGV/IPM del campo 17 | 12,2 | Numérico |
| 19 | BI Gravado DNG | BI de adquisiciones gravadas destinadas a **no gravadas** | 12,2 | Numérico |
| 20 | IGV / IPM DNG | IGV/IPM del campo 19 | 12,2 | Numérico |
| 21 | Valor Adq. NG | Valor de las adquisiciones no gravadas (exoneradas + inafectas) | 12,2 | Numérico |
| 22 | ISC | ISC deducible | 12,2 | Numérico |
| 23 | ICBPER | **Impuesto al Consumo de las Bolsas de Plástico** | 12,2 | Numérico |
| 24 | Otros Trib/ Cargos | Otros conceptos, tributos, cargos y descuentos fuera de la BI | 12,2 | Numérico |
| 25 | Total CP | Importe total de las adquisiciones según comprobante | 12,2 | Numérico |
| 26 | Moneda | Código de la moneda (Tabla 2 del Anexo N.º 1) | 3 | Alfanum. |
| 27 | Tipo de Cambio | Tipo de cambio (4) | 1 ent + 3 dec | Numérico |
| 28 | Fecha Emision Doc Modificado | Fecha de emisión del CP original que se modifica | 10 | DD/MM/AAAA |
| 29 | Tipo CP Modificado | Tipo del CP que se modifica | 2 | Alfanum. |
| 30 | Serie CP Modificado | N° de serie del CP que se modifica | hasta 20 | Alfanum. |
| 31 | COD. DAM O DSI | Código de la dependencia aduanera de la DAM/DSI (oblig. si campo 29 = `50`/`52`) | 3 | Alfanum. |
| 32 | Nro CP Modificado | Número del CP que se modifica | hasta 20 | Alfanum. |
| 33 | Clasif de Bss y Sss | Clasificación de bienes y servicios adquiridos (Tabla 23) — **solo > 1,500 UIT** | 1 | Numérico |
| 34 | ID Proyecto Operadores/Partícipes | Identificación del contrato/proyecto (consorcios, joint ventures) | hasta 50 | Alfanum. |
| 35 | PorcPart | % de participación en el contrato o proyecto (7) | 2 ent + 2 dec | Numérico |
| 36 | IMB | Impuesto materia de beneficio Ley 31053 (10) | 12,2 | Numérico |
| 37 | CAR Orig | CAR del CP a modificar (vacío; aplica para ajustes posteriores) | 27 | Alfanum. |
| 38–41 | *(auto)* | Completados automáticamente a partir de la propuesta | — | — |
| 42–80 | CLUtiliz | Campos de libre utilización | hasta 200 | Texto |

**Diferencias clave contra el PLE 8.1** — si el reporte se armó con la lista del PLE, van a faltar:
- `ICBPER` (campo 23) — no existe en el PLE 8.1.
- `CAR SUNAT` (campo 4) y `CAR Orig` (campo 37) — reemplazan el rol del CUO.
- `IMB` (campo 36, Ley 31053).
- `PorcPart` (campo 35).
- Y sobran: los cuatro campos "Error tipo 1..4" (36–39 del PLE), la marca de retención y las
  columnas de la constancia de detracción, que en el SIRE no van en este anexo.
- Longitudes distintas: razón social pasa de 100 a **1500**; el ID del proyecto de 12 a **50**.

Reglas del Anexo 11 a tener presentes al generar:
- Solo se anotan CP autorizados (electrónico con CDR aceptado o estado aceptado); no se anotan
  duplicados, ni dados de baja/revertidos, ni anulados con Nota de Crédito Tipo 02 por error en RUC.
- Los CP electrónicos con CDR distinto a aceptado, con baja comunicada, y los físicos anulados,
  se anotan con **importe cero (0.00)**.
- Suma de campos 15 + 17 + 19 debe corresponder al total de la BI del IGV del comprobante.
- Suma de campos 16 + 18 + 20 debe corresponder al total del IGV.
- Si no hay dato, consignar `0.00` (no vacío) en los numéricos.

---

## F. SIRE — RVIE, archivo plano de reemplazo/comparación (Anexo N.º 3)

Este es el **entregable vigente para ventas**.

| Campo | Nemotécnico | Descripción | Long. | Formato |
|---|---|---|---|---|
| 1 | RUC | RUC del generador u obligado a llevar el Registro de Ventas e Ingresos | 11 | Numérico |
| 2 | ID | Apellidos y nombres / razón social del generador | hasta 1500 | Alfanum. |
| 3 | Periodo | Periodo (AAAAMM) | 6 | Numérico |
| 4 | CAR SUNAT | Código de Anotación de Registro (Tabla 7) — *se completa automáticamente* | 27 | Alfanum. |
| 5 | Fecha de emisión | Fecha de emisión del CP o documento | 10 | DD/MM/AAAA |
| 6 | Fecha Vcto/Pago | Fecha de vencimiento o de pago (oblig. si campo 7 = `14`) | 10 | DD/MM/AAAA |
| 7 | Tipo CP/Doc. | Tipo de comprobante de pago o documento (Tabla 3 del Anexo N.º 1) | 2 | Alfanum. |
| 8 | Serie del CDP | N° de serie del CP o de la máquina registradora | hasta 20 | Alfanum. |
| 9 | Nro CP o Doc. Nro Inicial (Rango) | Número del CP o n° inicial del rango | hasta 20 | Alfanum. |
| 10 | Nro Final (Rango) | N° final del rango (consolidación diaria de boletas) | hasta 20 | Alfanum. |
| 11 | Tipo Doc Identidad | Tipo de documento de identidad del cliente | 1 | Alfanum. |
| 12 | Nro Doc Identidad | N° de RUC o documento de identidad del cliente | hasta 15 | Alfanum. |
| 13 | Apellidos Nombres/ Razón Social | Nombre o razón social del cliente | hasta 1500 | Alfanum. |
| 14 | Valor Facturado Exportación | Valor facturado de la exportación | 12,2 | Numérico |
| 15 | BI Gravada | Base imponible de la operación gravada | 12,2 | Numérico |
| 16 | Dscto BI | Descuento de la base imponible (solo tipo CP `07`/`87`) | 12,2 | Numérico |
| 17 | IGV / IPM | IGV y/o IPM | 12,2 | Numérico |
| 18 | Dscto IGV / IPM | Descuento del IGV y/o IPM (solo tipo CP `07`/`87`) | 12,2 | Numérico |
| 19 | Mto Exonerado | Importe total de la operación exonerada | 12,2 | Numérico |
| 20 | Mto Inafecto | Importe total de la operación inafecta | 12,2 | Numérico |
| 21 | ISC | Impuesto Selectivo al Consumo | 12,2 | Numérico |
| 22 | BI Grav IVAP | Base imponible gravada con el IVAP (oblig. si campo 7 = `49`) | 12,2 | Numérico |
| 23 | IVAP | Impuesto a las Ventas del Arroz Pilado (oblig. si campo 7 = `49`) | 12,2 | Numérico |
| 24 | ICBPER | **Impuesto al Consumo de las Bolsas de Plástico** (oblig. si campo 7 = `01`,`03`,`07`,`08`,`12`) | 12,2 | Numérico |
| 25 | Otros Tributos | Otros tributos, cargos y descuentos fuera de la base imponible | 12,2 | Numérico |
| 26 | Total CP | Importe total del comprobante de pago | 12,2 | Numérico |
| 27 | Moneda | Código de la moneda (ISO 4217 Alpha, Tabla 3 del Anexo N.º 1) | 3 | Alfanum. |
| 28 | Tipo Cambio | Tipo de cambio (oblig. si campo 27 ≠ PEN) | 1 ent + 3 dec | Numérico |
| 29 | Fecha Emisión Doc Modificado | Fecha de emisión del CP original que se modifica | 10 | DD/MM/AAAA |
| 30 | Tipo CP Modificado | Tipo del CP que se modifica | 2 | Numérico |
| 31 | Serie CP Modificado | N° de serie del CP que se modifica o código de dependencia aduanera | hasta 20 | Alfanum. |
| 32 | Nro CP Modificado | Número del CP que se modifica o número de la DAM | hasta 20 | Alfanum. |
| 33 | ID Proyecto Operadores Atribución | Identificación del contrato/proyecto (consorcios, joint ventures) | hasta 50 | Alfanum. |
| 34–40 | *(auto)* | Completados automáticamente a partir de la propuesta | — | — |
| 41–57 | CLU | Campos de libre utilización | hasta 200 | Texto |

**Diferencias clave contra el PLE 14.1:**
- Aparece `ICBPER` (campo 24) — no existe en el PLE 14.1.
- Aparece `CAR SUNAT` en lugar del CUO/correlativo de asiento (el PLE tenía campos 2 y 3; el RVIE
  no lleva número correlativo del asiento contable).
- Desaparecen: "Error tipo 1", "Indicador de comprobantes cancelados con medios de pago" y el
  campo "Estado" (34 del PLE) como campo informado — en el RVIE lo determina SUNAT.
- Longitudes distintas: razón social 100 → **1500**; ID de proyecto 12 → **50**.
- En **notas múltiples**, los campos 29–32 admiten varios valores separados por coma, con
  longitud 1500.
- CP electrónicos con CDR distinto a aceptado, con baja comunicada, o físicos anulados: se
  anotan con **importe cero (0.00)**.

---

## G. Checklist para validar los encabezados que nos entregaron

1. **Identificar el artefacto**: ¿la lista recibida tiene ~28/22 columnas (impreso), 41/34 (PLE) o 37/33 (SIRE)? El conteo ya descarta dos de las tres opciones.
2. **Compras — verificar que existan las TRES parejas de destino** (BI + IGV para: solo gravadas, gravadas+no gravadas, solo no gravadas). Es el error más frecuente: reportes que traen una sola columna de "Base imponible" e "IGV". No cumple.
3. **Verificar el ICBPER** si el destino es SIRE. Si la lista viene del PLE 8.1/14.1 clásico, no lo va a tener.
4. **Verificar el campo Estado / oportunidad de la anotación** (campo 41 en compras PLE, 34 en ventas PLE). Es obligatorio y es el que soporta la anotación de comprobantes de períodos anteriores.
5. **Verificar los cuatro campos de referencia de NC/ND** (fecha, tipo, serie, número del documento modificado). Sin ellos las notas de crédito no se pueden vincular.
6. **Verificar signos**: notas de crédito en negativo.
7. **Verificar el bloque de detracción** (constancia: número + fecha) en compras: obligatorio en el formato impreso salvo sistema de enlace.
8. **Verificar longitudes**: razón social 100 (PLE) vs 1500 (SIRE); son incompatibles si se reusa el mismo generador.
9. **Verificar el tipo de cambio**: obligatorio cuando la moneda ≠ PEN, con 3 decimales, y debe ser el publicado a la fecha de emisión (compras) — enlaza con el módulo `l10n_pe_currency_rate_bcrp` que ya está en el repo.
10. **Verificar tablas de parámetros**: tipo de comprobante y tipo de documento de identidad deben salir de las tablas SUNAT, no de códigos internos.

---

## Fuentes

- [RS 361-2015/SUNAT — Anexo N.º 1: Estructura del Registro de Ventas e Ingresos Electrónico](https://www.sunat.gob.pe/legislacion/superin/2015/anexo1-361-2015.pdf)
- [RS 361-2015/SUNAT — Anexo N.º 2: Estructura del Registro de Compras Electrónico](https://www.sunat.gob.pe/legislacion/superin/2015/anexo2-361-2015.pdf)
- [RS 234-2006/SUNAT — Formato 8.1 Registro de Compras (XLS oficial)](https://www.sunat.gob.pe/legislacion/superin/2006/234_formato81.xls)
- [RS 234-2006/SUNAT — Formato 14.1 Registro de Ventas e Ingresos (XLS oficial)](https://www.sunat.gob.pe/legislacion/superin/2006/234_formato141.xls)
- [RS 234-2006/SUNAT (texto de la resolución)](https://www.sunat.gob.pe/legislacion/superin/2006/234.htm)
- [RS 112-2021/SUNAT — Anexos (incluye Anexo N.º 3, estructura del RVIE)](https://www.sunat.gob.pe/legislacion/superin/2021/anexo-112-2021.pdf)
- [RS 040-2022/SUNAT — Resolución](https://www.sunat.gob.pe/legislacion/superin/2022/040-2022.pdf)
- [RS 040-2022/SUNAT — Anexos (incluye Anexo N.º 8 y Anexo N.º 11, estructura del RCE)](https://www.sunat.gob.pe/legislacion/superin/2022/anexo-040-2022.pdf)
- [SUNAT — Registro de Compras Electrónico RCE](https://cpe.sunat.gob.pe/node/160)
- [SUNAT — Estructura de archivos (CPE/SIRE)](https://cpe.sunat.gob.pe/estructura-de-archivos)
