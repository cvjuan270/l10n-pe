from odoo import api, SUPERUSER_ID
from datetime import datetime
import logging


def post_init_hook(cr, registry):
    """
    Hook que se ejecuta después de instalar el módulo.
    Se encarga de crear los años fiscales y períodos contables
    a partir del registro más antiguo en una compañía de Perú.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Buscar compañías en Perú
    pe_country_id = env['res.country'].search([('code', '=', 'PE')], limit=1).id
    if not pe_country_id:
        return
    peru_companies = env['res.company'].search([('partner_id.country_id', '=', pe_country_id)])

    if not peru_companies:
        return

    for company in peru_companies:
        # Buscar el movimiento contable más antiguo en la compañía
        oldest_move = env['account.move'].search([('company_id', '=', company.id)], order="date asc", limit=1)

        start_year = oldest_move.date.year if oldest_move else datetime.today().year  # Año más antiguo registrado
        current_year = datetime.today().year

        for year in range(start_year, current_year + 1):
            # Verificar si el año fiscal ya existe
            fiscal_year = env['account.fiscal.year'].search(
                [('name', '=', str(year)), ('company_id', '=', company.id)], limit=1)

            if not fiscal_year:
                # Crear el año fiscal
                fiscal_year = env['account.fiscal.year'].create({
                    'name': str(year),
                    'date_from': f'{year}-01-01',
                    'date_to': f'{year}-12-31',
                    'company_id': company.id
                })
                logging.info('Año fiscal %s creado.' % (fiscal_year.name))
            # Crear el períodos contables para el año fiscal
            wizard_period_generator = env['wizard.l10n_pe.period.generator']
            wizard_period_generator.create_periods(fiscal_year.id)

        # Actualizar periodo contable en asientos existentes
        moves = env['account.move'].search([('state', '=', 'posted'), ('company_id', '=', company.id)])
        moves._compute_l10n_pe_period()
