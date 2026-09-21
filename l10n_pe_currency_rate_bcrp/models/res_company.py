import datetime
import logging

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

BCRP_API_URL = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api/%s/json/%s/%s"
BCRP_SERIES_VENTA = "PD04640PD"  # TC Sistema bancario SBS (S/ por US$) - Venta
BCRP_DAYS_BACK = 7
# La API puede devolver la abreviatura del mes en ingles o espanol segun el
# locale del servidor del BCRP; el mapping cubre ambas variantes ('set' es la
# abreviatura peruana usual de septiembre).
BCRP_MONTHS = {
    "ene": 1,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "aug": 8,
    "sep": 9,
    "set": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
    "dec": 12,
}


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def _l10n_pe_parse_bcrp_period_date(self, name):
        """'08.Jul.26' -> date(2026, 7, 8). Retorna None si no es parseable."""
        try:
            day, month, year = name.strip().split(".")
            return datetime.date(
                2000 + int(year), BCRP_MONTHS[month.lower()[:3]], int(day)
            )
        except (ValueError, KeyError):
            _logger.warning("BCRP: fecha de periodo no parseable %r", name)
            return None

    @api.model
    def _l10n_pe_bcrp_date_range(self):
        """Rango de consulta: los ultimos BCRP_DAYS_BACK dias en hora Lima."""
        today = fields.Date.context_today(self.with_context(tz="America/Lima"))
        return today - datetime.timedelta(days=BCRP_DAYS_BACK - 1), today

    @api.model
    def _l10n_pe_bcrp_fetch_rates(self, date_from=None, date_to=None):
        """Consulta la API oficial del BCRP (serie PD04640PD, TC SBS venta)
        y retorna {date: 1/venta}. Por defecto, los ultimos BCRP_DAYS_BACK
        dias.
        Source: https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/api
        Dias sin publicacion ('n.d.') se omiten. Ante error de red retorna {}
        (solo log, no lanza)."""
        if not date_from or not date_to:
            date_from, date_to = self._l10n_pe_bcrp_date_range()
        url = BCRP_API_URL % (
            BCRP_SERIES_VENTA,
            date_from.isoformat(),
            date_to.isoformat(),
        )
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            _logger.error(e)
            return {}

        rates_by_date = {}
        for period in data.get("periods", []):
            date_rate = self._l10n_pe_parse_bcrp_period_date(period.get("name", ""))
            values = period.get("values") or []
            try:
                venta = float(values[0])
            except (IndexError, TypeError, ValueError):
                continue
            if date_rate and venta:
                rates_by_date[date_rate] = 1.0 / venta
        return rates_by_date

    def _l10n_pe_bcrp_upsert_usd_rates(
        self, rates_by_date, date_from=None, date_to=None
    ):
        """Upsert de tasas USD con la misma semantica por (currency, date,
        company) que usa el framework de tasas. Las tasas vienen relativas a
        PEN=1.0, por lo que solo aplica a companias con moneda base PEN.

        Si se pasa un rango [date_from, date_to], cada dia del rango sin tasa
        publicada se completa con la ultima anterior mas cercana (regla SUNAT:
        usar el ultimo TC publicado). Para los dias del inicio del rango sin
        publicacion previa dentro del mismo, la semilla es la ultima tasa ya
        registrada en la BD antes del rango."""
        usd = self.env["res.currency"].search([("name", "=", "USD")], limit=1)
        if not usd:
            return
        CurrencyRate = self.env["res.currency.rate"]
        for company in self:
            if company.currency_id.name != "PEN":
                _logger.warning(
                    "BCRP: se omiten tasas para %s (moneda base %s != PEN)",
                    company.name,
                    company.currency_id.name,
                )
                continue
            filled = dict(rates_by_date)
            if date_from and date_to:
                previous = CurrencyRate.search(
                    [
                        ("currency_id", "=", usd.id),
                        ("name", "<", date_from),
                        ("company_id", "=", company.id),
                    ],
                    order="name desc",
                    limit=1,
                )
                current = previous.rate if previous else None
                day = date_from
                while day <= date_to:
                    if day in filled:
                        current = filled[day]
                    elif current:
                        filled[day] = current
                    day += datetime.timedelta(days=1)
            for date_rate, rate in filled.items():
                existing = CurrencyRate.search(
                    [
                        ("currency_id", "=", usd.id),
                        ("name", "=", date_rate),
                        ("company_id", "=", company.id),
                    ]
                )
                if existing:
                    existing.rate = rate
                else:
                    CurrencyRate.create(
                        {
                            "currency_id": usd.id,
                            "rate": rate,
                            "name": date_rate,
                            "company_id": company.id,
                        }
                    )

    @api.model
    def _l10n_pe_bcrp_update_rates(self):
        """Entrada del cron propio (instalaciones Community). Si
        currency_rate_live (enterprise) esta instalado, la actualizacion la
        hace su cron via el proveedor 'bcrp_api' del modulo puente
        l10n_pe_currency_rate_bcrp_enterprise, y este metodo no hace nada."""
        if "currency_provider" in self._fields:
            return
        if not self.env["res.currency"].search([("name", "=", "USD")], limit=1):
            _logger.warning(
                "BCRP: la moneda USD no esta activa, no hay nada que actualizar"
            )
            return
        companies = self.search(
            [
                ("parent_id", "=", False),
                ("currency_id.name", "=", "PEN"),
            ]
        )
        if not companies:
            return
        date_from, date_to = self._l10n_pe_bcrp_date_range()
        companies._l10n_pe_bcrp_upsert_usd_rates(
            self._l10n_pe_bcrp_fetch_rates(date_from, date_to), date_from, date_to
        )
