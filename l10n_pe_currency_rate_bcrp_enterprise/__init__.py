from . import models


def _l10n_pe_set_bcrp_api_provider(env):
    """Migra las companias peruanas que quedaron con el proveedor SUNAT
    de enterprise al nuevo proveedor BCRP API."""
    env["res.company"].search(
        [
            ("country_id.code", "=", "PE"),
            ("currency_provider", "=", "bcrp"),
        ]
    ).write({"currency_provider": "bcrp_api"})
