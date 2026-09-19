{
    "name": "Peru - Stock PLE: Inventario Permanente Valorizado (Formato 13.1)",
    "version": "18.0.1.0.0",
    "summary": """Registro de Inventario Permanente Valorizado (Formato 13.1)
    del PLE de SUNAT Peru. Reporte a partir de las capas de valoracion de
    inventario (stock.valuation.layer) con exportacion a PDF (layout oficial)
    y Excel.""",
    "author": "Tagre.pe,Juan D. Collado Vasquez",
    "website": "https://github.com/cvjuan270/l10n-pe",
    "category": "Accounting/Financials/Localizations",
    "depends": ["l10n_pe", "stock_account"],
    "data": [
        "security/ir.model.access.csv",
        "security/l10n_pe_stock_ple_security.xml",
        "data/l10n_latam_document_type_data.xml",
        "data/uom_sunat_code_data.xml",
        "report/l10n_pe_stock_ple_report.xml",
        "report/l10n_pe_stock_ple_templates.xml",
        "views/l10n_pe_stock_ple_views.xml",
        "views/stock_picking_views.xml",
        "views/uom_views.xml",
        "views/product_views.xml",
        "wizard/l10n_pe_stock_ple_wizard_views.xml",
        "views/menuitems.xml",
    ],
    "price": 0,
    "currency": "USD",
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "AGPL-3",
}
