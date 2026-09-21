from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_provider = fields.Selection(
        selection_add=[("bcrp_api", "[PE] BCRP (API oficial)")],
        # Al desinstalar, volver al proveedor SUNAT de enterprise: el compute
        # (store=True) no se re-dispara solo y 'set null' detendria el cron.
        ondelete={"bcrp_api": lambda recs: recs.write({"currency_provider": "bcrp"})},
    )

    @api.depends("country_id")
    def _compute_currency_provider(self):
        res = super()._compute_currency_provider()
        for company in self:
            if company.country_id.code == "PE":
                company.currency_provider = "bcrp_api"
        return res

    def _parse_bcrp_api_data(self, available_currencies):
        """Proveedor para el framework de currency_rate_live. La consulta a
        la API y el parsing viven en el modulo base (community); aqui solo se
        adapta al contrato {moneda: (tasa, fecha)}:
        * Base PEN=1.0; USD = 1/venta.
        * El framework solo soporta una fecha por moneda, asi que todo el
          rango (dias publicados + dias completados con la ultima tasa
          anterior, regla SUNAT) se upsertea directamente y solo el ultimo
          dia publicado se retorna para _generate_currency_rates."""
        result = {}
        available_currency_names = available_currencies.mapped("name")
        if (
            "PEN" not in available_currency_names
            or "USD" not in available_currency_names
        ):
            return result
        date_from, date_to = self._l10n_pe_bcrp_date_range()
        result["PEN"] = (1.0, date_to)
        rates_by_date = self._l10n_pe_bcrp_fetch_rates(date_from, date_to)
        # Upsert de todo el rango, incluyendo dias sin publicacion rellenados
        # con la ultima tasa anterior (sembrada desde la BD si hace falta).
        self._l10n_pe_bcrp_upsert_usd_rates(rates_by_date, date_from, date_to)
        if not rates_by_date:
            return result

        last_date = max(rates_by_date)
        result["PEN"] = (1.0, last_date)
        result["USD"] = (rates_by_date[last_date], last_date)
        return result
