"""Genera el registro de ventas comparable desde ``account.move`` (fixtures
reales: factura, nota de credito, moneda extranjera) y lo cruza contra una
propuesta SUNAT mockeada cubriendo los 4 ``match_status``."""

import io
import zipfile
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from .common import SireRvieTestMixin, sire_mock_response

REST_MOCK_PATH = (
    "odoo.addons.tgr_sire_mixin.models.sire_rest_client_mixin.requests.request"
)

# Columnas reales del .txt de detalle de propuesta (servicio 5.18/5.17),
# confirmadas contra un archivo real de SUNAT -- ver
# sire_rvie_periodo._sire_rvie_parse_proposal_content.
PROPOSAL_FILE_HEADER = (
    "Ruc|Razon Social|Periodo|CAR SUNAT|Fecha de emisión|Fecha Vcto/Pago|"
    "Tipo CP/Doc.|Serie del CDP|Nro CP o Doc. Nro Inicial (Rango)|"
    "Nro Final (Rango)|Tipo Doc Identidad|Nro Doc Identidad|"
    "Apellidos Nombres/ Razón Social|Valor Facturado Exportación|"
    "BI Gravada|Dscto BI|IGV / IPM|Dscto IGV / IPM|Mto Exonerado|"
    "Mto Inafecto|ISC|BI Grav IVAP|IVAP|ICBPER|Otros Tributos|Total CP|"
    "Moneda|Tipo Cambio|Fecha Emisión Doc Modificado|Tipo CP Modificado|"
    "Serie CP Modificado|Nro CP Modificado"
)


