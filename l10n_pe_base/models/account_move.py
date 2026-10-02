import odoo
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_pe_period_id = fields.Many2one(
        "l10n_pe.account.period",
        string="Periodo Contable",
        domain="[('date_start','<=',date), ('date_end', '>=', date)]",
        compute="_compute_l10n_pe_period",
        store=True,
        readonly=False,
    )

    @api.depends("date", "invoice_date")
    def _compute_l10n_pe_period(self):
        for move in self:
            date = move.invoice_date if move.move_type in ["out_invoice", "out_refund"] else move.date
            move.l10n_pe_period_id = self._get_l10n_pe_period(date)

    def _validate_account_period(self, move):
        if move.l10n_pe_period_id.close:
            raise ValidationError("El asiento contable %s esta en un periodo contable Cerrado" % (move.name))
        return True

    def button_draft(self):
        for move in self:
            if self._validate_account_period(move):
                return super().button_draft()

    def action_post(self):
        for move in self:
            if self._validate_account_period(move):
                return super().action_post()

    def _get_l10n_pe_period(self, date):
        period = self.env["l10n_pe.account.period"].search(
            [
                ("date_start", "<=", date),
                ("date_end", ">=", date),
                ("code", "not like", "%00"),
                ("code", "not like", "%13"),
            ],
            limit=1,
        )
        return period

    @api.model_create_multi
    def create(self, vals_list):
        """
        Para facturas de cliente y notas de crédito de cliente (`out_invoice`, `out_refund`),
        se utiliza la fecha de la factura (`invoice_date`) como referencia.
        Para otros tipos de movimientos, se utiliza la fecha del asiento (`date`).
        """
        for vals in vals_list:
            move_type = vals.get("move_type")
            invoice_date = vals.get("invoice_date")
            date = vals.get("date")
            if move_type in ["out_invoice", "out_refund"]:
                date_ref = invoice_date or date
            else:
                date_ref = date or invoice_date
            period = self._get_l10n_pe_period(date_ref)
            if period:
                vals["l10n_pe_period_id"] = period.id
        return super().create(vals_list)
