from . import sunat_tables
# Los modelos que AGREGAN columnas (stock.picking) deben inicializarse antes
# que la vista SQL (l10n.pe.stock.ple), que las referencia. Por eso el modelo
# de vista se importa al final.
from . import stock_picking
from . import uom_uom
from . import product_template
from . import l10n_pe_stock_ple
from . import report_stock_ple
