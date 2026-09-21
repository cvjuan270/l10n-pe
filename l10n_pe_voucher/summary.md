# l10n_pe_voucher — Voucher logic for the Peruvian Journal Book

## Goal

Group journal items (`account.move.line`) by **voucher** (CUO — _Código Único de la
Operación_) so the Peruvian _Libro Diario_ can present every entry of the same business
operation together. Related entries — e.g. the inventory valuation move of a receipt and
the vendor bill of the same purchase — must share one voucher number.

**Scope of this step:** only the data model and the assignment logic on the accounting
entries. No report yet.

## Module split (bridge architecture)

- **`l10n_pe_voucher`** (this module, depends on `account`, `l10n_pe`): voucher model +
  sequence, the `account.move.line.l10n_pe_voucher_id` field, the `_post` hook, the
  resolution algorithm, the **fallback** (move itself) and the **payment** logic. The
  domain resolvers are empty extension points (`_l10n_pe_voucher_move_key` /
  `account.move.line._l10n_pe_voucher_line_key` return `None`).
- **`l10n_pe_voucher_sale_purchase`** (depends on `purchase_stock`, `sale_stock`):
  overrides the resolvers for vendor bills, customer invoices and inventory valuation
  moves (order-based grouping).
- **`l10n_pe_voucher_pos`** (depends on `point_of_sale`): overrides the resolver for POS
  entries. Rule: an **invoiced order** is grouped under its `pos.order` (invoice + that
  order's inventory valuation share one voucher); everything **not invoiced** is grouped
  under its `pos.session` (the session closing entry and the valuations of its
  non-invoiced orders). POS valuation moves are reached through
  `account.move.stock_move_id -> stock.picking.pos_order_id / pos_session_id` (POS does
  not use sale orders, so the sale/purchase bridge cannot resolve them).
- **`l10n_pe_voucher_reconcile`** (depends on `account`): resolves the voucher of
  payment (`origin_payment_id`) and bank/cash statement (`statement_line_id`) entries at
  **reconciliation** time instead of at posting.
- **`l10n_pe_voucher_analytic_target`** (depends on `l10n_pe_analytic_account_target`):
  the analytic destination entry inherits the voucher of the origin journal item it is
  derived from (`origin_move_line_id`), so the source operation and its destination
  entry share one CUO.

Bridges chain through `super()`, so each one only adds its own domain and the core keeps
working stand-alone (every entry still gets at least a fallback voucher).

### Deferred voucher assignment (reconciliation)

`account.move._l10n_pe_voucher_deferred()` (core: `False`) marks entries whose voucher
is decided after posting. The reconcile bridge returns `True` for payment and statement
entries and, on `account.move.line.reconcile()`, walks the invoice <-> payment <->
statement reconciliation graph:

- one real anchor voucher in the component -> every deferred move adopts it;
- several anchors (a payment settling unrelated operations) -> each keeps its own;
- no anchor (payment matched only with a statement) -> the component shares one new
  voucher.

Vouchers are **only created, never deleted**, so the gap-less correlative is preserved
(the previous create-fallback-then-delete approach skipped numbers and left orphan
vouchers for statement entries). Standalone deferred moves that are never reconciled get
an own voucher via `account.move._l10n_pe_backfill_deferred_vouchers()` (manual action
or the disabled-by-default monthly cron `ir_cron_backfill_deferred_vouchers`).

## Design decisions (agreed with the client)

- **Numbering:** global per-company correlative, no monthly reset. Backed by a gap-less
  `ir.sequence` (`l10n_pe.voucher`) created on demand per company.
- **Storage:** dedicated model `l10n.pe.voucher`; the line points to it through
  `account.move.line.l10n_pe_voucher_id` (Many2one). The mapping is **per line** so a
  consolidated move spanning several operations splits into several vouchers.
- **Payments:** a payment **shares** the voucher of the single invoice it settles
  (resolved at reconciliation time).

## How the link is resolved (`_post` → `_l10n_pe_assign_vouchers`)

Each posted move maps its lines to an _origin_ `(model, res_id)`. The voucher is
deduplicated by that origin, so related moves reuse the same voucher record/number.

Resolution order:

1. **Move-level**
   - Inventory valuation move → `account.move.stock_move_id` → `purchase_line_id` /
     `sale_line_id` → **purchase.order / sale.order**.
   - POS → **pos.order** (invoice) or **pos.session** (session entry).
2. **Line-level** (regular invoices/bills)
   - `purchase_line_id` → purchase.order
   - `sale_line_ids` (single order) → sale.order
3. **Fallback**
   - Lines with no own origin (taxes, payable/receivable, rounding) follow the move's
     single operation; if the move mixes several operations they fall back to the move
     itself (`account.move`, move.id).

A purchase receipt's valuation move and the vendor bill of the same PO therefore land on
the **same** voucher. A bill consolidating several POs splits its product lines per PO.

### Payments

Reconciliation runs after posting, so a payment first receives its own fallback voucher.
`account.move.line.reconcile()` is overridden: when the payment ends up matched against
exactly one counterpart voucher, every line of the payment entry is moved onto that
voucher and the empty fallback is removed. A payment settling invoices of several
vouchers keeps its own voucher.

## Coverage

- Purchases (receipt valuation + vendor bill) ✔
- Sales (delivery valuation/COGS + customer invoice) ✔
- POS (invoice / session entry) ✔
- Payments / collections (share invoice voucher) ✔
- Manual entries, adjustments, anything else → own voucher (guaranteed coverage)

Optional apps (purchase/sale/stock/pos) are detected at runtime via field/model checks;
the module depends only on `account` and `l10n_pe` and installs without them.

## Files

- `models/l10n_pe_voucher.py` — voucher model, sequence, get-or-create.
- `models/account_move.py` — `_post` hook + resolver chain.
- `models/account_move_line.py` — `l10n_pe_voucher_id` field + payment sync on
  reconcile.
- `views/*` — voucher list/form/search + menu, voucher column on journal items and the
  move form, group-by voucher on journal items.
- `security/ir.model.access.csv` — read for accountants, full for managers.

## Known edge cases / follow-ups

- Consolidated move across several operations: shared lines (tax/payable) fall on the
  move's own voucher. Revisit if the _Libro Diario_ needs them on a specific operation.
- POS ↔ stock valuation grouping is keyed by `pos.order`; deeper stock matching can be
  added if required.
- Voucher assignment happens at posting; existing posted moves get vouchers only if
  reposted or via a future backfill action (not built yet).
