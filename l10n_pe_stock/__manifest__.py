{
    "name": "Configuracion basica localizacion peruana Stock",
    "summary": """
        Extiende lacalazacion peruana Stock
    """,
    "author": "Juan D. Collado Vasquez",
    "license": "LGPL-3",
    "version": "16.0.1.0.1",
    "website": "https://github.com/cvjuan270/l10n-pe",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Accounting/Localization/Inventory",
    # any module necessary for this one to work correctly
    "depends": ["l10n_pe", "stock", "account", "l10n_pe_base"],
    # always loaded
    "data": [
        # 'security/ir.model.access.csv',
        "views/stock_picking_views.xml",
        "views/account_move_views.xml",
    ],
    # only loaded in demonstration mode
}
