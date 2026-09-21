# -*- coding: utf-8 -*-
import base64
import json
from datetime import datetime, time

from odoo import api, fields, models, tools

from .sunat_tables import TABLA_12, VALUATION_METHOD_MAP


class L10nPeStockPle(models.Model):
    """Modelo de reporte (vista SQL) del Formato 13.1 de SUNAT.

    Se construye a partir de las capas de valoracion de inventario
    (stock.valuation.layer), que son la fuente fiable de cantidades y
    costos valorizados en Odoo. Cada linea de la vista es una capa de
    valoracion con su saldo acumulado (window functions).
    """

    _name = "l10n.pe.stock.ple"
    _description = "Registro de Inventario Permanente Valorizado (Formato 13.1)"
    _auto = False
    _order = "product_id, date, id"

    date = fields.Datetime(string="Fecha emisión", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", readonly=True)
    product_tmpl_id = fields.Many2one(
        "product.template", string="Plantilla de producto", readonly=True
    )
    categ_id = fields.Many2one(
        "product.category", string="Categoría", readonly=True
    )
    location_id = fields.Many2one(
        "stock.location", string="Establecimiento", readonly=True
    )
    picking_id = fields.Many2one("stock.picking", string="Traslado", readonly=True)
    document_type_id = fields.Many2one(
        "l10n_latam.document.type", string="Tipo de documento", readonly=True
    )
    document_ref = fields.Char(string="Serie-Número", readonly=True)
    operation_type = fields.Selection(
        selection=TABLA_12, string="Tipo de operación", readonly=True
    )
    product_uom_id = fields.Many2one(
        "uom.uom", string="Unidad de medida", readonly=True
    )

    # Entradas
    qty_in = fields.Float(string="Entradas Cant.", readonly=True)
    cost_in_unit = fields.Float(string="Entradas C. Unit.", readonly=True)
    cost_in_total = fields.Float(string="Entradas C. Total", readonly=True)

    # Salidas
    qty_out = fields.Float(string="Salidas Cant.", readonly=True)
    cost_out_unit = fields.Float(string="Salidas C. Unit.", readonly=True)
    cost_out_total = fields.Float(string="Salidas C. Total", readonly=True)

    # Saldo final acumulado
    qty_balance = fields.Float(string="Saldo Cant.", readonly=True)
    cost_balance_unit = fields.Float(string="Saldo C. Unit.", readonly=True)
    cost_balance_total = fields.Float(string="Saldo C. Total", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # El Formato 13.1 es un kardex POR ESTABLECIMIENTO (almacen): el saldo
        # acumulado se particiona por producto, compania y ubicacion para que
        # cada almacen lleve su propio saldo. El orden cronologico usa la fecha
        # del documento con desempate por id de la capa (determinista). El costo
        # unitario del saldo se calcula en el SELECT externo porque PostgreSQL
        # no permite referenciar el alias de un window en el mismo nivel SELECT.
        # La expresion de ubicacion se repite en el PARTITION BY (no se puede
        # usar el alias de columna dentro de la misma window).
        self.env.cr.execute(
            """
            CREATE VIEW %s AS (
                SELECT
                    sub.*,
                    CASE
                        WHEN ABS(sub.qty_balance) > 0.00001
                        THEN sub.cost_balance_total / sub.qty_balance
                        ELSE 0
                    END AS cost_balance_unit
                FROM (
                    SELECT
                        svl.id AS id,
                        COALESCE(sp.date_done, sm.date, svl.create_date) AS date,
                        svl.company_id AS company_id,
                        svl.product_id AS product_id,
                        pt.id AS product_tmpl_id,
                        pt.categ_id AS categ_id,
                        CASE
                            WHEN svl.quantity >= 0 THEN sm.location_dest_id
                            ELSE sm.location_id
                        END AS location_id,
                        sm.picking_id AS picking_id,
                        sp.l10n_pe_ple_document_type_id AS document_type_id,
                        sp.l10n_pe_ple_document_ref AS document_ref,
                        sp.l10n_pe_ple_operation_type AS operation_type,
                        pt.uom_id AS product_uom_id,
                        CASE WHEN svl.quantity >= 0 THEN svl.quantity ELSE 0 END
                            AS qty_in,
                        CASE WHEN svl.quantity >= 0 THEN svl.unit_cost ELSE 0 END
                            AS cost_in_unit,
                        CASE WHEN svl.quantity >= 0 THEN svl.value ELSE 0 END
                            AS cost_in_total,
                        CASE WHEN svl.quantity < 0 THEN -svl.quantity ELSE 0 END
                            AS qty_out,
                        CASE WHEN svl.quantity < 0 THEN svl.unit_cost ELSE 0 END
                            AS cost_out_unit,
                        CASE WHEN svl.quantity < 0 THEN -svl.value ELSE 0 END
                            AS cost_out_total,
                        SUM(svl.quantity) OVER (
                            PARTITION BY svl.product_id, svl.company_id,
                                CASE
                                    WHEN svl.quantity >= 0 THEN sm.location_dest_id
                                    ELSE sm.location_id
                                END
                            ORDER BY
                                COALESCE(sp.date_done, sm.date, svl.create_date),
                                svl.id
                        ) AS qty_balance,
                        SUM(svl.value) OVER (
                            PARTITION BY svl.product_id, svl.company_id,
                                CASE
                                    WHEN svl.quantity >= 0 THEN sm.location_dest_id
                                    ELSE sm.location_id
                                END
                            ORDER BY
                                COALESCE(sp.date_done, sm.date, svl.create_date),
                                svl.id
                        ) AS cost_balance_total
                    FROM stock_valuation_layer svl
                    JOIN stock_move sm ON svl.stock_move_id = sm.id
                    LEFT JOIN stock_picking sp ON sm.picking_id = sp.id
                    JOIN product_product pp ON svl.product_id = pp.id
                    JOIN product_template pt ON pp.product_tmpl_id = pt.id
                ) sub
            )
            """
            % self._table
        )

    def _l10n_pe_valuation_method_label(self):
        """Devuelve la etiqueta del metodo de valuacion (Tabla 14 SUNAT)
        a partir del metodo de costo de la categoria del producto."""
        self.ensure_one()
        # property_cost_method es company-dependent: se lee en el contexto de la
        # compania del registro para no tomar el metodo de la compania del usuario.
        cost_method = self.categ_id.with_company(
            self.company_id
        ).property_cost_method
        return VALUATION_METHOD_MAP.get(cost_method, "9 Otros")

    # ------------------------------------------------------------------
    # Calculo del Formato 13.1 con saldo inicial (Tabla 12 = 16)
    # ------------------------------------------------------------------
    @api.model
    def _l10n_pe_period_lines(self, base_domain, date_from, date_to):
        """Lineas de la vista dentro del periodo [date_from, date_to]."""
        df = fields.Date.to_date(date_from)
        dt = fields.Date.to_date(date_to)
        domain = list(base_domain) + [
            ("date", ">=", datetime.combine(df, time.min)),
            ("date", "<=", datetime.combine(dt, time.max)),
        ]
        return self.search(domain, order="product_id, location_id, date, id")

    @api.model
    def _l10n_pe_compute_openings(self, base_domain, date_from):
        """Saldo inicial por (producto, establecimiento) anterior a date_from.

        El Formato 13.1 exige consignar el saldo inicial en la columna de
        Entradas (Tabla 12 codigo 16). Se acumula todo el historico previo al
        inicio del periodo. Devuelve {(product_id, location_id): {qty,value,unit}}.
        """
        df = fields.Date.to_date(date_from)
        domain = list(base_domain) + [
            ("date", "<", datetime.combine(df, time.min))
        ]
        groups = self.read_group(
            domain,
            ["qty_in:sum", "qty_out:sum", "cost_in_total:sum", "cost_out_total:sum"],
            ["product_id", "location_id"],
            lazy=False,
        )
        openings = {}
        for grp in groups:
            product = grp.get("product_id")
            if not product:
                continue
            location = grp.get("location_id")
            qty = (grp.get("qty_in") or 0.0) - (grp.get("qty_out") or 0.0)
            value = (grp.get("cost_in_total") or 0.0) - (
                grp.get("cost_out_total") or 0.0
            )
            key = (product[0], location[0] if location else False)
            openings[key] = {
                "qty": qty,
                "value": value,
                "unit": value / qty if qty else 0.0,
            }
        return openings

    @api.model
    def _l10n_pe_build_groups(self, lines, openings, company):
        """Estructura agrupada por (existencia, establecimiento) para el
        reporte PDF/Excel: cabecera, fila de saldo inicial, movimientos y
        totales. Reutilizado por el modelo de reporte y el controller xlsx.
        `openings` puede ser {} (impresion analitica sin saldo inicial)."""
        keys = []
        for line in lines:
            key = (line.product_id.id, line.location_id.id)
            if key not in keys:
                keys.append(key)
        for key in openings:
            if key not in keys:
                keys.append(key)
        product_model = self.env["product.product"]
        location_model = self.env["stock.location"]
        groups = []
        for pid, lid in keys:
            product = product_model.browse(pid)
            location = location_model.browse(lid) if lid else location_model
            grp = lines.filtered(
                lambda l, p=pid, x=lid: l.product_id.id == p
                and l.location_id.id == x
            ).sorted(lambda l: (l.date, l.id))
            opening = openings.get((pid, lid))
            opening_qty = opening["qty"] if opening else 0.0
            opening_val = opening["value"] if opening else 0.0
            cost_method = product.categ_id.with_company(
                company
            ).property_cost_method
            if grp:
                last = grp[-1]
                bal_qty, bal_total = last.qty_balance, last.cost_balance_total
            else:
                bal_qty, bal_total = opening_qty, opening_val
            groups.append(
                {
                    "product": product,
                    "location": location,
                    "method_label": VALUATION_METHOD_MAP.get(
                        cost_method, "9 Otros"
                    ),
                    "opening": opening,
                    "lines": grp,
                    "tot_qty_in": opening_qty + sum(grp.mapped("qty_in")),
                    "tot_cost_in": opening_val + sum(grp.mapped("cost_in_total")),
                    "tot_qty_out": sum(grp.mapped("qty_out")),
                    "tot_cost_out": sum(grp.mapped("cost_out_total")),
                    "bal_qty": bal_qty,
                    "bal_total": bal_total,
                }
            )
        return groups

    def action_export_xlsx(self):
        """Accion de servidor (binding en el menu Accion de la lista) que
        exporta a Excel via el controller. Prioriza la seleccion del usuario
        (active_ids); si no hay seleccion explicita, exporta el conjunto
        filtrado en pantalla (active_domain) para no truncar la URL ni exponer
        toda la tabla."""
        ctx = self.env.context
        active_ids = ctx.get("active_ids")
        # Cuando el usuario marca filas concretas en la lista, active_ids trae
        # solo esas; si no marca nada, Odoo no envia una seleccion util y se usa
        # el dominio de busqueda actual.
        if active_ids and len(active_ids) <= 1000:
            params = "ids=%s" % ",".join(str(i) for i in active_ids)
        else:
            domain = ctx.get("active_domain") or []
            encoded = base64.urlsafe_b64encode(
                json.dumps(domain).encode()
            ).decode()
            params = "domain=%s" % encoded
        return {
            "type": "ir.actions.act_url",
            "url": "/l10n_pe_stock_ple/export/xlsx?%s" % params,
            "target": "self",
        }
