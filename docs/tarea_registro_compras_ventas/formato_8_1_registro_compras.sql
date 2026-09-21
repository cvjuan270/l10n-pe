-- =====================================================================================
-- FORMATO 8.1 : "REGISTRO DE COMPRAS"  (layout impreso, 28 columnas)
-- RS 234-2006/SUNAT, Anexo 2
--
-- Base de datos : o18_cms   (Odoo 18 + l10n_pe)
--
-- Uso en pantalla:
--   PGPASSWORD=odoo18 psql -h localhost -U odoo18 -d o18_cms \
--     -f formato_8_1_registro_compras.sql
--
-- Exportar a CSV para abrir en Excel (encabezados en la primera fila):
--   PGPASSWORD=odoo18 psql -h localhost -U odoo18 -d o18_cms \
--     --csv -P csv_fieldsep=';' -f formato_8_1_registro_compras.sql \
--     > registro_compras_8_1.csv
--   (en Excel: Datos > Desde texto/CSV, delimitador ';', codificacion UTF-8)
--
-- Ajustar los tres parametros del CTE "par" (empresa y rango de fechas).
-- Un solo statement: devuelve las 28 columnas oficiales + fila TOTALES.
-- Las dos ultimas columnas (_DIAG_...) NO son parte del formato; son controles
-- internos, eliminarlas al exportar. Ver notas (E) y (F) al pie.
--
-- IMPORTANTE: el query no debe contener NINGUN caracter porcentaje, ni siquiera
-- dentro de un comentario. El modulo OCA sql_export ejecuta cr.mogrify(query, dict)
-- y psycopg2 lo interpreta como marcador de posicion, fallando con
-- "TypeError: dict is not a sequence". Ver nota (M).
-- =====================================================================================

WITH par AS (
    SELECT 1::int             AS company_id,     -- <<< empresa (1 = CLINICA MALL SALUD, 2 = ISM CORPORATE)
           DATE '2026-06-01'  AS fecha_desde,    -- <<< inicio del periodo
           DATE '2026-06-30'  AS fecha_hasta     -- <<< fin del periodo
),

-- Comprobantes de compra del periodo -----------------------------------------------
-- Solo diarios con l10n_latam_use_documents = TRUE, es decir los que registran
-- comprobantes con tipo de documento SUNAT. Ver nota (L).
mov AS (
    SELECT am.id,
           am.name,
           am.invoice_date,
           am.invoice_date_due,
           am.move_type,
           am.currency_id,
           am.invoice_currency_rate,
           am.amount_total_signed,
           am.commercial_partner_id,
           dt.code                                            AS tipo_cp,
           COALESCE(am.reversed_entry_id, am.debit_origin_id) AS ref_move_id,
           d.serie,
           d.numero,
           co.currency_id                                     AS moneda_empresa
      FROM account_move am
      JOIN par                ON TRUE
      JOIN res_company    co  ON co.id = am.company_id
      JOIN account_journal j  ON j.id  = am.journal_id
      LEFT JOIN l10n_latam_document_type dt ON dt.id = am.l10n_latam_document_type_id
      -- Serie y numero se obtienen del account_move.name separando por '-'.
      -- Ver nota (I).
      CROSS JOIN LATERAL (
          SELECT CASE WHEN strpos(x.doc, '-') > 0
                      THEN split_part(x.doc, '-', 1) END           AS serie,
                 CASE WHEN strpos(x.doc, '-') > 0
                      THEN split_part(x.doc, '-', 2)
                      ELSE x.doc END                               AS numero
            FROM (SELECT regexp_replace(am.name, '^.*\s', '') AS doc) x
      ) d
     WHERE am.company_id = par.company_id
       AND am.state      = 'posted'
       AND am.move_type IN ('in_invoice', 'in_refund')
       AND am.invoice_date BETWEEN par.fecha_desde AND par.fecha_hasta
       AND j.l10n_latam_use_documents = TRUE
),

