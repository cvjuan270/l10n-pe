from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)

class Account_journal(models.Model):

    _inherit = 'account.journal'

    entry_number_sequence_id = fields.Many2one(
        comodel_name="ir.sequence",
        string="Secuencia de numeración de asientos",
        compute="_compute_entry_number_sequence",
        domain="[('company_id', '=', company_id)]",
        check_company=True,
        readonly=False,
        store=True,
        copy=False,
        help="Secuencia utilizada para la numeración de asientos contables.",
    )
    entry_number_sequence_id_name = fields.Char(related="entry_number_sequence_id.code")

    @api.depends("company_id")
    def _compute_entry_number_sequence(self):
        for journal in self:
            # Solo aplicar a diarios de compra con documentos latinoamericanos
            if journal.type == 'purchase' and journal.l10n_latam_use_documents:

                # Buscar una secuencia existente para este diario
                sequence = self.env["ir.sequence"].search([
                    ("code", "=","account_journal_general_sequence.default" ),
                    ("company_id", "=", journal.company_id.id),
                ], limit=1)

                if not sequence:
                    _logger.info(f"Creando secuencia con date_range para el diario {journal.company_id.name}")
                    sequence = self.env["ir.sequence"].create({
                        "name": _(f"Secuencia de asientos para {journal.company_id.name}"),
                        "code":  "account_journal_general_sequence.default",
                        "company_id": journal.company_id.id,
                        "implementation": "no_gap",  # Sin huecos
                        "padding": 4,  # 4 dígitos para el correlativo
                        "prefix": "%(range_y)s-%(range_month)s-",  # Formato YY-MM-
                        "use_date_range": True,  # Usar rangos de fecha
                    })

                journal.entry_number_sequence_id = sequence
            else:
                journal.entry_number_sequence_id = False

