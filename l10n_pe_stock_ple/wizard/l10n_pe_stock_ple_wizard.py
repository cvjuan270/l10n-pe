# -*- coding: utf-8 -*-
import base64
import json
from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nPeStockPleWizard(models.TransientModel):
    _name = "l10n.pe.stock.ple.wizard"
    _description = "Asistente Formato 13.1 - Inventario Permanente Valorizado"

    @api.model
    def _default_date_from(self):
        return fields.Date.today().replace(day=1)

    date_from = fields.Date(
        string="Desde", required=True, default=_default_date_from
    )
    date_to = fields.Date(string="Hasta", required=True, default=fields.Date.today)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Establecimiento",
        domain="[('usage', '=', 'internal')]",
        help="Opcional: limita el reporte a un almacén/ubicación.",
    )
    product_id = fields.Many2one("product.product", string="Producto")
    categ_id = fields.Many2one("product.category", string="Categoría de producto")

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and (
                wizard.date_from > wizard.date_to
            ):
                raise UserError(
                    _("La fecha 'Desde' no puede ser posterior a 'Hasta'.")
                )

    def _base_domain(self):
        self.ensure_one()
        domain = [("company_id", "=", self.company_id.id)]
        if self.location_id:
            domain.append(("location_id", "=", self.location_id.id))
        if self.product_id:
            domain.append(("product_id", "=", self.product_id.id))
        if self.categ_id:
            domain.append(("categ_id", "child_of", self.categ_id.id))
        return domain

    def _prepare_data(self):
        self.ensure_one()
        return {
            "date_from": fields.Date.to_string(self.date_from),
            "date_to": fields.Date.to_string(self.date_to),
            "base_domain": self._base_domain(),
            "company_id": self.company_id.id,
        }

    def action_view_list(self):
        """Abre la vista lista filtrada por el periodo (análisis en pantalla)."""
        self.ensure_one()
        domain = self._base_domain() + [
            ("date", ">=", datetime.combine(self.date_from, time.min)),
            ("date", "<=", datetime.combine(self.date_to, time.max)),
        ]
        action = self.env["ir.actions.actions"]._for_xml_id(
            "l10n_pe_stock_ple.action_l10n_pe_stock_ple"
        )
        action["domain"] = domain
        # Sin el filtro por defecto "Este mes" para respetar el periodo elegido.
        action["context"] = {"group_by": ["product_id", "location_id"]}
        return action

    def action_print_pdf(self):
        """Genera el PDF oficial del Formato 13.1 (con saldo inicial)."""
        self.ensure_one()
        return self.env.ref(
            "l10n_pe_stock_ple.action_report_l10n_pe_stock_ple"
        ).report_action(self, data=self._prepare_data())

    def action_export_xlsx(self):
        """Genera el Excel oficial (con saldo inicial) vía el controller."""
        self.ensure_one()
        encoded = base64.urlsafe_b64encode(
            json.dumps(self._prepare_data()).encode()
        ).decode()
        return {
            "type": "ir.actions.act_url",
            "url": "/l10n_pe_stock_ple/export/xlsx?data=%s" % encoded,
            "target": "self",
        }