-- Clasificacion de cada linea de producto por grupo de impuesto ---------------------
-- Una linea puede tener varios impuestos (p.ej. IGV + RET); se elige uno solo por
-- prioridad para no duplicar la base imponible.
lin AS (
    SELECT DISTINCT ON (aml.id)
           aml.id,
           aml.move_id,
           aml.balance,
           g.name->>'en_US' AS grupo
      FROM account_move_line aml
      LEFT JOIN account_move_line_account_tax_rel r ON r.account_move_line_id = aml.id
      LEFT JOIN account_tax       t ON t.id = r.account_tax_id
      LEFT JOIN account_tax_group g ON g.id = t.tax_group_id
     WHERE aml.move_id      IN (SELECT id FROM mov)
       AND aml.display_type = 'product'
     ORDER BY aml.id,
              CASE g.name->>'en_US'
                   WHEN 'IGV'      THEN 1    -- destinadas solo a gravadas / exportacion
                   WHEN 'IGV GyNG' THEN 2    -- destinadas a gravadas y a no gravadas
                   WHEN 'IGV NG'   THEN 3    -- destinadas solo a no gravadas
                   WHEN 'GRA'      THEN 4
                   WHEN 'EXP'      THEN 5
                   WHEN 'EXO'      THEN 6
                   WHEN 'INA'      THEN 7
                   WHEN 'ISC'      THEN 8
                   WHEN 'RET'      THEN 20
                   WHEN 'DET'      THEN 21
                   ELSE 30
              END
),

-- Bases imponibles por destino de la adquisicion -----------------------------------
base AS (
    SELECT move_id,
           SUM(CASE WHEN grupo IN ('IGV','GRA')        THEN balance ELSE 0 END) AS bi_dg,
           SUM(CASE WHEN grupo = 'IGV GyNG'            THEN balance ELSE 0 END) AS bi_dgng,
           SUM(CASE WHEN grupo = 'IGV NG'              THEN balance ELSE 0 END) AS bi_dng,
           SUM(CASE WHEN grupo IN
                    ('EXO','INA','EXP','RET','DET')    THEN balance ELSE 0 END) AS no_gravadas,
           SUM(CASE WHEN grupo IS NULL                 THEN balance ELSE 0 END) AS sin_clasificar
      FROM lin
     GROUP BY move_id
),

-- Impuestos desde las lineas de impuesto -------------------------------------------
-- RET (retencion 4ta categoria) y DET (detraccion) se excluyen a proposito: no
-- forman parte del importe del comprobante, ver nota (D).
imp AS (
    SELECT aml.move_id,
           SUM(CASE WHEN g.name->>'en_US' = 'IGV'      THEN aml.balance ELSE 0 END) AS igv_dg,
           SUM(CASE WHEN g.name->>'en_US' = 'IGV GyNG' THEN aml.balance ELSE 0 END) AS igv_dgng,
           SUM(CASE WHEN g.name->>'en_US' = 'IGV NG'   THEN aml.balance ELSE 0 END) AS igv_dng,
           SUM(CASE WHEN g.name->>'en_US' = 'ISC'      THEN aml.balance ELSE 0 END) AS isc,
           SUM(CASE WHEN g.name->>'en_US' NOT IN
                    ('IGV','IGV GyNG','IGV NG','ISC','RET','DET')
                                                       THEN aml.balance ELSE 0 END) AS otros
      FROM account_move_line aml
      JOIN account_tax       t ON t.id = aml.tax_line_id
      JOIN account_tax_group g ON g.id = t.tax_group_id
     WHERE aml.move_id      IN (SELECT id FROM mov)
       AND aml.display_type = 'tax'
     GROUP BY aml.move_id
),

