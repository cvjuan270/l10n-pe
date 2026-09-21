# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ReportStockPle(models.AbstractModel):
    """Provee los datos del Formato 13.1 al QWeb.

    - Llamado desde el asistente (con `data` de periodo): incluye la fila de
      saldo inicial (Tabla 12 = 16) por existencia/establecimiento.
    - Llamado desde la lista (Imprimir, sin `data`): impresion analitica de los
      registros seleccionados, sin saldo inicial.
    """

    _name = "report.l10n_pe_stock_ple.report_stock_ple"
    _description = "Formato 13.1 - Inventario Permanente Valorizado (datos)"

    @api.model
    def _get_report_values(self, docids, data=None):
        ple_model = self.env["l10n.pe.stock.ple"]
        data = data or {}
        if data.get("date_from"):
            company = self.env["res.company"].browse(
                data.get("company_id")
            ) or self.env.company
            base_domain = data.get("base_domain") or []
            date_from = data["date_from"]
            date_to = data["date_to"]
            lines = ple_model._l10n_pe_period_lines(
                base_domain, date_from, date_to
            )
            openings = ple_model._l10n_pe_compute_openings(base_domain, date_from)
        else:
            lines = ple_model.browse(docids or [])
            openings = {}
            company = lines[:1].company_id or self.env.company
            dates = lines.filtered("date").mapped("date")
            date_from = fields.Date.to_string(min(dates).date()) if dates else False
            date_to = fields.Date.to_string(max(dates).date()) if dates else False

        groups = ple_model._l10n_pe_build_groups(lines, openings, company)
        return {
            "doc_ids": lines.ids,
            "doc_model": "l10n.pe.stock.ple",
            "docs": lines,
            "groups": groups,
            "company": company,
            "date_from": date_from,
            "date_to": date_to,
        }
