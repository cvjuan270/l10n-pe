"""Manual end-to-end check for l10n_pe_voucher: purchase -> receipt -> bill -> payment.

Run (does NOT commit, leaves the DB clean):

    python odoo/odoo-bin shell -c odoo-pe.conf -d o18_pe --no-http \
        < dev/l10n-pe/docs/general/test_voucher_purchase_flow.py

Expected: the inventory valuation move, the vendor bill and the payment all end
up on the SAME voucher (origin = the purchase order).
"""

from odoo import fields

env = env(user=1)
company = env.company
env = env(context=dict(env.context, allowed_company_ids=[company.id]))
Account = env["account.account"]


def pick(types, limit=1):
    return Account.search(
        [("company_ids", "in", company.id), ("account_type", "in", types)], limit=limit
    )


def check(label, condition):
    print(("PASS" if condition else "FAIL"), "-", label)
    return condition


# --- Setup: accounts, real-time valuation category, storable product, vendor ---
assets = pick(["asset_current"], limit=3)
val_acc = assets[0]
in_acc = assets[1] if len(assets) > 1 else pick(["asset_non_current"])
out_acc = pick(["expense", "expense_direct_cost"])
stock_journal = env["account.journal"].search(
    [("type", "=", "general"), ("company_id", "=", company.id)], limit=1
)

categ = env["product.category"].create(
    {
        "name": "Voucher Test",
        "property_cost_method": "standard",
        "property_valuation": "real_time",
        "property_stock_account_input_categ_id": in_acc.id,
        "property_stock_account_output_categ_id": out_acc.id,
        "property_stock_valuation_account_id": val_acc.id,
        "property_stock_journal": stock_journal.id,
    }
)

product = env["product.product"].create(
    {
        "name": "Voucher Product",
        "type": "consu",
        "is_storable": True,
        "categ_id": categ.id,
        "standard_price": 50.0,
        "purchase_method": "receive",
        "supplier_taxes_id": [(6, 0, [])],
    }
)

vendor = env["res.partner"].create({"name": "Voucher Vendor", "company_type": "company"})

# --- 1) Purchase order ---
po = env["purchase.order"].create(
    {
        "partner_id": vendor.id,
        "order_line": [
            (0, 0, {
                "product_id": product.id,
                "product_qty": 10.0,
                "price_unit": 50.0,
                "name": product.name,
                "taxes_id": [(6, 0, [])],
            })
        ],
    }
)
po.button_confirm()
print("PO:", po.name, "state:", po.state)

# --- 2) Receipt -> inventory valuation move ---
picking = po.picking_ids
picking.move_ids.write({"quantity": 10.0, "picked": True})
picking._action_done()
print("Picking:", picking.name, "state:", picking.state)

val_move = picking.move_ids.account_move_ids.filtered(lambda m: m.state == "posted")
val_voucher = val_move.line_ids.l10n_pe_voucher_id
print("Valuation move:", val_move.mapped("name"))
print("  voucher:", val_voucher.name, "| origin:",
      val_voucher.l10n_pe_origin_model, val_voucher.l10n_pe_origin_res_id)
check("valuation voucher origin is the PO",
      val_voucher.l10n_pe_origin_model == "purchase.order"
      and val_voucher.l10n_pe_origin_res_id == po.id)

# --- 3) Vendor bill ---
po.action_create_invoice()
bill = po.invoice_ids
bill.invoice_date = fields.Date.context_today(bill)
bill.action_post()
bill_product_lines = bill.line_ids.filtered(lambda l: l.purchase_line_id)
bill_voucher = bill_product_lines.l10n_pe_voucher_id
print("Bill:", bill.name, "state:", bill.state)
print("  product-line voucher(s):", bill_voucher.mapped("name"))
check("bill product line shares the valuation voucher",
      bill_voucher == val_voucher and len(bill_voucher) == 1)
check("all bill lines on a single voucher",
      len(bill.line_ids.l10n_pe_voucher_id) == 1)

# --- 4) Payment (should inherit the bill voucher on reconcile) ---
wizard = (
    env["account.payment.register"]
    .with_context(active_model="account.move", active_ids=bill.ids)
    .create({})
)
payments = wizard._create_payments()
pay_move = payments.move_id
pay_voucher = pay_move.line_ids.l10n_pe_voucher_id
print("Payment:", payments.name, "| move:", pay_move.name)
print("  voucher(s):", pay_voucher.mapped("name"))
check("payment inherits the bill voucher",
      pay_voucher == val_voucher and len(pay_voucher) == 1)

print("\nSUMMARY: PO", po.name,
      "| voucher", val_voucher.name,
      "| moves:", (val_move | bill | pay_move).mapped("name"))
print("Voucher.move_count:", val_voucher.move_count, "line_count:", val_voucher.line_count)

# No commit on purpose: roll back the whole scenario.
env.cr.rollback()
print("Rolled back (no data persisted).")