-- Una fila por comprobante ----------------------------------------------------------
reg AS (
    SELECT
        1                                                                       AS _orden,
        -- Numero correlativo del registro, generado en el mismo orden en que se
        -- imprime el registro. Ver nota (K).
        to_char(ROW_NUMBER() OVER (ORDER BY m.invoice_date,
                                            m.tipo_cp,
                                            m.serie,
                                            lpad(m.numero, 20, '0')),
                'FM00000000')                                                   AS "NUM_CORRELATIVO",
        to_char(m.invoice_date,     'DD/MM/YYYY')                               AS "FECHA_EMISION",
        to_char(m.invoice_date_due, 'DD/MM/YYYY')                               AS "FECHA_VCTO_PAGO",
        m.tipo_cp                                                               AS "CP_TIPO",
        m.serie                                                                 AS "CP_SERIE_O_COD_ADUANA",
        CASE WHEN m.tipo_cp IN ('50','52','53','54')
             THEN to_char(m.invoice_date, 'YYYY') END                           AS "CP_ANIO_DUA_DSI",
        m.numero                                                                AS "CP_NUMERO",
        it.l10n_pe_vat_code                                                     AS "PROV_TIPO_DOC",
        p.vat                                                                   AS "PROV_NUM_DOC",
        p.name                                                                  AS "PROV_RAZON_SOCIAL",
        ROUND(COALESCE(b.bi_dg,       0), 2)                                    AS "BI_GRAVADAS_DG",
        ROUND(COALESCE(i.igv_dg,      0), 2)                                    AS "IGV_DG",
        ROUND(COALESCE(b.bi_dgng,     0), 2)                                    AS "BI_GRAVADAS_DGNG",
        ROUND(COALESCE(i.igv_dgng,    0), 2)                                    AS "IGV_DGNG",
        ROUND(COALESCE(b.bi_dng,      0), 2)                                    AS "BI_GRAVADAS_DNG",
        ROUND(COALESCE(i.igv_dng,     0), 2)                                    AS "IGV_DNG",
        ROUND(COALESCE(b.no_gravadas, 0), 2)                                    AS "VALOR_ADQ_NO_GRAVADAS",
        ROUND(COALESCE(i.isc,         0), 2)                                    AS "ISC",
        ROUND(COALESCE(i.otros,       0), 2)                                    AS "OTROS_TRIB_CARGOS",
        -- Importe total = suma de las columnas del registro, conforme a la regla del
        -- campo 23 del PLE 8.1 ("suma de los campos 14 al 22"). Ver nota (D).
        ROUND(COALESCE(b.bi_dg,0)   + COALESCE(i.igv_dg,0)
            + COALESCE(b.bi_dgng,0) + COALESCE(i.igv_dgng,0)
            + COALESCE(b.bi_dng,0)  + COALESCE(i.igv_dng,0)
            + COALESCE(b.no_gravadas,0)
            + COALESCE(i.isc,0)     + COALESCE(i.otros,0), 2)                   AS "IMPORTE_TOTAL",
        NULL::varchar                                                           AS "CP_SUJETO_NO_DOMICILIADO",
        NULL::varchar                                                           AS "DETRACCION_NUMERO",
        NULL::varchar                                                           AS "DETRACCION_FECHA",
        CASE WHEN m.currency_id <> m.moneda_empresa
                  AND COALESCE(m.invoice_currency_rate, 0) <> 0
             THEN ROUND(1 / m.invoice_currency_rate, 3) END                     AS "TIPO_CAMBIO",
        to_char(rm.invoice_date, 'DD/MM/YYYY')                                  AS "REF_FECHA",
        rdt.code                                                                AS "REF_TIPO",
        rd.serie                                                                AS "REF_SERIE",
        rd.numero                                                               AS "REF_NUMERO",
        ROUND(COALESCE(b.sin_clasificar, 0), 2)                                 AS "_DIAG_BASE_SIN_IMPUESTO",
        ROUND(COALESCE(b.bi_dg,0)   + COALESCE(i.igv_dg,0)
            + COALESCE(b.bi_dgng,0) + COALESCE(i.igv_dgng,0)
            + COALESCE(b.bi_dng,0)  + COALESCE(i.igv_dng,0)
            + COALESCE(b.no_gravadas,0)
            + COALESCE(i.isc,0)     + COALESCE(i.otros,0)
            + COALESCE(b.sin_clasificar,0)
            + m.amount_total_signed, 2)                                         AS "_DIAG_DIF_VS_ODOO"
      FROM mov m
      LEFT JOIN base b ON b.move_id = m.id
      LEFT JOIN imp  i ON i.move_id = m.id
      LEFT JOIN res_partner p                     ON p.id  = m.commercial_partner_id
      LEFT JOIN l10n_latam_identification_type it ON it.id = p.l10n_latam_identification_type_id
      LEFT JOIN account_move rm                   ON rm.id = m.ref_move_id
      LEFT JOIN l10n_latam_document_type rdt      ON rdt.id = rm.l10n_latam_document_type_id
      -- Serie y numero del comprobante referenciado, mismo criterio que arriba.
      CROSS JOIN LATERAL (
          SELECT CASE WHEN strpos(y.doc, '-') > 0
                      THEN split_part(y.doc, '-', 1) END           AS serie,
                 CASE WHEN strpos(y.doc, '-') > 0
                      THEN split_part(y.doc, '-', 2)
                      ELSE y.doc END                               AS numero
            FROM (SELECT regexp_replace(rm.name, '^.*\s', '') AS doc) y
      ) rd
),

-- Detalle + fila TOTALES -------------------------------------------------------------
salida AS (
    SELECT * FROM reg
    UNION ALL
    SELECT
        2, 'TOTALES', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        SUM("BI_GRAVADAS_DG"),   SUM("IGV_DG"),
        SUM("BI_GRAVADAS_DGNG"), SUM("IGV_DGNG"),
        SUM("BI_GRAVADAS_DNG"),  SUM("IGV_DNG"),
        SUM("VALOR_ADQ_NO_GRAVADAS"), SUM("ISC"), SUM("OTROS_TRIB_CARGOS"),
        SUM("IMPORTE_TOTAL"),
        NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        SUM("_DIAG_BASE_SIN_IMPUESTO"), SUM("_DIAG_DIF_VS_ODOO")
      FROM reg
)

