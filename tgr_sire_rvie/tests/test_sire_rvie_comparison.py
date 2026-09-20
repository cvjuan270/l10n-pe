"""Genera el registro de ventas comparable desde ``account.move`` (fixtures
reales: factura, nota de credito, moneda extranjera) y lo cruza contra una
propuesta SUNAT mockeada cubriendo los 4 ``match_status``."""

from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from .common import SireRvieTestMixin, sire_mock_response

REST_MOCK_PATH = (
    "odoo.addons.tgr_sire_mixin.models.sire_rest_client_mixin.requests.request"
)


@tagged("post_install", "-at_install")
class TestSireRvieComparison(SireRvieTestMixin, AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._sire_rvie_setup_pe_company()

    def setUp(self):
        super().setUp()
        self._sire_set_company_token()

    # -- generacion del registro Odoo (account.move) -----------------------------
    def test_parse_document_number_with_prefix(self):
        invoice = self._sire_rvie_create_invoice("F F001-123", amount=100.0)
        serie, numero = invoice._sire_rvie_parse_document_number()
        self.assertEqual(serie, "F001")
        self.assertEqual(numero, "123")

    def test_parse_document_number_without_prefix(self):
        invoice = self._sire_rvie_create_invoice(
            "B001-00000467",
            amount=50.0,
            journal=self.no_doc_journal,
        )
        serie, numero = invoice._sire_rvie_parse_document_number()
        self.assertEqual(serie, "B001")
        self.assertEqual(numero, "00000467")

    def test_build_register_row_invoice(self):
        invoice = self._sire_rvie_create_invoice("F F001-1", amount=100.0)
        row = invoice._sire_rvie_build_register_row()
        self.assertEqual(row["tipo_cp"], "01")
        self.assertEqual(row["serie"], "F001")
        self.assertEqual(row["numero"], "1")
        self.assertEqual(row["partner_vat"], self.pe_partner.vat)
        self.assertEqual(row["partner_id_type"], "1")  # DNI -> l10n_pe_vat_code
        self.assertEqual(row["partner_name"], self.pe_partner.name)
        self.assertAlmostEqual(row["amount_taxed"], 100.0, places=2)
        self.assertAlmostEqual(row["amount_igv"], 18.0, places=2)
        self.assertAlmostEqual(row["amount_total"], 118.0, places=2)
        self.assertFalse(row["exchange_rate"])

    def test_build_register_row_credit_note_is_negative(self):
        invoice = self._sire_rvie_create_invoice("F F001-2", amount=100.0)
        credit_note = self._sire_rvie_create_credit_note(
            "F FC01-1", invoice, amount=100.0
        )
        row = credit_note._sire_rvie_build_register_row()
        self.assertEqual(row["tipo_cp"], "07")
        self.assertAlmostEqual(row["amount_total"], -118.0, places=2)
        self.assertAlmostEqual(row["amount_taxed"], -100.0, places=2)
        self.assertAlmostEqual(row["amount_igv"], -18.0, places=2)
        self.assertEqual(row["ref_tipo_cp"], "01")
        self.assertEqual(row["ref_serie"], "F001")
        self.assertEqual(row["ref_numero"], "2")

    def test_build_register_row_foreign_currency(self):
        # Moneda distinta a la de la compañía garantizada (no se asume cual
        # de USD/EUR coincide con la moneda del chart of accounts generico
        # de AccountTestInvoicingCommon).
        foreign_currency = self.env["res.currency"].create(
            {"name": "XTS", "symbol": "XTS", "rounding": 0.01}
        )
        invoice = self._sire_rvie_create_invoice(
            "F F001-3",
            amount=100.0,
            currency_id=foreign_currency.id,
            invoice_currency_rate=0.27,
        )
        row = invoice._sire_rvie_build_register_row()
        self.assertEqual(row["currency_code"], "XTS")
        self.assertAlmostEqual(row["exchange_rate"], round(1 / 0.27, 3), places=3)

    def test_register_includes_moves_without_document_type(self):
        self._sire_rvie_create_invoice(
            "TCK-1", amount=30.0, journal=self.no_doc_journal
        )
        rows = self.env["account.move"]._sire_rvie_get_ventas_register(
            self.company,
            "202601",
        )
        no_doc_rows = [r for r in rows if not r["tipo_cp"]]
        self.assertTrue(
            no_doc_rows,
            "un comprobante de un diario sin l10n_latam_use_documents debe "
            "seguir apareciendo en el registro Odoo, no desaparecer",
        )

    # -- cruce contra la propuesta SUNAT -----------------------------------------
    def test_cross_covers_four_match_statuses(self):
        self._sire_rvie_create_invoice("F F001-10", amount=100.0)  # matched
        self._sire_rvie_create_invoice("F F001-11", amount=100.0)  # amount_mismatch
        self._sire_rvie_create_invoice("F F001-12", amount=100.0)  # missing_in_sunat
        self._sire_rvie_create_invoice(
            "TCK-2",
            amount=20.0,
            journal=self.no_doc_journal,
        )  # tambien missing_in_sunat (sin tipo de documento)

        periodo = self.env["sire.rvie.periodo"].create(
            {"company_id": self.company.id, "periodo_tributario": "202601"}
        )
        self.env["sire.rvie.proposal.line"].create(
            [
                {
                    "periodo_id": periodo.id,
                    "tipo_cp": "01",
                    "serie": "F001",
                    "numero": "10",
                    "amount_total": 118.0,
                    "partner_name": self.pe_partner.name,
                },
                {
                    "periodo_id": periodo.id,
                    "tipo_cp": "01",
                    "serie": "F001",
                    "numero": "11",
                    "amount_total": 999.0,
                    "partner_name": self.pe_partner.name,
                },
                {
                    # Ningun comprobante Odoo tiene esta clave: missing_in_odoo.
                    "periodo_id": periodo.id,
                    "tipo_cp": "01",
                    "serie": "F001",
                    "numero": "999",
                    "amount_total": 50.0,
                    "partner_name": "Cliente solo en SUNAT",
                },
            ]
        )

        odoo_rows = self.env["account.move"]._sire_rvie_get_ventas_register(
            self.company,
            "202601",
        )
        periodo._sire_rvie_cross(odoo_rows)

        statuses = {line.match_status for line in periodo.diff_line_ids}
        self.assertEqual(
            statuses,
            {"matched", "amount_mismatch", "missing_in_odoo", "missing_in_sunat"},
        )
        self.assertEqual(periodo.diff_count_amount_mismatch, 1)
        self.assertEqual(periodo.diff_count_missing_odoo, 1)
        self.assertEqual(periodo.diff_count_missing_sunat, 2)

        matched_line = periodo.diff_line_ids.filtered(
            lambda line: line.match_status == "matched"
        )
        self.assertEqual(matched_line.amount_diff, 0.0)

        mismatch_line = periodo.diff_line_ids.filtered(
            lambda line: line.match_status == "amount_mismatch"
        )
        self.assertAlmostEqual(mismatch_line.amount_odoo, 118.0, places=2)
        self.assertAlmostEqual(mismatch_line.amount_sunat, 999.0, places=2)

    def test_action_compare_proposal_creates_async_ticket(self):
        """``action_compare_proposal`` llama al servicio real 5.18
        (asincrono: devuelve ``numTicket``, no el detalle de comprobantes)
        y solo crea el ``sire.ticket`` correspondiente -- no cruza contra
        Odoo en esta misma llamada (ver ``_sire_rvie_download_proposal``)."""
        periodo = self.env["sire.rvie.periodo"].create(
            {"company_id": self.company.id, "periodo_tributario": "202601"}
        )
        payload = {"numTicket": "202601000077"}
        with patch(
            REST_MOCK_PATH, return_value=sire_mock_response(200, payload)
        ) as mocked:
            ticket = periodo.action_compare_proposal()

        mocked.assert_called_once()
        self.assertEqual(ticket.operation_type, "export_proposal_detail")
        self.assertEqual(ticket.sunat_ticket_number, "202601000077")
        self.assertEqual(periodo.last_ticket_id, ticket)
        self.assertEqual(
            periodo.local_state,
            "draft",
            "no hay datos reales que cruzar todavia -- el parseo del "
            "archivo descargado queda pendiente (layout no confirmado)",
        )
        self.assertFalse(periodo.proposal_line_ids)
