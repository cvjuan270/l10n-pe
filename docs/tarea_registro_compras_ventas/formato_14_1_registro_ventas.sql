-- =====================================================================================
-- FORMATO 14.1 : "REGISTRO DE VENTAS E INGRESOS"  (layout impreso, 22 columnas)
-- RS 234-2006/SUNAT, Anexo 2
--
-- Base de datos : o18_cms   (Odoo 18 + l10n_pe)
--
-- Uso en pantalla:
--   PGPASSWORD=odoo18 psql -h localhost -U odoo18 -d o18_cms \
--     -f formato_14_1_registro_ventas.sql
--
-- Exportar a CSV para abrir en Excel (encabezados en la primera fila):
--   PGPASSWORD=odoo18 psql -h localhost -U odoo18 -d o18_cms \
--     --csv -P csv_fieldsep=';' -f formato_14_1_registro_ventas.sql \
--     > registro_ventas_14_1.csv
--   (en Excel: Datos > Desde texto/CSV, delimitador ';', codificacion UTF-8)
--
-- Ajustar los tres parametros del CTE "par" (empresa y rango de fechas).
-- Un solo statement: devuelve las 22 columnas oficiales + fila TOTALES.
-- La ultima columna (_DIAG_...) NO es parte del formato; es un control interno,
-- eliminarla al exportar. Ver nota (D) al pie.
--
-- IMPORTANTE: el query no debe contener NINGUN caracter porcentaje, ni siquiera
-- dentro de un comentario. El modulo OCA sql_export ejecuta cr.mogrify(query, dict)
-- y psycopg2 lo interpreta como marcador de posicion, fallando con
-- "TypeError: dict is not a sequence". Ver nota (I).
-- =====================================================================================

WITH par AS (
    SELECT 1::int             AS company_id,     -- <<< empresa (1 = CLINICA MALL SALUD, 2 = ISM CORPORATE)
           DATE '2026-05-01'  AS fecha_desde,    -- <<< inicio del periodo
           DATE '2026-06-30'  AS fecha_hasta     -- <<< fin del periodo
),

-- Comprobantes de venta del periodo -----------------------------------------------
-- Solo diarios con l10n_latam_use_documents = TRUE, es decir los que emiten
-- comprobantes con tipo de documento SUNAT. Ver nota (E).
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
      -- Ver nota (F).
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
       AND am.move_type IN ('out_invoice', 'out_refund')
       AND am.invoice_date BETWEEN par.fecha_desde AND par.fecha_hasta
       AND j.l10n_latam_use_documents = TRUE
),

-- Clasificacion de cada linea de producto por grupo de impuesto -------------------
-- Una linea puede tener varios impuestos (p.ej. IGV + ISC); se elige uno solo por
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
                   WHEN 'IGV'      THEN 1
                   WHEN 'IGV GyNG' THEN 2
                   WHEN 'IGV NG'   THEN 3
                   WHEN 'IVAP'     THEN 4
                   WHEN 'EXP'      THEN 5
                   WHEN 'GRA'      THEN 6
                   WHEN 'EXO'      THEN 7
                   WHEN 'INA'      THEN 8
                   ELSE 99
              END
),

-- Bases imponibles por bucket SUNAT ----------------------------------------------
base AS (
    SELECT move_id,
           SUM(CASE WHEN grupo = 'EXP'                                        THEN -balance ELSE 0 END) AS exportacion,
           SUM(CASE WHEN grupo IN ('IGV','IGV GyNG','IGV NG','GRA','IVAP')    THEN -balance ELSE 0 END) AS gravada,
           SUM(CASE WHEN grupo = 'EXO'                                        THEN -balance ELSE 0 END) AS exonerada,
           SUM(CASE WHEN grupo = 'INA'                                        THEN -balance ELSE 0 END) AS inafecta,
           SUM(CASE WHEN grupo IS NULL                                        THEN -balance ELSE 0 END) AS sin_clasificar
      FROM lin
     GROUP BY move_id
),