SELECT
    "NUM_CORRELATIVO", "FECHA_EMISION", "FECHA_VCTO_PAGO",
    "CP_TIPO", "CP_SERIE_O_COD_ADUANA", "CP_ANIO_DUA_DSI", "CP_NUMERO",
    "PROV_TIPO_DOC", "PROV_NUM_DOC", "PROV_RAZON_SOCIAL",
    "BI_GRAVADAS_DG", "IGV_DG",
    "BI_GRAVADAS_DGNG", "IGV_DGNG",
    "BI_GRAVADAS_DNG", "IGV_DNG",
    "VALOR_ADQ_NO_GRAVADAS", "ISC", "OTROS_TRIB_CARGOS", "IMPORTE_TOTAL",
    "CP_SUJETO_NO_DOMICILIADO", "DETRACCION_NUMERO", "DETRACCION_FECHA",
    "TIPO_CAMBIO",
    "REF_FECHA", "REF_TIPO", "REF_SERIE", "REF_NUMERO",
    "_DIAG_BASE_SIN_IMPUESTO", "_DIAG_DIF_VS_ODOO"
  FROM salida
-- Orden cronologico real: FECHA_EMISION es texto DD/MM/YYYY; ordenarla como texto
-- rompe el orden cuando el rango cruza meses. Idem CP_NUMERO, que viene con anchos
-- distintos ("1" vs "00000017").
 ORDER BY _orden,
          to_date("FECHA_EMISION", 'DD/MM/YYYY'),
          "CP_TIPO",
          "CP_SERIE_O_COD_ADUANA",
          lpad("CP_NUMERO", 20, '0');

