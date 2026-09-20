"""Fixtures compartidos para los tests de tgr_sire_rvie.

No importado por ``tests/__init__.py`` a propósito: no contiene ningún
``TestCase``, solo helpers reusados por los test modules de este addon.

Reusa el mock de ``requests.Response`` y el helper de credenciales de
``tgr_sire_mixin`` (mismo patrón, no se duplica) y agrega los fixtures de
``account.move`` peruanos (factura/NC/moneda extranjera) necesarios para
``test_sire_rvie_comparison.py``.
"""

from odoo import Command

from odoo.addons.tgr_sire_mixin.tests.common import (  # noqa: F401
    SireMixinTestMixin,
    sire_mock_response,
)


class SireRvieTestMixin(SireMixinTestMixin):
    """Fixtures de ``account.move`` con documentos peruanos, sobre el chart
    of accounts genérico que arma ``AccountTestInvoicingCommon``."""

    @classmethod
    def _sire_rvie_setup_pe_company(cls):
        """Ajusta ``cls.company_data['company']`` para que se comporte como
        una compañía peruana (país PE, RUC, diario de venta con
        documentos), sin depender del chart of accounts oficial de
        ``l10n_pe`` (el genérico de test alcanza para estos fixtures)."""
        company = cls.company_data["company"]
        company.write({"country_id": cls.env.ref("base.pe").id})
        company.partner_id.write(
            {
                "vat": "20557912879",
                "l10n_latam_identification_type_id": cls.env.ref("l10n_pe.it_RUC").id,
            }
        )
        cls.company = company

        cls.sale_journal = cls.company_data["default_journal_sale"]
        cls.sale_journal.l10n_latam_use_documents = True

        # Diario "mal configurado" (sin tipo de documento SUNAT), a
        # propósito para test_sire_rvie_comparison.py: sus comprobantes NO
        # deben desaparecer silenciosamente del registro Odoo.
        cls.no_doc_journal = cls.env["account.journal"].create(
            {
                "name": "Ventas sin documento SUNAT",
                "type": "sale",
                "code": "NODOC",
                "company_id": company.id,
                "l10n_latam_use_documents": False,
            }
        )

        cls.tax_group_igv = cls.env["account.tax.group"].create({"name": "IGV"})
        cls.tax_igv_18 = cls.env["account.tax"].create(
            {
                "name": "IGV 18%",
                "amount": 18.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": cls.tax_group_igv.id,
                "company_id": company.id,
            }
        )

        cls.doc_type_factura = cls.env.ref("l10n_pe.document_type01")
        cls.doc_type_nc = cls.env.ref("l10n_pe.document_type07")

        cls.pe_partner = cls.env["res.partner"].create(
            {
                "name": "Cliente RVIE SAC",
                "vat": "10467283414",
                "l10n_latam_identification_type_id": cls.env.ref("l10n_pe.it_DNI").id,
                "country_id": cls.env.ref("base.pe").id,
            }
        )

    def _sire_rvie_create_invoice(self, name, amount=100.0, journal=None, **overrides):
        journal = journal or self.sale_journal
        vals = {
            "move_type": "out_invoice",
            "name": name,
            "partner_id": self.pe_partner.id,
            "invoice_date": "2026-01-15",
            "date": "2026-01-15",
            "journal_id": journal.id,
            "l10n_latam_document_type_id": self.doc_type_factura.id
            if journal.l10n_latam_use_documents
            else False,
            "invoice_line_ids": [
                Command.create(
                    {
                        "product_id": self.product_a.id,
                        "quantity": 1,
                        "price_unit": amount,
                        "tax_ids": [Command.set(self.tax_igv_18.ids)],
                    }
                )
            ],
        }
        vals.update(overrides)
        move = self.env["account.move"].create(vals)
        move.action_post()
        return move

    def _sire_rvie_create_credit_note(self, name, invoice, amount=100.0, **overrides):
        vals = {
            "move_type": "out_refund",
            "name": name,
            "partner_id": self.pe_partner.id,
            "invoice_date": "2026-01-20",
            "date": "2026-01-20",
            "journal_id": self.sale_journal.id,
            "l10n_latam_document_type_id": self.doc_type_nc.id,
            "reversed_entry_id": invoice.id,
            "invoice_line_ids": [
                Command.create(
                    {
                        "product_id": self.product_a.id,
                        "quantity": 1,
                        "price_unit": amount,
                        "tax_ids": [Command.set(self.tax_igv_18.ids)],
                    }
                )
            ],
        }
        vals.update(overrides)
        move = self.env["account.move"].create(vals)
        move.action_post()
        return move
