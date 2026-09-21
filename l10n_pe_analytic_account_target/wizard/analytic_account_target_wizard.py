import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AnalyticAccountTargetWizard(models.TransientModel):
    _name = "analytic.account.target.wizard"
    _description = "Asistente de Asientos de Destino para Apuntes Analíticos"

    start_date = fields.Date("Fecha de Inicio", required=True)
    end_date = fields.Date("Fecha Fin", required=True)

    def get_accont_analytic_lines(self):
        domain = [
            ("date", ">=", self.start_date),
            ("date", "<=", self.end_date),
            ("category", "in", ["vendor_bill", "other"]),
            ("company_id", "=", self.env.company.id),
        ]
        batch_size = 10
        record_count = self.env["account.analytic.line"].search_count(domain)
        for offset in range(0, record_count, batch_size):
            analytic_lines = self.env["account.analytic.line"].search(
                domain, limit=batch_size, offset=offset
            )
            moves_to_create = []
            for line in analytic_lines:
                move_vals = line._prepare_destination_move()
                if move_vals:
                    moves_to_create.append(move_vals)
            if moves_to_create:
                created_moves = self.env["account.move"].create(moves_to_create)
                for c_move in created_moves:
                    c_move.line_ids.write({"analytic_distribution": False})
                    analytic_lines.browse(c_move.origin_analytic_line_id.id).write(
                        {"account_target_id": c_move.id}
                    )

                created_moves.action_post()
                _logger.info(
                    "Lote procesado: Líneas analíticas procesadas: %d"
                    " - Movimientos creados (%d): %s",
                    len(analytic_lines),
                    len(created_moves),
                    ", ".join(m.name for m in created_moves),
                )

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for record in self:
            if record.start_date > record.end_date:
                raise ValidationError(
                    _("La fecha de inicio no puede ser mayor a la fecha fin")
                )
            if (record.end_date - record.start_date).days > 31:
                raise ValidationError(
                    _("El rango de fechas no puede ser mayor a 31 días")
                )
