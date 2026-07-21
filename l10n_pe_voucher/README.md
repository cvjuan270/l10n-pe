# Peru - Voucher contable (CUO)

Asigna a cada asiento contable un **voucher** con correlativo único por compañía (CUO -
Código Único de la Operación), agrupando los apuntes que pertenecen a la misma operación
de negocio para el **Libro Diario PLE** de SUNAT.

## Qué hace

- Al **postear** un asiento, cada apunte recibe un voucher. El voucher se deduplica por
  **origen de la operación** (documento fuente): los asientos relacionados de una misma
  operación — p. ej. la valorización de inventario y la factura de la misma compra —
  comparten el mismo CUO.
- El correlativo sale de una secuencia **`no_gap` por compañía** (formato de 8 dígitos),
  creada bajo demanda.
- La unicidad por operación está garantizada **a nivel de base de datos** (constraint
  `unique(company_id, origin_model, origin_res_id)` con reintento optimista): dos
  transacciones concurrentes nunca producen dos CUOs para la misma operación, y el
  reintento no quema correlativos.
- Módulos puente extienden el origen a otros documentos: ventas/compras
  (`l10n_pe_voucher_sale_purchase`), POS (`l10n_pe_voucher_pos`), conciliación de pagos
  (`l10n_pe_voucher_reconcile`) y analítica (`l10n_pe_voucher_analytic_target`).

## Asignación histórica (backfill)

Los asientos posteados **antes** de instalar el módulo no reciben CUO automáticamente
(asignar correlativos retroactivos es una decisión fiscal). El asistente
**Contabilidad > Asignar vouchers históricos** procesa el histórico por lotes, con fecha
de inicio configurable y barra de progreso.

## Migración a 18.0.1.1.0

La actualización valida que no existan CUOs duplicados preexistentes (producto de la
condición de carrera que esta versión elimina). Si los hay, **aborta** listando las
operaciones afectadas: la fusión debe resolverse manualmente, porque un correlativo ya
declarado en un PLE cerrado no puede reasignarse.