-- =====================================================================================
-- NOTAS
--
-- (A) Signos. En compras las lineas de producto van al debe, asi que se usa balance
--     directo (a diferencia del 14.1 de ventas, que usa -balance). Las notas de
--     credito de compra (in_refund) salen en negativo, como exige SUNAT, sin ningun
--     CASE por move_type.
--
-- (B) Las tres parejas de destino. Es el corazon del 8.1 y lo que mas se equivoca:
--       cols 11-12  BI + IGV destinadas EXCLUSIVAMENTE a gravadas y/o exportacion
--       cols 13-14  BI + IGV destinadas a gravadas y/o exportacion Y a no gravadas
--       cols 15-16  BI + IGV destinadas EXCLUSIVAMENTE a no gravadas
--     Se resuelven con los grupos de impuesto que ya trae l10n_pe: 'IGV',
--     'IGV GyNG' e 'IGV NG' respectivamente. El destino lo define el impuesto que
--     el usuario elige en la linea de la factura: si siempre usa "VAT 18" todo cae
--     en la primera pareja y el prorrateo del credito fiscal queda mal.
--
-- (C) Adquisiciones no gravadas (col 17). Agrupa EXO + INA + EXP. Tambien recibe las
--     lineas cuyo unico impuesto es RET (retencion de 4ta categoria): un recibo por
--     honorarios es inafecto al IGV, asi que su valor pertenece a esta columna. Es
--     una inferencia sobre configuracion incompleta; si el cliente empieza a marcar
--     esos recibos con "0 Ina" la clasificacion sale sola y esta regla deja de
--     aplicar.
--
-- (D) Importe total. NO se toma de amount_total_signed de Odoo, sino de la suma de
--     las columnas del registro, que es la definicion de SUNAT (campo 23 del PLE
--     8.1: "suma de los campos 14 al 22"). La diferencia importa: en un recibo por
--     honorarios con retencion de 8 por ciento, Odoo guarda el neto a pagar
--     (1380.00) mientras que el importe del comprobante es 1500.00. La retencion
--     (RET) y la detraccion (DET) se excluyen de todas las columnas de importe por
--     la misma razon: se descuentan del pago, no forman parte del comprobante.
--
-- (E) _DIAG_BASE_SIN_IMPUESTO. Base de lineas de producto sin ningun impuesto
--     asignado, imposibles de clasificar en las tres parejas de destino. No es parte
--     del formato: es el control de que no se pierde plata en el camino. Si sale
--     distinto de cero, esos comprobantes estan mal configurados y el registro no
--     cuadra contra el balance.
--
-- (F) _DIAG_DIF_VS_ODOO. Diferencia entre el importe total del registro (mas lo no
--     clasificado) y el total del asiento en Odoo. Se suma amount_total_signed
--     porque en compras viene con signo invertido. Deberia ser 0.00 en cada fila;
--     lo esperable distinto de cero es el monto de la retencion en los recibos por
--     honorarios, por lo explicado en (D).
--
-- (G) Columnas sin dato en esta base. La BD o18_cms no tiene ningun campo de
--     detraccion (se verifico information_schema: no existe ninguna columna
--     detrac/spot/constancia), ni campo para el comprobante de sujeto no
--     domiciliado. Por eso salen siempre vacias:
--       col 21  CP_SUJETO_NO_DOMICILIADO  (utilizacion de servicios del exterior)
--       col 22  DETRACCION_NUMERO
--       col 23  DETRACCION_FECHA
--     El llenado de 22 y 23 es optativo solo si existe un sistema de enlace que
--     mantenga esa informacion y permita identificar los comprobantes; si el cliente
--     tiene operaciones sujetas a detraccion hay que agregar los campos al modelo.
--
-- (H) Ano de emision de la DUA o DSI (col 6). Se llena solo para tipos de
--     comprobante 50/52/53/54, tomando el ano de la fecha de emision. En o18_cms no
--     hay importaciones registradas, asi que sale vacia.
--
-- (I) Serie y numero. Se obtienen de account_move.name separando por '-'. Antes del
--     split se quita el prefijo del tipo de documento que Odoo antepone al nombre
--     ("F F100-00851582" -> "F100-00851582"), porque si no el prefijo quedaria
--     dentro de la serie ("F F100"). Los nombres sin prefijo ("E001-109") pasan
--     intactos. Si el comprobante no tiene '-', la serie queda vacia y todo el texto
--     va al numero.
--
-- (J) Alcance. Solo in_invoice / in_refund en estado posted, filtrados por
--     invoice_date (fecha de emision del comprobante del proveedor).
--
-- (K) Columna 1: NUMERO CORRELATIVO. El encabezado oficial es "NUMERO CORRELATIVO
--     DEL REGISTRO **O** CODIGO UNICO DE LA OPERACION": admite cualquiera de los
--     dos. Como el modulo l10n_pe_voucher todavia no esta en produccion en esta
--     base, no hay CUO disponible y se usa la primera opcion: un correlativo
--     generado con ROW_NUMBER() en el mismo orden en que se imprime el registro
--     (fecha de emision, tipo, serie, numero).
--
--     Consecuencia importante: este correlativo NO es estable. Se recalcula en cada
--     ejecucion, asi que si se agrega, anula o corrige un comprobante del periodo,
--     los numeros de las filas posteriores se corren. Sirve para el reporte impreso
--     del 8.1/14.1; NO sirve como llave del PLE ni del SIRE, donde el campo debe ser
--     unico y persistente por operacion. Cuando l10n_pe_voucher entre en produccion
--     hay que reemplazar esta expresion por el CUO del voucher.
--
-- (L) Filtro por diario. Solo entran comprobantes de diarios con
--     l10n_latam_use_documents = TRUE. En compras, o18_cms tiene los tres diarios
--     con el flag en TRUE, asi que el filtro no excluye nada hoy: es una proteccion
--     para que un diario auxiliar futuro no se cuele en el registro. En ventas si
--     excluye datos, ver la nota (E) del archivo del formato 14.1.
--
-- (M) Compatibilidad con OCA sql_export. El modulo llama a
--     cr.mogrify(query, variable_dict). psycopg2 recorre TODO el string buscando
--     el caracter porcentaje. Solo acepta dos formas: duplicado (porcentaje dos
--     veces) para un literal, o seguido de (nombre)s para un parametro con nombre.
--     Cualquier otra aparicion la toma como parametro posicional y, como recibe un
--     dict, aborta con "TypeError: dict is not a sequence". Esto aplica tambien
--     dentro de comentarios SQL, porque la sustitucion ocurre antes de que
--     PostgreSQL vea el texto. Por eso este archivo no lo usa en ningun lado: se
--     emplea strpos(campo, '-') > 0 en vez de LIKE, y los comentarios estan escritos
--     nombrando el simbolo en vez de imprimirlo. Si algun dia se agrega un LIKE, el
--     comodin va duplicado.
--
-- (N) Tipo de documento de identidad del proveedor. Sale de
--     l10n_latam_identification_type.l10n_pe_vat_code, que es el campo que trae el
--     modulo l10n_pe y contiene los codigos de la tabla 2 de SUNAT (1 = DNI,
--     4 = carnet de extranjeria, 6 = RUC, 7 = pasaporte, A..H el resto). NO existe
--     un campo l10n_pe_code en ese modelo; el unico l10n_pe_code de la base esta en
--     res.city y corresponde al ubigeo, que es otra cosa.
-- =====================================================================================
