"""Genera el registro de compras comparable contra la propuesta SIRE (RCE)
desde ``account.move``.

Calco de ``tgr_sire_rvie/models/account_move.py``, cambiando
venta->compra: filtra ``in_invoice``/``in_refund`` en vez de
``out_invoice``/``out_refund``, y el "partner" de cada fila es el
proveedor, no el cliente. Ver plan aprobado, "Extensión de account.move":
simplificación explícita del MVP -- no distingue destino de la operación/
uso del crédito fiscal (eso es FV0621, fuera de alcance), solo calcula una
única base "gravada".
"""

import calendar
import logging
from datetime import date

from odoo import api, models

from .sunat_rce_tables import (
    SIRE_RCE_TAX_GROUP_BUCKET,
    SIRE_RCE_TAX_GROUP_PRIORITY,
    SIRE_RCE_TAX_LINE_BUCKET,
)

_logger = logging.getLogger(__name__)

# move_type que participan del Registro de Compras Electrónico (RCE).
SIRE_RCE_MOVE_TYPES = ("in_invoice", "in_refund")


class AccountMove(models.Model):
    _inherit = "account.move"

    # -- parseo de serie/numero ----------------------------------------------
    def _sire_rce_parse_document_number(self):
        """(serie, numero) de ``self.name`` -- idéntico a
        ``sire.rvie.models.account_move._sire_rvie_parse_document_number``:
        el parseo de serie/número desde ``self.name`` no depende del
        sentido de la operación (venta/compra), depende del formato del
        documento (``l10n_latam_invoice_document``)."""
        self.ensure_one()
        name = (self.name or "").strip()
        if not name:
            return False, False
        if "-" not in name:
            return False, name
        serie_part, numero = name.split("-", 1)
        serie = serie_part.replace(" ", "")[-4:]
        return serie or False, numero or False

    # -- clasificacion de montos ----------------------------------------------
    def _sire_rce_amount_buckets(self):
        """Bases imponibles (gravada/exonerada/inafecta) e impuestos
        (igv/isc/otros) de ``self``, clasificados por ``account.tax.group``
        -- ver ``sunat_rce_tables.SIRE_RCE_TAX_GROUP_BUCKET``.

        Simplificación explícita del MVP (ver plan aprobado): el registro
        de compras SUNAT distingue crédito fiscal "destinado a operaciones
        gravadas" vs "no gravadas" (prorrata, FV0621) -- fuera de alcance.
        Aquí solo se calcula una única base "gravada" sin esa distinción,
        igual que RVIE simplificó su propio registro. Sin bucket
        "exportación" (no aplica a compras).

        Los importes usan ``+balance`` (a diferencia de RVIE, que usa
        ``-balance``): en una compra la linea de producto/impuesto (gasto)
        queda en DEBITO (balance positivo) para una factura de proveedor,
        asi que ``+balance`` da el monto en positivo para una factura y en
        negativo para una nota de credito de proveedor -- lo opuesto de una
        venta, donde la linea de producto queda en credito.
        """
        self.ensure_one()
        buckets = {
            "gravada": 0.0,
            "exonerada": 0.0,
            "inafecta": 0.0,
            "sin_clasificar": 0.0,
            "igv": 0.0,
            "isc": 0.0,
            "otros": 0.0,
        }
        for line in self.line_ids.filtered(lambda ln: ln.display_type == "product"):
            group_name = self._sire_rce_priority_tax_group(line.tax_ids.tax_group_id)
            bucket = SIRE_RCE_TAX_GROUP_BUCKET.get(group_name, "sin_clasificar")
            buckets[bucket] += line.balance
        for line in self.line_ids.filtered(lambda ln: ln.display_type == "tax"):
            group_name = line.tax_line_id.tax_group_id.name
            bucket = SIRE_RCE_TAX_LINE_BUCKET.get(group_name, "otros")
            buckets[bucket] += line.balance
        return buckets

    @staticmethod
    def _sire_rce_priority_tax_group(tax_groups):
        """Del conjunto de ``account.tax.group`` de una linea, el de mayor
        prioridad segun ``SIRE_RCE_TAX_GROUP_PRIORITY`` (evita duplicar la
        base imponible cuando una linea lleva mas de un impuesto). ``None``
        si la linea no lleva ningun grupo reconocido."""
        names = set(tax_groups.mapped("name"))
        for candidate in SIRE_RCE_TAX_GROUP_PRIORITY:
            if candidate in names:
                return candidate
        return None

    # -- fila del registro ----------------------------------------------------
    def _sire_rce_build_register_row(self):
        """Una fila del registro de compras comparable para ``self``
        (``account.move``). El "partner" es el proveedor -- ver plan
        aprobado, "Extensión de account.move".

        Limitación conocida del MVP: columnas del registro de compras SUNAT
        que exceden lo que se modela aquí (clasificación de destino de la
        operación/uso del crédito fiscal, percepciones, detracciones) no se
        mapean.
        """
        self.ensure_one()
        serie, numero = self._sire_rce_parse_document_number()
        buckets = self._sire_rce_amount_buckets()
        partner = self.commercial_partner_id
        id_type = partner.l10n_latam_identification_type_id

        # Referencia NC/ND: reversed_entry_id (nota de credito estandar) o
        # debit_origin_id (nota de debito, campo de account_debit_note --
        # dependencia transitiva de l10n_pe, ver __manifest__.py).
        ref_move = self.reversed_entry_id or self.debit_origin_id
        ref_tipo_cp = ref_serie = ref_numero = False
        ref_fecha = False
        if ref_move:
            ref_serie, ref_numero = ref_move._sire_rce_parse_document_number()
            ref_tipo_cp = ref_move.l10n_latam_document_type_id.code or False
            ref_fecha = ref_move.invoice_date

        exchange_rate = False
        if (
            self.currency_id != self.company_id.currency_id
            and self.invoice_currency_rate
        ):
            # Odoo guarda el factor empresa -> comprobante; SUNAT pide soles
            # por unidad de moneda extranjera.
            exchange_rate = round(1 / self.invoice_currency_rate, 3)

        return {
            "move_id": self.id,
            "tipo_cp": self.l10n_latam_document_type_id.code or False,
            "serie": serie,
            "numero": numero,
            "fecha_emision": self.invoice_date,
            "partner_id_type": id_type.l10n_pe_vat_code or False,
            "partner_vat": partner.vat or False,
            "partner_name": partner.name or False,
            "amount_taxed": round(buckets["gravada"], 2),
            "amount_exempt": round(buckets["exonerada"], 2),
            "amount_unaffected": round(buckets["inafecta"], 2),
            "amount_isc": round(buckets["isc"], 2),
            "amount_igv": round(buckets["igv"], 2),
            "amount_other_taxes": round(buckets["otros"], 2),
            "amount_unclassified": round(buckets["sin_clasificar"], 2),
            # Odoo.amount_total_signed es NEGATIVO para una factura de
            # proveedor (in_invoice) y POSITIVO para una nota de credito de
            # proveedor (in_refund) -- ver account.move._compute_amount:
            # `amount_total_signed = -total`, con `total` ya en balance de
            # debito (positivo) para in_invoice. Se invierte el signo para
            # que el registro de compras muestre positivo en una factura
            # normal y negativo en una nota de credito, igual convencion
            # que usa RVIE para su registro de ventas.
            "amount_total": round(-self.amount_total_signed, 2),
            "currency_code": self.currency_id.name,
            "exchange_rate": exchange_rate,
            "ref_fecha_emision": ref_fecha,
            "ref_tipo_cp": ref_tipo_cp,
            "ref_serie": ref_serie,
            "ref_numero": ref_numero,
        }

    # -- registro completo de un periodo --------------------------------------
    @api.model
    def _sire_rce_get_compras_register(self, company, periodo_tributario):
        """Registro de compras comparable del periodo ``periodo_tributario``
        (``AAAAMM``) de ``company``, una fila (dict) por comprobante.

        Filtro: ``state = 'posted'``, ``move_type in ('in_invoice',
        'in_refund')``, ``invoice_date`` dentro del periodo.

        PROBADO EN VIVO (periodo 202608, o18_cms) -- BUG REAL corregido: a
        diferencia de lo que se asumió al copiar el patrón de RVIE, el campo
        ``l10n_pe_edi_is_required`` (módulo externo ``l10n_pe_edi``) NO
        aplica "por defecto True" a facturas de proveedor -- su cómputo real
        es ``move.is_sale_document() and ...``, es decir, es SIEMPRE
        ``False`` para ``in_invoice``/``in_refund`` (mide la obligación de
        EMITIR el comprobante electrónicamente, no de recibirlo). Usarlo
        aquí filtraba TODAS las facturas de compra a cero filas. No existe
        un campo equivalente para "obligación de e-invoicing del emisor" que
        Odoo pueda evaluar del lado del comprador, así que este filtro
        simplemente no se aplica al registro de compras.
        """
        date_from, date_to = self._sire_rce_period_bounds(periodo_tributario)
        moves = self.search(
            [
                ("company_id", "=", company.id),
                ("state", "=", "posted"),
                ("move_type", "in", SIRE_RCE_MOVE_TYPES),
                ("invoice_date", ">=", date_from),
                ("invoice_date", "<=", date_to),
            ]
        )
        return [move._sire_rce_build_register_row() for move in moves]

    @staticmethod
    def _sire_rce_period_bounds(periodo_tributario):
        """(fecha_desde, fecha_hasta) del periodo ``AAAAMM``. Duplicado
        local (no se importa desde ``tgr_sire_rvie``): son módulos
        hermanos, ninguno depende del otro."""
        year = int(periodo_tributario[:4])
        month = int(periodo_tributario[4:6])
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)
