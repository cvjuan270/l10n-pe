import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    account_target_id = fields.Many2one(
        "account.move",
        string="Asiento contable Destino",
        readonly=True,
        copy=False,
    )

    def unlink(self):
        for rec in self:
            if rec.account_target_id:
                rec.account_target_id.button_draft()
                rec.account_target_id.button_cancel()
        return super().unlink()

    def action_create_destination_move(self):
        self.ensure_one()
        move_data = self._prepare_destination_move()
        if move_data:
            self._create_and_post_move(move_data)

    def _get_target_analytic_account(self):
        """Cuenta analítica con asiento destino configurado.

        Se obtiene desde ``analytic_distribution`` (fuente real) en lugar de
        ``account_id``, porque en Odoo 18 la cuenta puede vivir en cualquier
        columna de plan (``account_id`` o ``x_planN_id``) según el plan al
        que pertenezca. ``analytic_distribution`` la contiene siempre.
        """
        self.ensure_one()
        account_ids = []
        for key in self.analytic_distribution or {}:
            account_ids += [int(i) for i in str(key).split(",")]
        accounts = (
            self.env["account.analytic.account"].browse(set(account_ids)).exists()
        )
        return accounts.filtered("account_entry_target")[:1]

    def _prepare_destination_move(self):
        self.ensure_one()
        analytic_account = self._get_target_analytic_account()
        if (
            not analytic_account
            or self.category not in ("vendor_bill", "other")
            or self.account_target_id
        ):
            return False
        debit_account = analytic_account.acccount_debit_target
        credit_account = analytic_account.acccount_credit_target
        company = self.company_id or self.env.company
        journal = company.sudo().analytic_account_journal_target_id
        if not debit_account or not credit_account:
            raise UserError(
                _(
                    "Debe configurar las cuentas de destino de débito y "
                    "crédito en la cuenta analítica: %s.",
                    analytic_account.name,
                )
            )
        if not journal:
            raise UserError(
                _(
                    "Debe configurar el diario de destino en la configuración "
                    "del sistema para la compañía: %s.",
                    company.name,
                )
            )

        # Resolución de moneda y tasa con fallback robusto.
        currency = self.move_line_id.currency_id or company.currency_id
        rate = self.move_line_id.currency_rate or 1.0

        # Manejo de signo: trabajamos con la magnitud del importe.
        # Caso normal (gasto, amount < 0): DEBE = débito, HABER = crédito.
        # Caso inverso (amount > 0, p.ej. nota de crédito de proveedor /
        # devolución): se invierte el asiento intercambiando las cuentas.
        if self.amount > 0:
            debit_account, credit_account = credit_account, debit_account
        amount = abs(self.amount)
        amount_currency = currency.round(amount * rate)

        move_data = {
            "origin_move_id": self.move_line_id.move_id.id,
            "origin_move_line_id": self.move_line_id.id,
            "origin_analytic_line_id": self.id,
            "ref": self.move_line_id.display_name or self.name,
            "date": self.date,
            "journal_id": journal.id,
            "company_id": company.id,
            "currency_id": currency.id,
            "move_type": "entry",
        }
        line_data = {
            "origin_move_id": self.move_line_id.move_id.id,
            "origin_move_line_id": self.move_line_id.id,
            "name": self.move_line_id.display_name or self.name,
            "ref": self.ref or "",
            "partner_id": self.partner_id.id,
            "currency_id": currency.id,
        }
        debit_data = dict(line_data)
        credit_data = dict(line_data)
        debit_data.update(
            account_id=debit_account.id,
            debit=amount,
            credit=False,
            amount_currency=amount_currency,
            currency_id=currency.id,
        )
        credit_data.update(
            account_id=credit_account.id,
            debit=False,
            credit=amount,
            amount_currency=-amount_currency,
            currency_id=currency.id,
        )

        move_data["line_ids"] = [(0, 0, debit_data), (0, 0, credit_data)]
        return move_data

    def _create_and_post_move(self, move_data):
        account_target = self.env["account.move"].create(move_data)
        # Limpiamos la distribución analítica de las líneas del asiento destino
        # para evitar que genere nuevas líneas analíticas reprocesables (mismo
        # comportamiento que el wizard).
        account_target.line_ids.write({"analytic_distribution": False})
        account_target.action_post()
        self.account_target_id = account_target.id
