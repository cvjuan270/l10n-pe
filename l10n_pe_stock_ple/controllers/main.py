# -*- coding: utf-8 -*-
import base64
import io
import json

from odoo import _, fields, http
from odoo.http import content_disposition, request

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class L10nPeStockPleController(http.Controller):
    """Exportacion del Formato 13.1 a Excel usando xlsxwriter nativo.

    Dos modos:
    - `data` (asistente de periodo): incluye la fila de saldo inicial
      (Tabla 12 = 16) por existencia/establecimiento. Reporte oficial.
    - `ids`/`domain` (desde la lista): exportacion analitica sin saldo inicial.
    """

    def _line_values(self, rec):
        return [
            rec.date and rec.date.strftime("%d/%m/%Y") or "",
            rec.product_id.default_code or "",
            rec.product_id.display_name or "",
            rec.product_uom_id.l10n_pe_sunat_code or "",
            rec.product_tmpl_id.l10n_pe_existence_type or "",
            rec.document_type_id.code or "",
            rec.document_ref or "",
            dict(rec._fields["operation_type"].selection).get(
                rec.operation_type, ""
            ),
            rec.qty_in,
            rec.cost_in_unit,
            rec.cost_in_total,
            rec.qty_out,
            rec.cost_out_unit,
            rec.cost_out_total,
            rec.qty_balance,
            rec.cost_balance_unit,
            rec.cost_balance_total,
        ]

    def _opening_values(self, product, opening, date_from):
        date_label = fields.Date.to_date(date_from)
        return [
            date_label and date_label.strftime("%d/%m/%Y") or "",
            product.default_code or "",
            product.display_name or "",
            product.uom_id.l10n_pe_sunat_code or "",
            product.l10n_pe_existence_type or "",
            "",
            "",
            "16 Saldo inicial",
            opening["qty"],
            opening["unit"],
            opening["value"],
            0.0,
            0.0,
            0.0,
            opening["qty"],
            opening["unit"],
            opening["value"],
        ]

    @http.route(
        "/l10n_pe_stock_ple/export/xlsx",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def export_xlsx(self, ids=None, domain=None, data=None, **kwargs):
        if xlsxwriter is None:
            return request.make_response(
                _("La librería 'xlsxwriter' no está instalada en el servidor."),
                headers=[("Content-Type", "text/plain; charset=utf-8")],
            )

        ple_model = request.env["l10n.pe.stock.ple"]
        company = request.env.company
        period_label = ""
        rows = []

        if data is not None:
            # Modo oficial: con saldo inicial (Tabla 12 = 16).
            try:
                payload = json.loads(base64.urlsafe_b64decode(data).decode())
            except (ValueError, TypeError):
                payload = None
            if not isinstance(payload, dict) or not payload.get("date_from"):
                return request.make_response(
                    _("Parámetros del reporte inválidos."),
                    headers=[("Content-Type", "text/plain; charset=utf-8")],
                )
            base_domain = payload.get("base_domain") or []
            date_from = payload["date_from"]
            date_to = payload["date_to"]
            if payload.get("company_id"):
                company = request.env["res.company"].browse(
                    payload["company_id"]
                )
            period_lines = ple_model._l10n_pe_period_lines(
                base_domain, date_from, date_to
            )
            openings = ple_model._l10n_pe_compute_openings(base_domain, date_from)
            groups = ple_model._l10n_pe_build_groups(
                period_lines, openings, company
            )
            for grp in groups:
                if grp["opening"]:
                    rows.append(
                        self._opening_values(
                            grp["product"], grp["opening"], date_from
                        )
                    )
                rows.extend(self._line_values(line) for line in grp["lines"])
            period_label = "%s a %s" % (date_from, date_to)
        else:
            # Modo analitico: registros seleccionados / filtrados (sin saldo
            # inicial). Respeta ir.model.access e ir.rule (sin sudo).
            if ids:
                rec_ids = [
                    int(i) for i in ids.split(",") if i.strip().isdigit()
                ]
                records = ple_model.browse(rec_ids).exists()
            elif domain is not None:
                try:
                    parsed = json.loads(base64.urlsafe_b64decode(domain).decode())
                except (ValueError, TypeError):
                    parsed = None
                if not isinstance(parsed, list):
                    return request.make_response(
                        _("Parámetro de filtro inválido."),
                        headers=[("Content-Type", "text/plain; charset=utf-8")],
                    )
                records = ple_model.search(parsed)
            else:
                return request.make_response(
                    _("Indique los registros a exportar."),
                    headers=[("Content-Type", "text/plain; charset=utf-8")],
                )
            epoch = fields.Datetime.from_string("1900-01-01 00:00:00")
            records = records.sorted(
                key=lambda r: (r.product_id.id, r.date or epoch, r.id)
            )
            dates = records.filtered(lambda r: r.date).mapped("date")
            if dates:
                period_label = "%s a %s" % (
                    min(dates).strftime("%d/%m/%Y"),
                    max(dates).strftime("%d/%m/%Y"),
                )
            rows = [self._line_values(rec) for rec in records]

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Formato 13.1")

        bold = workbook.add_format({"bold": True})
        header_fmt = workbook.add_format(
            {"bold": True, "border": 1, "bg_color": "#D9E1F2", "align": "center"}
        )
        cell_fmt = workbook.add_format({"border": 1})
        num_fmt = workbook.add_format({"border": 1, "num_format": "#,##0.0000"})

        row = 0
        sheet.write(
            row,
            0,
            "REGISTRO DE INVENTARIO PERMANENTE VALORIZADO - "
            "DETALLE DEL INVENTARIO VALORIZADO",
            bold,
        )
        row += 1
        sheet.write(row, 0, _("Período: %s") % period_label)
        row += 1
        sheet.write(row, 0, _("RUC: %s") % (company.vat or ""))
        row += 1
        sheet.write(row, 0, _("Razón Social: %s") % (company.name or ""))
        row += 2

        headers = [
            _("Fecha"),
            _("Código existencia"),
            _("Descripción"),
            _("U.M. (T6)"),
            _("Tipo existencia (T5)"),
            _("Tipo doc."),
            _("Serie-Número"),
            _("Tipo operación"),
            _("Entradas Cant."),
            _("Entradas C.Unit."),
            _("Entradas C.Total"),
            _("Salidas Cant."),
            _("Salidas C.Unit."),
            _("Salidas C.Total"),
            _("Saldo Cant."),
            _("Saldo C.Unit."),
            _("Saldo C.Total"),
        ]
        for col, head in enumerate(headers):
            sheet.write(row, col, head, header_fmt)
        row += 1

        num_cols = set(range(8, 17))
        for values in rows:
            for col, value in enumerate(values):
                fmt = num_fmt if col in num_cols else cell_fmt
                sheet.write(row, col, value, fmt)
            row += 1

        sheet.set_column(0, 0, 12)
        sheet.set_column(2, 2, 30)
        sheet.set_column(8, 16, 14)

        workbook.close()
        output.seek(0)
        content = output.read()
        filename = "Formato_13.1_Inventario_Valorizado.xlsx"
        return request.make_response(
            content,
            headers=[
                (
                    "Content-Type",
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet",
                ),
                ("Content-Disposition", content_disposition(filename)),
            ],
        )