-- Impuestos desde las lineas de impuesto -----------------------------------------
imp AS (
    SELECT aml.move_id,
           SUM(CASE WHEN g.name->>'en_US' IN ('IGV','IGV GyNG','IGV NG')      THEN -aml.balance ELSE 0 END) AS igv,
           SUM(CASE WHEN g.name->>'en_US' = 'ISC'                             THEN -aml.balance ELSE 0 END) AS isc,
           SUM(CASE WHEN g.name->>'en_US' NOT IN
                        ('IGV','IGV GyNG','IGV NG','ISC')                     THEN -aml.balance ELSE 0 END) AS otros
      FROM account_move_line aml
      JOIN account_tax       t ON t.id = aml.tax_line_id
      JOIN account_tax_group g ON g.id = t.tax_group_id
     WHERE aml.move_id      IN (SELECT id FROM mov)
       AND aml.display_type = 'tax'
     GROUP BY aml.move_id
),

-- Una fila por comprobante --------------------------------------------------------
reg AS (
    SELECT
        1                                                                       AS _orden,
        -- Numero correlativo del registro, generado en el mismo orden en que se
        -- imprime el registro. Ver nota (H).
        to_char(ROW_NUMBER() OVER (ORDER BY m.invoice_date,
                                            m.tipo_cp,
                                            m.serie,
                                            lpad(m.numero, 20, '0')),
                'FM00000000')                                                   AS "NUM_CORRELATIVO",
        to_char(m.invoice_date,     'DD/MM/YYYY')                               AS "FECHA_EMISION",
        to_char(m.invoice_date_due, 'DD/MM/YYYY')                               AS "FECHA_VCTO_PAGO",
        m.tipo_cp                                                               AS "CP_TIPO",
        m.serie                                                                 AS "CP_SERIE",
        m.numero                                                                AS "CP_NUMERO",
        it.l10n_pe_vat_code                                                     AS "CLI_TIPO_DOC",
        p.vat                                                                   AS "CLI_NUM_DOC",
        p.name                                                                  AS "CLI_RAZON_SOCIAL",
        ROUND(COALESCE(b.exportacion,    0), 2)                                 AS "VALOR_FACT_EXPORTACION",
        ROUND(COALESCE(b.gravada,        0), 2)                                 AS "BASE_IMPONIBLE_GRAVADA",
        ROUND(COALESCE(b.exonerada,      0), 2)                                 AS "EXONERADA",
        ROUND(COALESCE(b.inafecta,       0), 2)                                 AS "INAFECTA",
        ROUND(COALESCE(i.isc,            0), 2)                                 AS "ISC",
        ROUND(COALESCE(i.igv,            0), 2)                                 AS "IGV_IPM",
        ROUND(COALESCE(i.otros,          0), 2)                                 AS "OTROS_TRIB_CARGOS",
        ROUND(m.amount_total_signed, 2)                                         AS "IMPORTE_TOTAL_CP",
        CASE WHEN m.currency_id <> m.moneda_empresa
                  AND COALESCE(m.invoice_currency_rate, 0) <> 0
             THEN ROUND(1 / m.invoice_currency_rate, 3) END                     AS "TIPO_CAMBIO",
        to_char(rm.invoice_date, 'DD/MM/YYYY')                                  AS "REF_FECHA",
        rdt.code                                                                AS "REF_TIPO",
        rd.serie                                                                AS "REF_SERIE",
        rd.numero                                                               AS "REF_NUMERO",
        ROUND(COALESCE(b.sin_clasificar, 0), 2)                                 AS "_DIAG_BASE_SIN_IMPUESTO"
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

-- Detalle + fila TOTALES ----------------------------------------------------------
salida AS (
    SELECT * FROM reg
    UNION ALL
    SELECT
        2, 'TOTALES', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
        SUM("VALOR_FACT_EXPORTACION"), SUM("BASE_IMPONIBLE_GRAVADA"), SUM("EXONERADA"),
        SUM("INAFECTA"), SUM("ISC"), SUM("IGV_IPM"), SUM("OTROS_TRIB_CARGOS"),
        SUM("IMPORTE_TOTAL_CP"), NULL, NULL, NULL, NULL, NULL,
        SUM("_DIAG_BASE_SIN_IMPUESTO")
      FROM reg
)

SELECT
    "NUM_CORRELATIVO", "FECHA_EMISION", "FECHA_VCTO_PAGO",
    "CP_TIPO", "CP_SERIE", "CP_NUMERO",
    "CLI_TIPO_DOC", "CLI_NUM_DOC", "CLI_RAZON_SOCIAL",
    "VALOR_FACT_EXPORTACION", "BASE_IMPONIBLE_GRAVADA",
    "EXONERADA", "INAFECTA", "ISC", "IGV_IPM", "OTROS_TRIB_CARGOS",
    "IMPORTE_TOTAL_CP", "TIPO_CAMBIO",
    "REF_FECHA", "REF_TIPO", "REF_SERIE", "REF_NUMERO",
    "_DIAG_BASE_SIN_IMPUESTO"
  FROM salida
-- Orden cronologico real: FECHA_EMISION es texto DD/MM/YYYY; ordenarla como texto
-- rompe el orden cuando el rango cruza meses. Idem CP_NUMERO, que viene con anchos
-- distintos ("1" vs "00000017").
 ORDER BY _orden,
          to_date("FECHA_EMISION", 'DD/MM/YYYY'),
          "CP_TIPO",
          "CP_SERIE",
          lpad("CP_NUMERO", 20, '0');

-- =====================================================================================
-- NOTAS
--
-- (A) Signos. Las notas de credito (out_refund) salen en negativo, tal como exige
--     SUNAT. Se logra con -balance sobre las lineas y con amount_total_signed en el
--     importe total; no se aplica ningun CASE por move_type.
--
-- (B) Moneda. Todos los importes salen en moneda de la empresa (PEN), que es lo que
--     pide el registro. La columna TIPO_CAMBIO solo se llena cuando el comprobante
--     se emitio en moneda distinta: es 1 / invoice_currency_rate, porque Odoo guarda
--     el factor empresa -> comprobante y SUNAT pide soles por unidad de moneda
--     extranjera. En o18_cms hoy todas las ventas son PEN, asi que sale vacia.
--
-- (C) IVAP. El layout impreso del 14.1 no tiene columnas de IVAP (el TXT del PLE si,
--     campos 21 y 22). La base IVAP se acumula en BASE_IMPONIBLE_GRAVADA y el
--     impuesto en OTROS_TRIB_CARGOS. Si el cliente vende arroz pilado hay que
--     separarlos.
--
-- (D) _DIAG_BASE_SIN_IMPUESTO. Base de lineas de producto que no tienen ningun
--     impuesto asignado, por lo que no se pueden clasificar en gravada / exonerada /
--     inafecta / exportacion. No es parte del formato: es el control de que no se
--     pierde plata en el camino. Si sale distinto de cero, esos comprobantes estan
--     mal configurados y el registro no cuadra.
--
-- (E) Filtro por diario. Solo entran comprobantes de diarios con
--     l10n_latam_use_documents = TRUE, que son los que emiten con tipo de documento
--     SUNAT. Es el filtro correcto para el registro, pero deja fuera ventas reales
--     si algun diario esta mal configurado: en o18_cms excluye 1045 comprobantes por
--     S/ 374,379.53 del diario "Tickets de cliente - ISM" (company_id = 2), que
--     tiene el flag en FALSE y por eso ninguno de sus comprobantes tiene tipo de
--     documento. Esas ventas existieron y tienen que aparecer en algun registro:
--     hay que decidir si ese diario se corrige o si esas operaciones se resumen por
--     otra via. Con el filtro activo, company_id = 2 no tiene ventas registrables.
--
-- (F) Serie y numero. Se obtienen de account_move.name separando por '-'. Antes del
--     split se quita el prefijo del tipo de documento que Odoo antepone al nombre
--     ("F E001-1" -> "E001-1"), porque si no el prefijo quedaria dentro de la serie
--     ("F E001"). Los nombres sin prefijo ("B001-00000467") pasan intactos. Si el
--     comprobante no tiene '-', la serie queda vacia y todo el texto va al numero.
--
-- (G) Alcance. Solo out_invoice / out_refund en estado posted. No incluye notas de
--     debito emitidas como asiento aparte si no usan debit_origin_id, ni ordenes de
--     POS que no generaron factura.
--
-- (H) Columna 1: NUMERO CORRELATIVO. El encabezado oficial es "NUMERO CORRELATIVO
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
-- (I) Compatibilidad con OCA sql_export. El modulo llama a
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
-- (J) Tipo de documento de identidad del cliente. Sale de
--     l10n_latam_identification_type.l10n_pe_vat_code, que es el campo que trae el
--     modulo l10n_pe y contiene los codigos de la tabla 2 de SUNAT (1 = DNI,
--     4 = carnet de extranjeria, 6 = RUC, 7 = pasaporte, A..H el resto). NO existe
--     un campo l10n_pe_code en ese modelo; el unico l10n_pe_code de la base esta en
--     res.city y corresponde al ubigeo, que es otra cosa.
-- =====================================================================================
