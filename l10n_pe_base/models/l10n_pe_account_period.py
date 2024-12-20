from odoo import models, fields, api


class AccountPeriod(models.Model):
    _name = 'l10n_pe.account.period'
    _description = 'Periodo Contable'

    code = fields.Char(string='Codigo')
    name = fields.Char(string='Nombre')
    fiscal_year_id = fields.Many2one('account.fiscal.year', string='Año Fiscal')
    date_start = fields.Date(string='Fecha de Inicio')
    date_end = fields.Date(string='Fecha de Fin')
    close = fields.Boolean(string='Cerrado', default=False)

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search(['|', ('code', '=', name), ('name', '=', name)] + args, limit=limit)
        if not recs:
            recs = self.search(['|', ('code', operator, name), ('name', operator, name)] + args, limit=limit)
        return recs.name_get()

    def name_get(self):
        result = []
        for r in self:
            result.append([r.id,r.code])
        return result

    _sql_constraints = [
        ('code_uniq_period', 'unique (code)', 'Dos periodos no pueden tener el mismo código.'),
    ]
