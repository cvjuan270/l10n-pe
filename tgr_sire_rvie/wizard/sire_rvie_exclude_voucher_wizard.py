"""Exclusión definitiva de un comprobante de la propuesta RVIE
(``DELETE .../retiracomprobante?codCar=...&codSituacion=0``).

**Irreversible** -- ver plan aprobado, seccion B: por eso exige un checkbox
de confirmación explícita y está restringido a
``account.group_account_manager`` (ver ``security/ir.model.access.csv``).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SireRvieExcludeVoucherWizard(models.TransientModel):
    _name = "sire.rvie.exclude.voucher.wizard"
    _description = "SIRE RVIE - Excluir comprobante (irreversible)"
    _inherit = ["sire.rest.client.mixin"]

    periodo_id = fields.Many2one(
        "sire.rvie.periodo",
        string="Periodo RVIE",
        required=True,
    )
    company_id = fields.Many2one(
        related="periodo_id.company_id",
        string="Compañía",
    )
    diff_line_id = fields.Many2one(
        "sire.rvie.diff.line",
        string="Línea de diferencia",
        domain="[('periodo_id', '=', periodo_id)]",
        help="Opcional: si se elige una línea de diferencia con CAR conocido, "
        "se precarga el código a continuación.",
    )
    move_id = fields.Many2one(
        "account.move",
        string="Comprobante Odoo",
        related="diff_line_id.move_id",
        readonly=True,
    )
    cod_car = fields.Char(
        string="CAR SUNAT",
        required=True,
        help="Código de Anotación de Registro del comprobante a excluir.",
    )
    confirm_irreversible = fields.Boolean(
        string="Confirmo que esta exclusión es irreversible",
    )

    @api.onchange("diff_line_id")
    def _onchange_diff_line_id(self):
        if self.diff_line_id and self.diff_line_id.proposal_line_id.cod_car:
            self.cod_car = self.diff_line_id.proposal_line_id.cod_car

    def action_exclude(self):
        self.ensure_one()
        if not self.confirm_irreversible:
            raise UserError(
                _(
                    "Debe confirmar explícitamente que esta exclusión es "
                    "irreversible antes de continuar."
                )
            )
        if not self.cod_car:
            raise UserError(_("Debe indicar el CAR SUNAT del comprobante a excluir."))

        periodo = self.periodo_id
        self._sire_request(
            "DELETE",
            periodo._sire_rvie_exclude_voucher_url(self.cod_car),
            periodo.company_id,
        )
        # Rastro local de auditoria: la exclusion es irreversible en SUNAT y
        # no genera ningun ticket que la registre (a diferencia del resto de
        # acciones del modulo), asi que se marca aqui la linea de propuesta
        # correspondiente -- no hay excepcion despues de este punto, asi que
        # el write si sobrevive (ver decision de diseno 7 del plan aprobado).
        _logger.info(
            "SIRE RVIE: comprobante con CAR %s excluido definitivamente "
            "(periodo %s, compañía %s, usuario %s)",
            self.cod_car,
            periodo.periodo_tributario,
            periodo.company_id.name,
            self.env.user.login,
        )
        matching_line = self.env["sire.rvie.proposal.line"].search(
            [("periodo_id", "=", periodo.id), ("cod_car", "=", self.cod_car)],
            limit=1,
        )
        if matching_line:
            matching_line.write(
                {
                    "excluded": True,
                    "excluded_date": fields.Datetime.now(),
                    "excluded_by_user_id": self.env.uid,
                }
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Exclusión RVIE"),
                "message": _(
                    "El comprobante con CAR %s fue excluido definitivamente "
                    "de la propuesta."
                )
                % self.cod_car,
                "type": "success",
                "sticky": False,
            },
        }
