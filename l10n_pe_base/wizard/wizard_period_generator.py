import calendar

from odoo import fields, models

from datetime import date
import logging
from odoo.exceptions import UserError

month_es_pe = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]


class WizardPeriodGenerator(models.TransientModel):
    _name = 'wizard.l10n_pe.period.generator'
    _description = 'Generador de Periodos Contables'

    def _get_fiscal_year(self):
        today = fields.Date.context_today(self)
        fiscal_year = self.env['account.fiscal.year'].search([('name', '=', str(today.year))], limit=1)
        if not fiscal_year:
            raise UserError('el año fiscal no existe para este año')
        else:
            return fiscal_year.id

    account_fiscal_year_id = fields.Many2one(
        'account.fiscal.year', string='Año Fiscal', default=lambda self: self._get_fiscal_year(), required=True)

    def period_generator(self):
        if not self.account_fiscal_year_id:
            raise UserError('El año fiscal es un campo obligatorio')
        if not self.account_fiscal_year_id.name.isdigit():
            raise UserError('El año fiscal debe ser un número entero válido ejemplo: 2022')
        self.create_periods(self.account_fiscal_year_id.id)

    def create_periods(self, fiscal_year_id):
        fiscal_year = self.env['account.fiscal.year'].browse(fiscal_year_id)
        log = []
        for c in range(0, 14):
            account_fiscal_year = str(fiscal_year.date_from.year)
            period_code = f'{account_fiscal_year}{str(c).zfill(2)}'
            if c == 0:
                period_name = f'APERTURA-{account_fiscal_year}'
                date_start = f'{date(int(account_fiscal_year), 1, 1)}'
                date_end = f'{date(int(account_fiscal_year), 1, 1)}'
            elif c == 13:
                period_name = f'CIERRE-{account_fiscal_year}'
                date_start = f'{date(int(account_fiscal_year), 12, 31)}'
                date_end = f'{date(int(account_fiscal_year), 12, 31)}'
            else:
                period_name = f'{month_es_pe[c-1].upper()}-{account_fiscal_year}'
                date_start = f'{date(int(account_fiscal_year), c, 1)}'
                date_end = f'{date(int(account_fiscal_year), c, calendar.monthrange(int(account_fiscal_year), c)[1])}'
            account_period = self.env['l10n_pe.account.period'].search(
                [('code', '=', period_code), ('fiscal_year_id', '=', fiscal_year_id)], limit=1)
            if account_period:
                continue
            else:
                self.env['l10n_pe.account.period'].create({
                    'code': period_code,
                    'name': period_name,
                    'fiscal_year_id': fiscal_year_id,
                    'company_id': fiscal_year.company_id.id,
                    'date_start': date_start,
                    'date_end': date_end,
                })
                logging.info('Periodo %s creado' % (period_name))
                log.append(period_name)
        # raise UserWarning(f'Se generaron los periodos contables: \n {log}')
