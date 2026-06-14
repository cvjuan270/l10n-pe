1. Lagica de asietos contables


Tenemos que implementar un logica de vocher en los apuntes contables para la contabilidad peruana en el modelo account.move.line hay que agregar un campo l10n_pe_voucher.

En la contabilidad peruana nos piden un reporte de libro diario hay que agrupar los apuntes contables por vaucher; por ejemplo si hago una compra y esta tiene un movimiento de inventario este asiento debe de tener el numero de voucher y cuondo se haga la factura tambien debe de tener numero de voucher.
En casuistica cuando se tiene muchos movimientos de inventario y muchas facturas, se tiene que tener ese mapeo, por lo que recomiendo que el mapeo sea por las lineas.
