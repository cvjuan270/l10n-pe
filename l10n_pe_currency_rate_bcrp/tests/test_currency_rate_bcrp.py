import datetime
from unittest.mock import Mock, patch

import requests
from freezegun import freeze_time

from odoo.tests.common import TransactionCase, tagged

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
class TestCurrencyRateBcrp(TransactionCase):
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
                "name": "Compania PE Test BCRP",
                "currency_id": cls.pen.id,
                "country_id": cls.env.ref("base.pe").id,
            }
        )

    def _usd_rates(self, company=None):
        return self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", (company or self.company).id),
            ],
            order="name",
        )

    def test_period_date_parsing(self):
        """Parseo de fechas de periodo con meses en espanol e ingles."""
        Company = self.env["res.company"]
        cases = {
            "08.Jul.26": datetime.date(2026, 7, 8),
            "05.Ago.26": datetime.date(2026, 8, 5),
            "15.Set.26": datetime.date(2026, 9, 15),
            "01.Aug.26": datetime.date(2026, 8, 1),
            "01.Dic.25": datetime.date(2025, 12, 1),
        }
        for name, expected in cases.items():
            self.assertEqual(Company._l10n_pe_parse_bcrp_period_date(name), expected)
        self.assertIsNone(Company._l10n_pe_parse_bcrp_period_date("basura"))
        self.assertIsNone(Company._l10n_pe_parse_bcrp_period_date("08.Xyz.26"))

    @freeze_time("2026-07-12 12:00:00")
    def test_fetch_rates_inversion_and_nd(self):
        """El fetch retorna {fecha: 1/venta} y omite los dias 'n.d.'."""
        with patch(MOCK_PATH, return_value=_mock_response(BCRP_JSON)) as mocked:
            rates = self.env["res.company"]._l10n_pe_bcrp_fetch_rates()
        self.assertEqual(
            rates,
            {
                datetime.date(2026, 7, 8): 1.0 / 3.412,
                datetime.date(2026, 7, 9): 1.0 / 3.406,
            },
        )
        url = mocked.call_args[0][0]
        self.assertIn("/PD04640PD/json/2026-07-06/2026-07-12", url)

    @freeze_time("2026-07-12 12:00:00")
    def test_fetch_rates_network_error(self):
        """Ante error de red el fetch retorna {} sin lanzar."""
        with patch(MOCK_PATH, side_effect=requests.ConnectionError("boom")):
            self.assertEqual(self.env["res.company"]._l10n_pe_bcrp_fetch_rates(), {})

    def test_upsert_idempotent_and_corrects(self):
        """El upsert crea, no duplica y re-corrige valores editados a mano."""
        rates = {
            datetime.date(2026, 7, 8): 1.0 / 3.412,
            datetime.date(2026, 7, 9): 1.0 / 3.406,
        }
        self.company._l10n_pe_bcrp_upsert_usd_rates(rates)
        rows = self._usd_rates()
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0].rate, 1.0 / 3.412)
        self.assertAlmostEqual(rows[1].rate, 1.0 / 3.406)

        rows[0].rate = 999.0
        self.company._l10n_pe_bcrp_upsert_usd_rates(rates)
        rows = self._usd_rates()
        self.assertEqual(len(rows), 2, "el upsert no debe duplicar filas")
        self.assertAlmostEqual(rows[0].rate, 1.0 / 3.412)

    def test_upsert_fill_missing_dates(self):
        """Con rango, cada dia sin publicacion se completa con la ultima tasa
        anterior; la semilla inicial sale de la BD."""
        seed_date = datetime.date(2026, 7, 5)
        seed_rate = 1.0 / 3.420
        self.env["res.currency.rate"].create(
            {
                "currency_id": self.usd.id,
                "rate": seed_rate,
                "name": seed_date,
                "company_id": self.company.id,
            }
        )
        published = {
            datetime.date(2026, 7, 8): 1.0 / 3.412,
            datetime.date(2026, 7, 9): 1.0 / 3.406,
        }
        self.company._l10n_pe_bcrp_upsert_usd_rates(
            published,
            datetime.date(2026, 7, 6),
            datetime.date(2026, 7, 12),
        )
        rows = self._usd_rates()
        expected = {
            datetime.date(2026, 7, 5): seed_rate,
            datetime.date(2026, 7, 6): seed_rate,  # relleno con semilla BD
            datetime.date(2026, 7, 7): seed_rate,
            datetime.date(2026, 7, 8): 1.0 / 3.412,  # publicada
            datetime.date(2026, 7, 9): 1.0 / 3.406,  # publicada
            datetime.date(2026, 7, 10): 1.0 / 3.406,  # relleno
            datetime.date(2026, 7, 11): 1.0 / 3.406,
            datetime.date(2026, 7, 12): 1.0 / 3.406,
        }
        self.assertEqual(len(rows), len(expected))
        for row in rows:
            self.assertAlmostEqual(row.rate, expected[row.name], msg=row.name)

    def test_upsert_fill_without_seed(self):
        """Sin publicaciones en el rango ni tasas previas en BD, no se crea
        nada (no hay de donde rellenar)."""
        self.company._l10n_pe_bcrp_upsert_usd_rates(
            {},
            datetime.date(2026, 7, 6),
            datetime.date(2026, 7, 12),
        )
        self.assertFalse(self._usd_rates())

    def test_upsert_non_pen_base_skipped(self):
        """Compania con base != PEN no recibe tasas del upsert."""
        company_usd = self.env["res.company"].create(
            {
                "name": "Base USD",
                "currency_id": self.usd.id,
                "country_id": self.env.ref("base.pe").id,
            }
        )
        company_usd._l10n_pe_bcrp_upsert_usd_rates(
            {datetime.date(2026, 7, 8): 1.0 / 3.412}
        )
        self.assertFalse(self._usd_rates(company_usd))

    @freeze_time("2026-07-12 12:00:00")
    def test_cron_entrypoint(self):
        """El cron actualiza en Community y no hace nada si currency_rate_live
        (enterprise) esta instalado — ahi manda el proveedor bcrp_api."""
        Company = self.env["res.company"]
        with patch(MOCK_PATH, return_value=_mock_response(BCRP_JSON)):
            Company._l10n_pe_bcrp_update_rates()
        if "currency_provider" in Company._fields:
            self.assertFalse(
                self._usd_rates(),
                "con enterprise instalado el cron propio debe ser no-op",
            )
        else:
            # 08 y 09 publicadas + 10..12 rellenadas con la de 09; 06 y 07
            # quedan fuera (sin semilla previa en BD).
            rows = self._usd_rates()
            self.assertEqual(
                rows.mapped("name"),
                [datetime.date(2026, 7, d) for d in range(8, 13)],
            )
            for row in rows[1:]:
                self.assertAlmostEqual(row.rate, 1.0 / 3.406)
