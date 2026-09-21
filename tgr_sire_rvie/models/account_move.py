"""Genera el registro de ventas comparable contra la propuesta SIRE (RVIE)
desde ``account.move``.

Porta el CRITERIO de mapeo de
``docs/tarea_registro_compras_ventas/formato_14_1_registro_ventas.sql``
(reporte SQL puntual de emergencia, verificado contra datos reales) a
metodos Python/ORM normales -- ver decision de diseno del plan aprobado,
seccion "Comparacion propuesta SUNAT vs. Odoo": ningun modulo de este repo
usa SQL crudo para logica de negocio, salvo ``init()`` puntual para indices.
"""

import calendar
import logging
from datetime import date

from odoo import api, models

from .sunat_rvie_tables import (
    SIRE_RVIE_TAX_GROUP_BUCKET,
    SIRE_RVIE_TAX_GROUP_PRIORITY,
    SIRE_RVIE_TAX_LINE_BUCKET,
)

_logger = logging.getLogger(__name__)

# move_type que participan del Registro de Ventas e Ingresos (RVIE).
SIRE_RVIE_MOVE_TYPES = ("out_invoice", "out_refund")


class AccountMove(models.Model):
    _inherit = "account.move"

    # -- parseo de serie/numero ----------------------------------------------
    def _sire_rvie_parse_document_number(self):
        """(serie, numero) de ``self.name``.

        ``self.name`` es ``"{prefijo del tipo de documento} {serie}-{numero}"``
        (``l10n_latam_invoice_document`` antepone el prefijo con un espacio,
        p.ej. ``"F FFI-00000122"``): el indice 0 de separar por el primer
        "-" es ``"{prefijo} {serie}"`` junto -- se le quitan los espacios y
        se toman los ultimos 4 caracteres para obtener la serie real de 4
        caracteres que SUNAT tiene registrada (``"FFFI"``, no ``"FFI"``).

        PROBADO EN VIVO: el criterio anterior (tomar el texto tras el
        ultimo espacio y descartar el prefijo en vez de concatenarlo)
        generaba ``"FFI"`` para un comprobante cuyo XML UBL enviado a SUNAT
        usa ``"FFFI"`` -- todo el cruce contra la propuesta fallaba para
        esa serie. Con series de 4 caracteres sin prefijo separado (p.ej.
        ``"B001-00001134"``, boletas) el resultado no cambia: no hay
        espacio que quitar y ya son 4 caracteres.

        Deliberadamente MAS robusto que el SQL de referencia original (que
        usaba ``split_part(doc, '-', 2)``, que descarta cualquier fragmento
        despues de un segundo "-"): aqui se hace un unico split con
        maxsplit=1, asi que un numero que a su vez contuviera un "-" no se
        trunca.
        """
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
    def _sire_rvie_amount_buckets(self):
        """Bases imponibles (gravada/exportacion/exonerada/inafecta) e
        impuestos (igv/isc/otros) de ``self``, clasificados por
        ``account.tax.group`` -- ver notas (A)/(C) del SQL de referencia y
        ``sunat_rvie_tables.SIRE_RVIE_TAX_GROUP_BUCKET``.

        Devuelve un dict con las claves fijas
        ``gravada/exportacion/exonerada/inafecta/sin_clasificar`` (bases) y
        ``igv/isc/otros`` (impuestos). Los importes usan ``-balance`` (igual
        que el SQL de referencia): en una venta la linea de producto/impuesto
        queda en credito (balance negativo), asi que ``-balance`` da el monto
        en positivo para una factura y en negativo para una nota de credito.
        """
        self.ensure_one()
        buckets = {
            "gravada": 0.0,
            "exportacion": 0.0,
            "exonerada": 0.0,
            "inafecta": 0.0,
            "sin_clasificar": 0.0,
            "igv": 0.0,
            "isc": 0.0,
            "otros": 0.0,
        }
        for line in self.line_ids.filtered(lambda ln: ln.display_type == "product"):
            group_name = self._sire_rvie_priority_tax_group(line.tax_ids.tax_group_id)
            bucket = SIRE_RVIE_TAX_GROUP_BUCKET.get(group_name, "sin_clasificar")
            buckets[bucket] += -line.balance
        for line in self.line_ids.filtered(lambda ln: ln.display_type == "tax"):
            group_name = line.tax_line_id.tax_group_id.name
            bucket = SIRE_RVIE_TAX_LINE_BUCKET.get(group_name, "otros")
            buckets[bucket] += -line.balance
        return buckets

    @staticmethod
    def _sire_rvie_priority_tax_group(tax_groups):
        """Del conjunto de ``account.tax.group`` de una linea, el de mayor
        prioridad segun ``SIRE_RVIE_TAX_GROUP_PRIORITY`` (evita duplicar la
        base imponible cuando una linea lleva mas de un impuesto, p.ej. IGV +
        ISC). ``None`` si la linea no lleva ningun grupo reconocido."""
        names = set(tax_groups.mapped("name"))
        for candidate in SIRE_RVIE_TAX_GROUP_PRIORITY:
            if candidate in names:
                return candidate
        return None

    # -- fila del registro ----------------------------------------------------
    def _sire_rvie_build_register_row(self):
        """Una fila del registro de ventas comparable para ``self``
        (``account.move``). Ver "Comparacion propuesta SUNAT vs. Odoo" del
        plan aprobado para el detalle de cada campo.
        """
        self.ensure_one()
        serie, numero = self._sire_rvie_parse_document_number()
        buckets = self._sire_rvie_amount_buckets()
        partner = self.commercial_partner_id
        id_type = partner.l10n_latam_identification_type_id

        # Referencia NC/ND: reversed_entry_id (nota de credito estandar) o
        # debit_origin_id (nota de debito, campo de account_debit_note --
        # dependencia transitiva de l10n_pe, ver __manifest__.py).
        ref_move = self.reversed_entry_id or self.debit_origin_id
        ref_tipo_cp = ref_serie = ref_numero = False
        ref_fecha = False
        if ref_move:
            ref_serie, ref_numero = ref_move._sire_rvie_parse_document_number()
            ref_tipo_cp = ref_move.l10n_latam_document_type_id.code or False
            ref_fecha = ref_move.invoice_date

        exchange_rate = False
        if (
            self.currency_id != self.company_id.currency_id
            and self.invoice_currency_rate
        ):
            # Odoo guarda el factor empresa -> comprobante; SUNAT pide soles
            # por unidad de moneda extranjera (ver nota B del SQL).
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
            "amount_export": round(buckets["exportacion"], 2),
            "amount_taxed": round(buckets["gravada"], 2),
            "amount_exempt": round(buckets["exonerada"], 2),
            "amount_unaffected": round(buckets["inafecta"], 2),
            "amount_isc": round(buckets["isc"], 2),
            "amount_igv": round(buckets["igv"], 2),
            "amount_other_taxes": round(buckets["otros"], 2),
            "amount_unclassified": round(buckets["sin_clasificar"], 2),
            "amount_total": round(self.amount_total_signed, 2),
            "currency_code": self.currency_id.name,
            "exchange_rate": exchange_rate,
            "ref_fecha_emision": ref_fecha,
            "ref_tipo_cp": ref_tipo_cp,
            "ref_serie": ref_serie,
            "ref_numero": ref_numero,
        }

    # -- registro completo de un periodo --------------------------------------
    @api.model
    def _sire_rvie_get_ventas_register(self, company, periodo_tributario):
        """Registro de ventas comparable del periodo ``periodo_tributario``
        (``AAAAMM``) de ``company``, una fila (dict) por comprobante.

        Filtro: ``state = 'posted'``, ``move_type in ('out_invoice',
        'out_refund')``, ``invoice_date`` dentro del periodo, y
        ``l10n_pe_edi_is_required`` (si el campo existe -- ver mas abajo).
        Un comprobante que no requiere envio electronico nunca puede
        aparecer en la propuesta de SUNAT, asi que compararlo solo genera
        ruido ``missing_in_sunat`` indistinguible de una discrepancia real.

        ``l10n_pe_edi_is_required`` es un campo de un modulo externo
        (``l10n_pe_edi``) que NO es dependencia de ``tgr_sire_rvie`` -- se
        lee con ``getattr``/default ``True`` para no romper instalaciones
        sin ese modulo (mismo comportamiento que antes: sin el campo, no se
        filtra nada).
        """
        date_from, date_to = self._sire_rvie_period_bounds(periodo_tributario)
        moves = self.search(
            [
                ("company_id", "=", company.id),
                ("state", "=", "posted"),
                ("move_type", "in", SIRE_RVIE_MOVE_TYPES),
                ("invoice_date", ">=", date_from),
                ("invoice_date", "<=", date_to),
            ]
        )
        moves = moves.filtered(
            lambda move: getattr(move, "l10n_pe_edi_is_required", True)
        )
        return [move._sire_rvie_build_register_row() for move in moves]

    @staticmethod
    def _sire_rvie_period_bounds(periodo_tributario):
        """(fecha_desde, fecha_hasta) del periodo ``AAAAMM``."""
        year = int(periodo_tributario[:4])
        month = int(periodo_tributario[4:6])
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)
