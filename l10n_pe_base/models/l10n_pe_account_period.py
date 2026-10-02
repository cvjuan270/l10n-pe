from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountPeriod(models.Model):
    _name = "l10n_pe.account.period"
    _description = "Periodo Contable"

    code = fields.Char(string="Codigo", readonly=True)
    name = fields.Char(string="Nombre", readonly=True)
    fiscal_year_id = fields.Many2one(
        "account.fiscal.year", string="Año Fiscal", readonly=True
    )
    date_start = fields.Date(string="Fecha de Inicio", readonly=True)
    date_end = fields.Date(string="Fecha de Fin", readonly=True)
    close = fields.Boolean(string="Cerrado", default=False)
    company_id = fields.Many2one("res.company", string="Compañía", readonly="True")

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search(
                ["|", ("code", "=", name), ("name", "=", name)] + args, limit=limit
            )
        if not recs:
            recs = self.search(
                ["|", ("code", operator, name), ("name", operator, name)] + args,
                limit=limit,
            )
        return recs.name_get()

    def name_get(self):
        result = []
        for r in self:
            result.append([r.id, r.name])
        return result

    def unlink(self):
        for period in self:
            related_moves = self.env["account.move"].search_count(
                [("l10n_pe_period_id", "=", period.id)]
            )
            if related_moves > 0:
                raise ValidationError(
                    "No se pede eliminar el perido contable %s por que esta relacionado con %s asientos contables"
                    % (period.name, related_moves)
                )
        return super().unlink()

    _sql_constraints = [
        (
            "code_uniq_period",
            "unique (code,fiscal_year_id,company_id) ",
            "Dos periodos no pueden tener el mismo código dentro del mismo año fiscal.",
        ),
    ]
