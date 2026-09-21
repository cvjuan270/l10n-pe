import datetime
from unittest.mock import Mock, patch

import requests
from freezegun import freeze_time

from odoo.tests.common import TransactionCase, tagged

# requests vive en el modulo base (community), que es donde se mockea.
MOCK_PATH = "odoo.addons.l10n_pe_currency_rate_bcrp.models.res_company.requests.get"

BCRP_JSON = {
    "config": {
        "title": "Tipo de cambio",
        "series": [
            {
                "name": "Tipo de cambio - TC Sistema bancario SBS (S/ por US$) - Venta",
                "dec": "3",
            }
        ],
    },
    "periods": [
        {"name": "08.Jul.26", "values": ["3.412"]},
        {"name": "09.Jul.26", "values": ["3.406"]},
        {"name": "10.Jul.26", "values": ["n.d."]},
    ],
}


def _mock_response(payload):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = payload
    return response


@tagged("post_install", "-at_install")
class TestCurrencyRateBcrpEnterprise(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # En BDs con automatizaciones sobre res.partner (p.ej. ID de contacto
        # obligatorio en o18_cms) la creacion de companias de prueba falla;
        # se archivan dentro de la transaccion del test.
        if "base.automation" in cls.env:
            cls.env["base.automation"].search(
                [("model_id.model", "=", "res.partner")]
            ).action_archive()
        cls.pen = cls.env.ref("base.PEN")
        cls.usd = cls.env.ref("base.USD")
        (cls.pen + cls.usd).write({"active": True})
        cls.company = cls.env["res.company"].create(
            {
                "name": "Compania PE Test BCRP Ent",
                "currency_id": cls.pen.id,
                "country_id": cls.env.ref("base.pe").id,
            }
        )
        cls.company.currency_provider = "bcrp_api"
        cls.currencies = cls.pen + cls.usd

    def _usd_rates(self):
        return self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
            ],
            order="name",
        )

    @freeze_time("2026-07-12 12:00:00")
    def test_parse_basic_and_inversion(self):
        """El parser retorna la ultima fecha publicada con la tasa 1/venta
        y PEN=1.0 en la misma fecha."""
        with patch(MOCK_PATH, return_value=_mock_response(BCRP_JSON)):
            result = self.company._parse_bcrp_api_data(self.currencies)
        self.assertEqual(result["USD"], (1.0 / 3.406, datetime.date(2026, 7, 9)))
        self.assertEqual(result["PEN"], (1.0, datetime.date(2026, 7, 9)))

    @freeze_time("2026-07-12 12:00:00")
    def test_nd_omitted(self):
        """Si todos los dias vienen 'n.d.' no se retorna USD, solo PEN."""
        payload = {
            "config": {},
            "periods": [
                {"name": "10.Jul.26", "values": ["n.d."]},
                {"name": "11.Jul.26", "values": ["n.d."]},
            ],
        }
        with patch(MOCK_PATH, return_value=_mock_response(payload)):
            result = self.company._parse_bcrp_api_data(self.currencies)
        self.assertNotIn("USD", result)
        self.assertEqual(result["PEN"], (1.0, datetime.date(2026, 7, 12)))

    @freeze_time("2026-07-12 12:00:00")
    def test_update_currency_rates_multi_date_upsert(self):
        """El flujo completo del framework crea tasas para todas las fechas
        del rango (publicadas + rellenadas con la ultima anterior), es
        idempotente y re-corrige valores modificados a mano."""
        with patch(MOCK_PATH, return_value=_mock_response(BCRP_JSON)):
            self.company.update_currency_rates()
        rates = self._usd_rates()
        # 08 y 09 publicadas + 10..12 rellenadas con la de 09; 06 y 07 quedan
        # fuera (sin semilla previa en BD).
        self.assertEqual(
            rates.mapped("name"),
            [datetime.date(2026, 7, d) for d in range(8, 13)],
        )
        self.assertAlmostEqual(rates[0].rate, 1.0 / 3.412)
        for row in rates[1:]:
            self.assertAlmostEqual(row.rate, 1.0 / 3.406)

        rates[0].rate = 999.0
        with patch(MOCK_PATH, return_value=_mock_response(BCRP_JSON)):
            self.company.update_currency_rates()
        rates = self._usd_rates()
        self.assertEqual(len(rates), 5, "el upsert no debe duplicar filas")
        self.assertAlmostEqual(rates[0].rate, 1.0 / 3.412)

    @freeze_time("2026-07-12 12:00:00")
    def test_network_error_partial(self):
        """Ante error de red el parser retorna solo PEN y el flujo con
        suppress_errors no lanza."""
        with patch(MOCK_PATH, side_effect=requests.ConnectionError("boom")):
            result = self.company._parse_bcrp_api_data(self.currencies)
            self.assertNotIn("USD", result)
            self.assertEqual(result["PEN"], (1.0, datetime.date(2026, 7, 12)))
            self.company.with_context(suppress_errors=True).update_currency_rates()

    def test_compute_provider_pe_default(self):
        """Una compania nueva con pais PE toma bcrp_api; otros paises
        conservan el default del super."""
        company_pe = self.env["res.company"].create(
            {"name": "Otra PE", "country_id": self.env.ref("base.pe").id}
        )
        self.assertEqual(company_pe.currency_provider, "bcrp_api")
        company_cl = self.env["res.company"].create(
            {"name": "Chilena", "country_id": self.env.ref("base.cl").id}
        )
        self.assertEqual(company_cl.currency_provider, "mindicador")
