# -*- coding: utf-8 -*-
{
    'name': "Enumera asientos contables de Factura de proveedores",

    'summary': """
        """,

    'description': """
        Este módulo implementa una secuencia correlativa para documentos de compra (facturas, notas de crédito y débito)
        con formato YY-MM-NNNN (año-mes-correlativo) basado en la fecha contable del documento.
        Utiliza rangos de fecha mensuales para mantener numeración coherente por mes.
    """,

    'author': "Juan D. Collado V.",
    'website': "https://tagre.pe",

    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting/Localization',
    'version': '0.1',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account'],
    'excludes':['account_journal_general_sequence'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/account_journal_views.xml',
        'views/account_move_views.xml',
        'wizards/account_move_renumber_wizard_views.xml'
    ],
}