def _build_proposal_zip(rows):
    """Arma en memoria un ZIP con el mismo layout que descarga el ticket
    "export_proposal_detail" (encabezado + filas separadas por ``|``)."""
    content = "\n".join([PROPOSAL_FILE_HEADER] + rows)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        zip_file.writestr("propuesta.txt", content)
    return buffer.getvalue()


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

    def test_parse_document_number_prefix_concatenates_into_serie(self):
        """PROBADO EN VIVO: un comprobante real con este patron de nombre
        tenia serie "FFFI" en el XML UBL enviado a SUNAT, pero el criterio
        anterior (descartar el prefijo en vez de concatenarlo) devolvia
        "FFI" -- serie de 3 caracteres que nunca cruzaba contra la
        propuesta."""
        invoice = self._sire_rvie_create_invoice(
            "F FFI-00000122",
            amount=100.0,
            journal=self.no_doc_journal,
        )
        serie, numero = invoice._sire_rvie_parse_document_number()
        self.assertEqual(serie, "FFFI")
        self.assertEqual(numero, "00000122")

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
                    "amount_taxed": 100.0,
                    "amount_igv": 18.0,
                    "amount_total": 118.0,
                    "partner_name": self.pe_partner.name,
                },
                {
                    "periodo_id": periodo.id,
                    "tipo_cp": "01",
                    "serie": "F001",
                    "numero": "11",
                    "amount_taxed": 900.0,
                    "amount_igv": 99.0,
                    "amount_total": 999.0,
                    "partner_name": self.pe_partner.name,
                },
                {
                    # Ningun comprobante Odoo tiene esta clave: missing_in_odoo.
                    "periodo_id": periodo.id,
                    "tipo_cp": "01",
                    "serie": "F001",
                    "numero": "999",
                    "amount_taxed": 42.0,
                    "amount_igv": 8.0,
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
        self.assertEqual(periodo.diff_count_matched, 1)

        # F001-10 (matched, 118.0); F001-12 + TCK-2 (missing_in_sunat,
        # 118.0 + 23.6); numero 999 (missing_in_odoo, 50.0 -- solo existe
        # en la propuesta SUNAT, se suma su amount_sunat).
        self.assertAlmostEqual(periodo.diff_amount_matched, 118.0, places=2)
        self.assertAlmostEqual(periodo.diff_amount_missing_sunat, 141.6, places=2)
        self.assertAlmostEqual(periodo.diff_amount_missing_odoo, 50.0, places=2)
        self.assertAlmostEqual(periodo.diff_taxed_matched, 100.0, places=2)
        self.assertAlmostEqual(periodo.diff_taxed_missing_sunat, 120.0, places=2)
        self.assertAlmostEqual(periodo.diff_taxed_missing_odoo, 42.0, places=2)
        self.assertAlmostEqual(periodo.diff_igv_matched, 18.0, places=2)
        self.assertAlmostEqual(periodo.diff_igv_missing_sunat, 21.6, places=2)
        self.assertAlmostEqual(periodo.diff_igv_missing_odoo, 8.0, places=2)

        matched_line = periodo.diff_line_ids.filtered(
            lambda line: line.match_status == "matched"
        )
        self.assertEqual(matched_line.amount_diff, 0.0)
        self.assertEqual(matched_line.amount_taxed_diff, 0.0)
        self.assertEqual(matched_line.amount_igv_diff, 0.0)

        mismatch_line = periodo.diff_line_ids.filtered(
            lambda line: line.match_status == "amount_mismatch"
        )
        self.assertAlmostEqual(mismatch_line.amount_odoo, 118.0, places=2)
        self.assertAlmostEqual(mismatch_line.amount_sunat, 999.0, places=2)
        self.assertAlmostEqual(mismatch_line.amount_taxed_odoo, 100.0, places=2)
        self.assertAlmostEqual(mismatch_line.amount_taxed_sunat, 900.0, places=2)
        self.assertAlmostEqual(mismatch_line.amount_taxed_diff, -800.0, places=2)
        self.assertAlmostEqual(mismatch_line.amount_igv_odoo, 18.0, places=2)
        self.assertAlmostEqual(mismatch_line.amount_igv_sunat, 99.0, places=2)
        self.assertAlmostEqual(mismatch_line.amount_igv_diff, -81.0, places=2)

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
            "action_compare_proposal solo crea el ticket -- el parseo se "
            "dispara recien cuando ese ticket termina (ver "
            "test_poll_ticket_done_imports_proposal_and_crosses)",
        )
        self.assertFalse(periodo.proposal_line_ids)

    def test_cross_normalizes_leading_zeros_in_numero(self):
        """PROBADO EN VIVO (periodo 202609, comprobante B001-1134): Odoo
        genera el numero con ceros a la izquierda ("00001134"), SUNAT lo
        entrega sin ellos ("1134") -- deben cruzar como "matched", no
        aparecer duplicados como missing_in_odoo + missing_in_sunat."""
        invoice = self._sire_rvie_create_invoice("F B001-00001134", amount=100.0)

        periodo = self.env["sire.rvie.periodo"].create(
            {"company_id": self.company.id, "periodo_tributario": "202601"}
        )
        self.env["sire.rvie.proposal.line"].create(
            {
                "periodo_id": periodo.id,
                "tipo_cp": "01",
                "serie": "B001",
                "numero": "1134",
                "amount_total": 118.0,
                "partner_name": self.pe_partner.name,
            }
        )

        odoo_rows = self.env["account.move"]._sire_rvie_get_ventas_register(
            self.company,
            "202601",
        )
        periodo._sire_rvie_cross(odoo_rows)

        self.assertEqual(len(periodo.diff_line_ids), 1)
        diff_line = periodo.diff_line_ids
        self.assertEqual(diff_line.match_status, "matched")
        self.assertEqual(diff_line.move_id, invoice)

    def test_poll_ticket_done_imports_proposal_and_crosses(self):
        """``action_poll_ticket`` sobre un ticket "export_proposal_detail"
        ya terminado descarga el archivo real, puebla ``proposal_line_ids``,
        corre ``_sire_rvie_cross`` contra el registro Odoo y avanza
        ``local_state`` a "compared" -- todo en un solo paso, sin que el
        usuario tenga que descargar/inspeccionar el archivo a mano."""
        invoice = self._sire_rvie_create_invoice("F F001-20", amount=100.0)

        periodo = self.env["sire.rvie.periodo"].create(
            {
                "company_id": self.company.id,
                "periodo_tributario": "202601",
                "local_state": "checked",
            }
        )
        ticket = self.env["sire.ticket"].create(
            {
                "company_id": self.company.id,
                "operation_type": "export_proposal_detail",
                "periodo_tributario": "202601",
                "sunat_ticket_number": "202601000088",
                "state": "sent",
                "rvie_periodo_id": periodo.id,
            }
        )
        periodo.last_ticket_id = ticket

        status_payload = {
            "registros": [
                {
                    "numTicket": ticket.sunat_ticket_number,
                    "codProceso": "10",
                    "detalleTicket": {
                        "codEstadoEnvio": "06",
                        "desEstadoEnvio": "Terminado",
                    },
                    "archivoReporte": [
                        {
                            "nomArchivoReporte": "propuesta.zip",
                            "codTipoAchivoReporte": "00",
                        }
                    ],
                }
            ]
        }
        proposal_row = (
            "20557912879|Test Co|202601|CAR123|15/01/2026||01|F001|20||1|"
            f"{self.pe_partner.vat}|{self.pe_partner.name}|0|100.00|0|18.00|"
            "0|0|0|0|0|0|0|0|118.00|PEN|1.000||||"
        )
        zip_content = _build_proposal_zip([proposal_row])

        with patch(
            REST_MOCK_PATH,
            side_effect=[
                sire_mock_response(200, status_payload),
                sire_mock_response(200, content=zip_content),
            ],
        ) as mocked:
            periodo.action_poll_ticket()

        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(periodo.local_state, "compared")
        self.assertEqual(len(periodo.proposal_line_ids), 1)
        proposal_line = periodo.proposal_line_ids
        self.assertEqual(proposal_line.tipo_cp, "01")
        self.assertEqual(proposal_line.serie, "F001")
        self.assertEqual(proposal_line.numero, "20")
        self.assertAlmostEqual(proposal_line.amount_total, 118.0, places=2)

        self.assertEqual(len(periodo.diff_line_ids), 1)
        diff_line = periodo.diff_line_ids
        self.assertEqual(diff_line.match_status, "matched")
        self.assertEqual(diff_line.move_id, invoice)
