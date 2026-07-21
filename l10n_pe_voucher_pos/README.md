# Peru - Voucher contable (CUO) para Punto de Venta

Puente entre `l10n_pe_voucher` y el **Punto de Venta**: controla _cuándo_ se asigna el
CUO a los asientos generados por POS para no quemar correlativos ni fragmentar una misma
operación en varios vouchers.

## Qué hace

- **Difiere** la asignación del voucher de los asientos de POS hasta el **cierre de
  sesión**: el cierre es el momento en que la operación queda completa y puede recibir
  su correlativo definitivo.
- Al cerrar la sesión, los asientos de liquidación se enrutan al voucher que corresponde
  (por orden o por sesión), reutilizando un cache para resolver cada origen una sola
  vez.
- Las órdenes **facturadas después del cierre de sesión** también reciben su CUO: la
  asignación se dispara al aplicar los pagos de la factura, limitada a las órdenes cuya
  sesión ya está cerrada (las de sesiones abiertas esperan a su propio cierre).

## Dependencias

- `l10n_pe_voucher` (core del CUO)
- `point_of_sale`
- `account`
