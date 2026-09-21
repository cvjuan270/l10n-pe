"""Shared fixtures for the voucher (CUO) test suites.

Not imported by ``tests/__init__.py`` on purpose: it holds no test case, only
helpers reused by this module and by its bridges.
"""

import contextlib
from unittest.mock import patch


class L10nPeVoucherTestMixin:
    """Neutralise database-specific customisations that would break the
    *fixtures* of the standard Odoo test helpers.

    Production databases of the client carry a ``base.automation`` rule on
    ``res.partner`` that refuses to save a contact without an identification
    document ("No se puede guardar el contacto sin un ID"). The rule fires on
    every partner creation, including the ones the core test helpers build for
    their own users (``AccountTestInvoicingCommon.setup_independent_user``,
    ``TestPoSCommon`` customers, ...), which we do not control and which are
    created *inside* ``super().setUpClass()``.

    The rule is neither part of the modules under test nor of the behaviour they
    implement, so we disable the automation engine for the whole test class
    instead of altering the code under test. The patch is installed before
    ``super().setUpClass()`` runs, and removed by ``addClassCleanup``.

    Partners created by our own tests still carry a coherent Peruvian
    identification (``_l10n_pe_partner_vals``) so the fixtures stay realistic.
    """

    # Form views of this database that make fields mandatory at *view* level
    # (not at model level) and would break the standard Odoo test helpers built
    # on ``Form`` -- e.g. ``AccountTestInvoicingCommon.init_invoice`` cannot fill
    # the hospital "Physician" the customer-invoice form demands. None of them
    # belongs to the modules under test.
    _l10n_pe_neutralised_views = ("tgr_hms_base.view_move_form",)

    @classmethod
    def setUpClass(cls):
        cls._l10n_pe_disable_base_automation()
        super().setUpClass()
        cls._l10n_pe_neutralise_views()

    @classmethod
    def _l10n_pe_neutralise_views(cls):
        for xmlid in cls._l10n_pe_neutralised_views:
            view = cls.env.ref(xmlid, raise_if_not_found=False)
            if view:
                view.sudo().active = False

    @classmethod
    def _l10n_pe_disable_base_automation(cls):
        try:
            from odoo.addons.base_automation.models.base_automation import (
                BaseAutomation,
            )
        except ImportError:  # base_automation not installed: nothing to do.
            return

        def _no_actions(self, records, triggers):
            return self.env["base.automation"].browse()

        patcher = patch.object(BaseAutomation, "_get_actions", _no_actions)
        patcher.start()

        def _stop():
            # Odoo's own class teardown already disables patchers it finds
            # still active, so stopping twice must not blow up.
            with contextlib.suppress(RuntimeError):
                patcher.stop()

        cls.addClassCleanup(_stop)

    @classmethod
    def get_default_groups(cls):
        """Grant the test user the right to create contacts.

        The client database narrows the ``res.partner`` create ACL to a handful
        of groups (Contact Creation, Hospital/*, ...), which the stock Odoo test
        user does not have -- and every test helper starts by creating a company,
        hence a partner. Unrelated to the code under test.
        """
        groups = super().get_default_groups()
        for xmlid in (
            # Contact creation is restricted to a few groups in this database.
            "base.group_partner_manager",
            # ``account.cash.rounding._check_session_state`` (core POS) searches
            # pos.session without sudo, so building the account test fixtures
            # needs read access on it as soon as point_of_sale is installed.
            "point_of_sale.group_pos_user",
            # ``TestPoSCommon`` builds its own pos.config / pos.session and
            # stock locations for the POS warehouse.
            "point_of_sale.group_pos_manager",
            "stock.group_stock_manager",
        ):
            group = cls.env.ref(xmlid, raise_if_not_found=False)
            if group:
                groups |= group
        return groups

    # -- fixtures -------------------------------------------------------------
    def _l10n_pe_partner_vals(self, name, vat="46728341"):
        """Values of a contact holding a valid Peruvian identification (DNI)."""
        vals = {"name": name, "vat": vat}
        id_type = self.env.ref("l10n_pe.it_DNI", raise_if_not_found=False)
        if id_type:
            vals["l10n_latam_identification_type_id"] = id_type.id
        return vals
