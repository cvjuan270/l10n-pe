# -*- coding: utf-8 -*-
# Copyright 2026 tagre.pe
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
import logging
import re

import requests

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

API_BASE_URL = "https://dniruc.apisperu.com/api/v1"
API_TIMEOUT = 10


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _l10n_pe_vat_parse_token(self, token):
        """Split the stored token from its optional service plan marker."""
        match = re.fullmatch(r"(.+?)\s*\|\s*(\d+)", token)
        if match:
            return match.group(1).strip(), int(match.group(2))
        return token, None

    @api.model
    def _l10n_pe_vat_register_query(self, cap):
        """Count one outgoing query against the current month allowance.

        :param cap: maximum queries allowed per month, or None for no cap.
        :return: True if the query is allowed, False otherwise.
        """
        if not cap:
            return True
        icp = self.env["ir.config_parameter"].sudo()
        month = fields.Date.context_today(self).strftime("%Y-%m")
        if icp.get_param("l10n_pe_vat.query_month") != month:
            icp.set_param("l10n_pe_vat.query_month", month)
            count = 0
        else:
            count = int(icp.get_param("l10n_pe_vat.query_count", "0") or 0)
        if count >= cap:
            return False
        icp.set_param("l10n_pe_vat.query_count", str(count + 1))
        return True

    @api.model
    def l10n_pe_vat_consult(self, vat_number, identification_type_id):
        """Query the APIs Peru DNI/RUC service and build partner values.

        :param vat_number: document number typed in the vat field.
        :param identification_type_id: id of the l10n_latam.identification.type.
        :return: ``{'values': {...}}`` ready for ``record.update()`` on the
            client (many2one as ``[id, display_name]``) or ``{'error': msg}``.
        """
        # RPC-exposed method: restrict to users that can edit partners.
        self.check_access_rights("write")

        token = self.env["ir.config_parameter"].sudo().get_param("l10n_pe_vat.api_token")
        if not token:
            return {"error": _(
                "The APIs Peru token is not set. Configure it in Settings > "
                "General Settings > Contacts.")}

        id_type = self.env["l10n_latam.identification.type"].browse(
            int(identification_type_id or 0))
        if id_type == self.env.ref("l10n_pe.it_DNI", raise_if_not_found=False):
            endpoint = "dni"
        elif id_type == self.env.ref("l10n_pe.it_RUC", raise_if_not_found=False):
            endpoint = "ruc"
        else:
            return {"error": _(
                "The lookup is only available for DNI or RUC identification types.")}

        number = str(vat_number or "").strip()
        if endpoint == "dni" and not re.fullmatch(r"\d{8}", number):
            return {"error": _("The DNI must have 8 digits.")}
        if endpoint == "ruc" and not re.fullmatch(r"\d{11}", number):
            return {"error": _("The RUC must have 11 digits.")}

        token, cap = self._l10n_pe_vat_parse_token(token)
        if not self._l10n_pe_vat_register_query(cap):
            return {"error": _(
                "The monthly limit of %s queries has been reached. "
                "Try again next month.") % cap}

        try:
            response = requests.get(
                "%s/%s/%s" % (API_BASE_URL, endpoint, number),
                params={"token": token},
                timeout=API_TIMEOUT,
            )
        except requests.exceptions.RequestException:
            # Never log the URL/params: the token travels in the query string.
            _logger.warning("APIs Peru %s lookup failed", endpoint, exc_info=True)
            return {"error": _(
                "Could not reach the APIs Peru service. Check your internet "
                "connection and try again.")}

        try:
            data = response.json()
        except ValueError:
            data = None

        # API errors come back as {'success': false, 'message': ...}, usually
        # with HTTP 200 but sometimes with a 4xx status.
        if isinstance(data, dict) and "success" in data and not data.get("success"):
            return {"error": data.get("message") or _("Document not found.")}
        if not response.ok or not isinstance(data, dict):
            _logger.warning(
                "APIs Peru %s lookup returned HTTP %s with unexpected payload",
                endpoint, response.status_code)
            return {"error": _(
                "Could not reach the APIs Peru service. Check your internet "
                "connection and try again.")}

        country = self.env.ref("base.pe")
        values = {"country_id": [country.id, country.display_name]}
        if endpoint == "dni":
            name = " ".join(filter(None, [
                data.get("nombres"),
                data.get("apellidoPaterno"),
                data.get("apellidoMaterno"),
            ]))
            if name:
                values["name"] = name
        else:
            # Never overwrite existing partner data with empty API values.
            if data.get("razonSocial"):
                values["name"] = data["razonSocial"]
            if data.get("direccion"):
                values["street"] = data["direccion"]
            if data.get("ubigeo"):
                values["zip"] = data["ubigeo"]
            district = self.env["l10n_pe.res.city.district"].search(
                [("code", "=", data.get("ubigeo"))], limit=1)
            if district:
                values["l10n_pe_district"] = [district.id, district.display_name]
                city = district.city_id
                if city:
                    values["city_id"] = [city.id, city.display_name]
                    if city.state_id:
                        values["state_id"] = [
                            city.state_id.id, city.state_id.display_name]
        return {"values": values}
