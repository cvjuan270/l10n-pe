import logging

from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

ADDON = 'l10n_pe_bill_sequence'


class AccountMove(models.Model):
    _inherit = 'account.move'

    _sql_constraints = [
            (
                "entry_number_unique",
                "UNIQUE(entry_number, journal_id)",
                "Entry number must be unique per journal.",
            ),
        ]

    entry_number = fields.Char(
        index=True,
        readonly=True,
        store=True,
        compute="_compute_entry_number",
        string='Número de asiento',
        help="Numeración automática, basada en la configuración del Diario (formato YY-MM-NNNN)",
    )

    @api.depends("state")
    def _compute_entry_number(self):
        # Omitir durante la instalación del módulo, por razones de rendimiento
        if self.env.context.get("module") == ADDON:
            module = self.env["ir.module.module"].search([("name", "=", ADDON)])
            if module.state == "to install":
                _logger.info(
                    "Omitiendo generación de números de asiento durante la instalación para %s.",
                    self,
                )
                return

         # """Asignar un número de asiento al publicar."""
        canceled = self.filtered_domain(
            [("state", "=", "cancel"), ("entry_number", "!=", False)]
        )
        canceled.entry_number = False
        if canceled:
            _logger.warning(
                "Se eliminó entry_number para %r después de cancelación. "
                "Esto podría crear huecos en las secuencias.",
                canceled,
            )

        # Seleccionar asientos que necesitan número
        chosen = self.filtered_domain([
            ("state", "=", "posted"),
            ("entry_number", "=", False),
                ("journal_id.type", "=", "purchase"),
                ("journal_id.l10n_latam_use_documents", "=", True),
                ("journal_id.entry_number_sequence_id", "!=", False)
            ])

            # Verificar que todos los asientos seleccionados tengan fecha contable
        for move in chosen:
            if not move.date:
                raise UserError("El asiento %s debe tener una fecha contable definida para asignar un número de secuencia" % move.name)

        # Almacenar en caché todos los nuevos números
        chosen_map = {}
        for move in chosen.sorted(lambda one: (one.date, one.name, one.id)):
            chosen_map[move.id] = self._get_next_sequence_number(move)

        # Escribir todos los nuevos números en los asientos elegidos
        for move_id, new_number in chosen_map.items():
            self.browse(move_id).entry_number = new_number

        if chosen:
            _logger.info("Añadido número de asiento a %d asientos contables", len(chosen))
            _logger.debug("Añadido número de asiento a %r", chosen)

    def _get_next_sequence_number(self, move):
        """Obtener el siguiente número de secuencia con formato YY-MM-NNNN.

        Nota: La secuencia se basa SIEMPRE en la fecha contable del asiento,
        no en la fecha actual del sistema.
        """
        if not move.date:
            raise UserError("El asiento debe tener una fecha contable definida para asignar un número de secuencia")

        if not move.journal_id.entry_number_sequence_id:
            raise UserError("El diario %s no tiene configurada una secuencia para numeración de asientos" % move.journal_id.name)

        # Obtener la secuencia del diario
        sequence = move.journal_id.entry_number_sequence_id

        date_obj = fields.Date.from_string(move.date)
        date_range = self._ensure_date_range_exists(sequence, date_obj)
        number = sequence._next(sequence_date=move.date)
        return number

    def _ensure_date_range_exists(self, sequence, date_obj):
        """Asegurar que existe un rango de fecha para el mes y año indicados."""
        # Formato para construir los rangos de fecha: Primer y último día del mes
        year = date_obj.year
        month = date_obj.month

        # Calcular primer día del mes
        first_day = fields.Date.to_string(datetime(year, month, 1))

        # Calcular último día del mes (usando el primer día del mes siguiente y restando un día)
        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)

        last_day = fields.Date.to_string(next_month - timedelta(days=1))

        # Buscar si ya existe un rango para este mes y año
        date_range = self.env['ir.sequence.date_range'].search([
            ('sequence_id', '=', sequence.id),
            ('date_from', '=', first_day),
            ('date_to', '=', last_day)
        ], limit=1)

        # Si no existe, crear el rango
        if not date_range:
            _logger.info(f"Creando rango de fecha para {year}-{month:02d}")
            date_range = self.env['ir.sequence.date_range'].create({
                'sequence_id': sequence.id,
                'date_from': first_day,
                'date_to': last_day,
            })

        return date_range


    def button_draft(self):
        """Prevenir cambio a borrador para asientos con número asignado."""
        for record in self:
            if record.entry_number and record.journal_id.type == 'purchase' and record.journal_id.l10n_latam_use_documents:
                raise UserError('No puede revertir a borrador un documento que ya tiene asignado un número: %s' % record.entry_number)
        return super(AccountMove, self).button_draft()

    def unlink(self):
        """Prevenir eliminación de documentos con número de seguimiento."""
        for record in self:
            if record.entry_number and record.journal_id.type == 'purchase' and record.journal_id.l10n_latam_use_documents:
                raise UserError('No puede eliminar un documento que ya tiene asignado un número: %s' % record.entry_number)
        return super(AccountMove, self).unlink()

