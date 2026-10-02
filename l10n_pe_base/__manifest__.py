{
    "name": "Configuracion basica localizacion peruana.",
    "summary": """
        Extiende localización peruana l10n_pe
        - Add table 12: Tipo de operación
        - Add  period on account move.
        - Restrictions by open or clase period
    """,
    "author": "Juan D. Collado Vasquez",
    "license": "LGPL-3",
    "version": "16.0.1.0.2",
    "website": "https://github.com/cvjuan270/l10n-pe",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Accounting/Localization/",
    # any module necessary for this one to work correctly
    "depends": ["l10n_pe", "account_fiscal_year"],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "security/l10n_pe_base_security.xml",
        # data
        "data/l10n_pe.table.12.csv",
        # views
        "views/l10n_pe_account_period.xml",
        "views/account_move_views.xml",
        "wizard/wizard_period_generator.xml",
        "views/menu_items.xml",
    ],
    "post_init_hook": "post_init_hook",
}
