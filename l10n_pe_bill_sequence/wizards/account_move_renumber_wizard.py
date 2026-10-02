from datetime import date

from odoo import _, api, exceptions, fields, models


class AccountMoveRenumberWizard(models.TransientModel):
    _name = "account.move.renumber.wizard"
    _description = "Account move entry renumbering wizard"

    starting_date = fields.Date(
        string='Fecha de inicio',
        required=True,
        default=lambda self: self._default_starting_date(),
        help="Resecuencias Número de Asiento (compras) iniciando este día.",
    )
    available_sequence_ids = fields.Many2many(
        comodel_name="ir.sequence",
        string="Secuencias disponibles",
        default=lambda self: self._default_available_sequence_ids(),
    )
    sequence_id = fields.Many2one(
        comodel_name="ir.sequence",
        string="Secuencia",
        required=True,
        default=lambda self: self._default_entry_number_sequence(),
        domain="[('id', 'in', available_sequence_ids)]",
        help="Secuencia a utilizar para la renumeración. Afecta a todas las revistas que utilizan esta secuencia."
    )

    @api.model
    def _default_starting_date(self):
        """Start by default on day 1 of current year."""
        return date(date.today().year, 1, 1)

    @api.model
    def _default_entry_number_sequence(self):
        """Get default sequence if it exists."""
        return self.env["ir.sequence"].search(
            [
                "&",
                ("code", "=", "account_journal_general_sequence.default"),
                ("company_id", "in", self.env.companies.ids),
            ]
        )

    @api.model
    def _default_available_sequence_ids(self):
        """Let view display only journal-related sequences."""
        return (
            self.env["account.journal"]
            .search([("company_id", "in", self.env.companies.ids)])
            .mapped("entry_number_sequence_id")
        )

    def action_renumber(self):
        """Renumber moves.

        Makes sure moves exist. Sorts them. Resets sequences. Renumbers them.
        """
        # Find posted moves that match wizard criteria
        moves = self.env["account.move"].search(
            [
                ("state", "=", "posted"),
                ("date", ">=", self.starting_date),
                ("journal_id.entry_number_sequence_id", "=", self.sequence_id.id),
            ],
            order="date, id",
        )
        if not moves:
            raise exceptions.UserError("No hay ninguna cuenta contable")
        moves = moves.with_context(skip_invoice_sync=True)
        moves.entry_number = False
        moves.flush_recordset(["entry_number"])
        moves._compute_entry_number()
