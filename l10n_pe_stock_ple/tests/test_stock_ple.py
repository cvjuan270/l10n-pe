# -*- coding: utf-8 -*-
import base64
import json
from datetime import timedelta

from odoo import fields
from odoo.addons.stock_account.tests.test_stockvaluationlayer import (
    TestStockValuationCommon,
)
from odoo.exceptions import ValidationError
from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestStockPle(TestStockValuationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Metodo de costo promedio ponderado para resultados deterministas.
        cls.product1.product_tmpl_id.categ_id.property_cost_method = "average"

    def test_ple_balance_accumulates(self):
        """Dos entradas valorizadas deben generar registros en la vista y el
        saldo acumulado debe sumar correctamente."""
        self._make_in_move(self.product1, 10, unit_cost=5)
        self._make_in_move(self.product1, 10, unit_cost=5)

        records = self.env["l10n.pe.stock.ple"].search(
            [("product_id", "=", self.product1.id)], order="date, id"
        )
        self.assertEqual(
            len(records), 2, "Deben existir 2 lineas (una por capa de valoracion)."
        )
        self.assertEqual(records[0].qty_in, 10)
        self.assertEqual(records[0].qty_balance, 10)
        # El saldo acumulado de la segunda capa es 20.
        self.assertEqual(records[1].qty_balance, 20)
        self.assertEqual(records[1].cost_balance_total, 100)
        self.assertAlmostEqual(records[1].cost_balance_unit, 5.0)

    def test_ple_in_and_out(self):
        """Una entrada y una salida: la salida se refleja en qty_out y el
        saldo baja."""
        self._make_in_move(self.product1, 10, unit_cost=5)
        self._make_out_move(self.product1, 4)

        records = self.env["l10n.pe.stock.ple"].search(
            [("product_id", "=", self.product1.id)], order="date, id"
        )
        self.assertEqual(len(records), 2)
        out_line = records[1]
        self.assertEqual(out_line.qty_out, 4)
        self.assertEqual(out_line.qty_in, 0)
        self.assertEqual(out_line.qty_balance, 6)

    def test_document_ref_normalization(self):
        """La normalizacion rellena el numero con ceros a la izquierda."""
        Picking = self.env["stock.picking"]
        self.assertEqual(
            Picking._l10n_pe_normalize_document_ref("AB12-1"), "AB12-000001"
        )
        self.assertEqual(
            Picking._l10n_pe_normalize_document_ref("ab12-123"), "AB12-000123"
        )
        self.assertEqual(
            Picking._l10n_pe_normalize_document_ref("AB12-000456"), "AB12-000456"
        )

    def test_document_ref_invalid(self):
        """Un valor que no cumple el patron lanza ValidationError."""
        Picking = self.env["stock.picking"]
        with self.assertRaises(ValidationError):
            Picking._l10n_pe_normalize_document_ref("ABC-1")
        with self.assertRaises(ValidationError):
            Picking._l10n_pe_normalize_document_ref("AB12-1234567")
        with self.assertRaises(ValidationError):
            Picking._l10n_pe_normalize_document_ref("AB12_000001")

    def test_valuation_method_label(self):
        """El metodo de valuacion se mapea correctamente (Tabla 14)."""
        self._make_in_move(self.product1, 5, unit_cost=2)
        record = self.env["l10n.pe.stock.ple"].search(
            [("product_id", "=", self.product1.id)], limit=1
        )
        self.assertEqual(
            record._l10n_pe_valuation_method_label(), "1 Promedio ponderado"
        )

    def test_pdf_report_renders(self):
        """El reporte QWeb se renderiza sin errores de plantilla."""
        self._make_in_move(self.product1, 10, unit_cost=5)
        self._make_out_move(self.product1, 3)
        records = self.env["l10n.pe.stock.ple"].search(
            [("product_id", "=", self.product1.id)]
        )
        html, _dummy = self.env["ir.actions.report"]._render_qweb_html(
            "l10n_pe_stock_ple.report_stock_ple", records.ids
        )
        self.assertIn(b"INVENTARIO PERMANENTE VALORIZADO", html)

    def test_saldo_inicial_openings(self):
        """El saldo inicial acumula el histórico anterior a 'date_from'."""
        self._make_in_move(self.product1, 10, unit_cost=5)
        self._make_in_move(self.product1, 6, unit_cost=5)
        # date_from mañana: todos los movimientos quedan como saldo inicial.
        tomorrow = fields.Date.today() + timedelta(days=1)
        Ple = self.env["l10n.pe.stock.ple"]
        openings = Ple._l10n_pe_compute_openings(
            [("product_id", "=", self.product1.id)], tomorrow
        )
        self.assertEqual(sum(o["qty"] for o in openings.values()), 16)
        self.assertEqual(sum(o["value"] for o in openings.values()), 80)

    def test_report_values_include_opening_row(self):
        """El reporte oficial (con periodo) emite la fila de saldo inicial."""
        self._make_in_move(self.product1, 4, unit_cost=7)
        tomorrow = fields.Date.today() + timedelta(days=1)
        data = {
            "date_from": fields.Date.to_string(tomorrow),
            "date_to": fields.Date.to_string(tomorrow + timedelta(days=1)),
            "base_domain": [("product_id", "=", self.product1.id)],
            "company_id": self.env.company.id,
        }
        report = self.env["report.l10n_pe_stock_ple.report_stock_ple"]
        values = report._get_report_values([], data)
        groups = values["groups"]
        self.assertTrue(groups, "Debe existir al menos un grupo con saldo inicial.")
        self.assertTrue(groups[0]["opening"])
        self.assertEqual(groups[0]["opening"]["qty"], 4)
        # El PDF se renderiza e incluye la etiqueta de saldo inicial.
        html, _dummy = self.env["ir.actions.report"]._render_qweb_html(
            "l10n_pe_stock_ple.report_stock_ple", [], data=data
        )
        self.assertIn("16 Saldo inicial".encode(), html)


@tagged("post_install", "-at_install")
class TestStockPleExport(HttpCase, TestStockValuationCommon):
    def test_xlsx_export_controller(self):
        """El controller de export Excel responde un .xlsx valido."""
        self.product1.product_tmpl_id.categ_id.property_cost_method = "average"
        self._make_in_move(self.product1, 8, unit_cost=4)
        # Fija una contrasena conocida (revertida al cerrar el modo de prueba).
        admin = self.env.ref("base.user_admin")
        admin.password = "ple_test_pwd"
        self.authenticate(admin.login, "ple_test_pwd")
        domain = json.dumps([("product_id", "=", self.product1.id)])
        encoded = base64.urlsafe_b64encode(domain.encode()).decode()
        response = self.url_open(
            "/l10n_pe_stock_ple/export/xlsx?domain=%s" % encoded
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "spreadsheetml.sheet", response.headers.get("Content-Type", "")
        )
        # Firma de archivo xlsx (zip): comienza con 'PK'.
        self.assertEqual(response.content[:2], b"PK")
