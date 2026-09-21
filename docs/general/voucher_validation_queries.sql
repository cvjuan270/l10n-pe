-- =====================================================================
-- l10n_pe_voucher - Validation queries (DBeaver / psql)
-- DB: o18_pe   |   user: odoo18   |   host: localhost:5432
-- Tables: l10n_pe_voucher, account_move_line, account_move, account_account
-- Note (Odoo 18): account code lives in account_account.code_store (jsonb keyed
--   by company id) and account/partner names in jsonb -> use ->> 'en_US'.
-- =====================================================================


-- 1) VOUCHER SUMMARY -----------------------------------------------------
-- One row per voucher: how many entries/lines it groups, totals and balance.
-- "asientos" lists the journal entries sharing the voucher.
SELECT v.id,
       v.name                              AS voucher,
       v.l10n_pe_origin_model              AS origin_model,
       v.l10n_pe_origin_res_id             AS origin_id,
       v.date,
       COUNT(DISTINCT l.move_id)           AS num_entries,
       COUNT(l.id)                         AS num_lines,
       ROUND(SUM(l.debit), 2)              AS total_debit,
       ROUND(SUM(l.credit), 2)             AS total_credit,
       ROUND(SUM(l.balance), 2)            AS balance,
       STRING_AGG(DISTINCT m.name, ', ' ORDER BY m.name) AS entries
FROM l10n_pe_voucher v
JOIN account_move_line l ON l.l10n_pe_voucher_id = v.id
JOIN account_move m      ON m.id = l.move_id
GROUP BY v.id, v.name, v.l10n_pe_origin_model, v.l10n_pe_origin_res_id, v.date
ORDER BY v.id DESC;


-- 2) VOUCHER DETAIL (journal-book style) ---------------------------------
-- All journal items of a voucher, grouped by entry. Replace the voucher name.
SELECT v.name                                  AS voucher,
       m.name                                  AS entry,
       m.move_type,
       m.origin_payment_id IS NOT NULL         AS is_payment,
       l.date,
       a.code_store ->> l.company_id::text      AS account_code,
       a.name ->> 'en_US'                       AS account_name,
       p.name                                   AS partner,
       l.name                                   AS label,
       ROUND(l.debit, 2)                        AS debit,
       ROUND(l.credit, 2)                       AS credit
FROM account_move_line l
JOIN l10n_pe_voucher v   ON v.id = l.l10n_pe_voucher_id
JOIN account_move m      ON m.id = l.move_id
JOIN account_account a   ON a.id = l.account_id
LEFT JOIN res_partner p  ON p.id = l.partner_id
WHERE v.name = '00000001'          -- <-- change voucher number
ORDER BY m.name, l.id;


-- 3) PURCHASE GROUPING CHECK ---------------------------------------------
-- For a purchase order, the valuation move + vendor bill (+ payment) must
-- all share ONE voucher. Replace the purchase order id.
SELECT v.name                                   AS voucher,
       COUNT(DISTINCT m.id)                      AS entries,
       STRING_AGG(DISTINCT m.name || ' [' || m.move_type || ']', ', ') AS detail
FROM l10n_pe_voucher v
JOIN account_move_line l ON l.l10n_pe_voucher_id = v.id
JOIN account_move m      ON m.id = l.move_id
WHERE v.l10n_pe_origin_model = 'purchase.order'
  AND v.l10n_pe_origin_res_id = 1   -- <-- change purchase.order id
GROUP BY v.name;


-- 4) ANOMALY: posted lines WITHOUT a voucher -----------------------------
-- Should be empty for entries posted AFTER the module was installed.
-- Rows here are usually the historical backlog (posted before install).
SELECT m.name                              AS entry,
       m.move_type,
       m.date,
       COUNT(l.id)                         AS lines_without_voucher
FROM account_move_line l
JOIN account_move m ON m.id = l.move_id
WHERE m.state = 'posted'
  AND l.l10n_pe_voucher_id IS NULL
  AND l.display_type IS NULL          -- ignore section/note lines
GROUP BY m.id, m.name, m.move_type, m.date
ORDER BY m.date DESC;


-- 5) INFO: entries split across several vouchers -------------------------
-- Expected ONLY for consolidated moves (e.g. one bill covering several POs).
-- A regular invoice/bill must return a single voucher (not appear here).
SELECT m.name                                  AS entry,
       m.move_type,
       COUNT(DISTINCT l.l10n_pe_voucher_id)    AS num_vouchers,
       STRING_AGG(DISTINCT v.name, ', ')       AS vouchers
FROM account_move_line l
JOIN account_move m     ON m.id = l.move_id
JOIN l10n_pe_voucher v  ON v.id = l.l10n_pe_voucher_id
GROUP BY m.id, m.name, m.move_type
HAVING COUNT(DISTINCT l.l10n_pe_voucher_id) > 1
ORDER BY num_vouchers DESC;


-- 6) PAYMENT SHARES THE INVOICE VOUCHER ----------------------------------
-- Vouchers that group both a payment entry and a non-payment entry: confirms
-- the payment inherited the invoice voucher.
SELECT v.name                                                       AS voucher,
       BOOL_OR(m.origin_payment_id IS NOT NULL)                     AS has_payment,
       BOOL_OR(m.origin_payment_id IS NULL AND m.move_type <> 'entry') AS has_invoice,
       STRING_AGG(DISTINCT m.name || ' [' || m.move_type || ']', ', ') AS entries
FROM l10n_pe_voucher v
JOIN account_move_line l ON l.l10n_pe_voucher_id = v.id
JOIN account_move m      ON m.id = l.move_id
GROUP BY v.id, v.name
HAVING BOOL_OR(m.origin_payment_id IS NOT NULL)
ORDER BY v.id DESC;
