# Análisis — NC de compra que ajusta la valorización por su propio importe

**Cliente**: Tagre.pe · **Odoo**: 18 · **Fecha**: 2026-07-04
**Módulo puente propuesto**: `l10n_pe_purchase_stock`, `depends: ["purchase_stock"]`

## Problema

Una NC de compra por descuento/ajuste de precio, creada como **reversión** de la factura
(`reversed_entry_id` seteado), NO refleja el descuento esperado en la valorización.
El core de `purchase_stock` (rama `is_refund`, `account_move_line.py:101-132`) **deshace la
corrección de precio de la factura original** e **ignora el importe de la NC**.

Caso real verificado (PO 30, producto AVCO):
- Recepción 10 uds @ PO 20 → SVL 35: qty 10, value **+200** (capa padre).
- Factura @ 15/u → SVL 36: qty 0, value **−50** (baja costo 20→15). Correcto.
- NC reversión, línea @ 1/u, neto 10 → SVL 37: qty 0, value **+50** (deshace la factura).
  Se esperaba **−10** (costo final 14/u). Confirmado comportamiento NATIVO, sin código del proyecto.

## Restricciones del cliente

1. El criterio y la magnitud del ajuste se derivan del **valor/importe neto de la NC**,
   no del Catálogo 09 ni de campos de la localización.
2. El módulo depende **únicamente de `purchase_stock`**.

## Decisión de arquitectura

**Opción A (recomendada): NC independiente ligada a `purchase_line_id`, sin `reversed_entry_id`.**
El core hace `continue` cuando no hay `reversed_entry_id` (`account_move_line.py:104-106`);
rellenamos ese hueco. La reversión queda reservada a anulación real (SUNAT 01/02) y no se toca.

- Ventaja: cero regresión sobre el flujo de anulación; sin heurísticas por importe.
- Costo: la NC de descuento debe crearse ligada a la PO (`purchase_line_id`) y **sin** "Revertir".

**Fallback Opción B** (si el cliente no puede cambiar el workflow): conservar reversión y gatear
con un booleano genérico `stock_price_adjustment` en `account.move` (definido en el módulo, sin
l10n). Más intrusivo: hay que neutralizar el +50 de la rama nativa. +4–6 h.

## Fórmula del ajuste (basada en el valor de la NC)

En moneda de compañía. `N` = neto de la línea de NC; `Q_nc` = cantidad cubierta;
`d = N / Q_nc` = descuento por unidad. Por capa padre impactada:
- `in_stock_qty = layer.remaining_qty`
- `out_qty = min(invoicing_layer_qty, layer.quantity − layer.remaining_qty)`

Destinos y signos:
- **Porción en stock** → SVL hija: `value = −d · in_stock_qty`; `layer.remaining_value += value`.
- **Porción salida** → ajuste COGS vía AML: `−d · out_qty` (no toca inventario).
- Conservación: `Σ(SVL) + Σ(COGS) = −N`.

Ejemplo: N=10, Q_nc=10, d=1, 10 en stock → SVL **−10**, costo final 14/u. Da −10, no +50.

## Punto de inyección

`account.move.line._generate_price_difference_vals` (override de `account_move_line.py:55`):

```python
def _generate_price_difference_vals(self, layers):
    if self._is_purchase_price_adjustment_nc():
        return self._generate_pnc_adjustment_vals(layers)
    return super()._generate_price_difference_vals(layers)
```

Reutiliza del core: `_replay_history` (`:165`, matcheo capa↔factura, coherencia FIFO),
`_prepare_pdiff_svl_vals` (`:308`), `_prepare_pdiff_aml_vals` (`:280`). La única diferencia
es que la magnitud sale de `−d` (valor de la NC) en vez de `aml_price_unit − layer_price_unit`.
No se hace override de `_post` ni de `_apply_price_difference`: los SVL suben por
`account_invoice.py:131` y entran solos en el recompute de `standard_price` (`:134-137`) y en
`_validate_accounting_entries` (`:153-154`).

Diferencia deliberada con el core: **sí** ajustamos COGS de la porción salida (el core la anula
en `:129` porque revierte; nosotros aplicamos un descuento real).

## Contabilidad (cuadre)

NC postea: `Dr CxP N / Cr Stock Interim N`. Nuestro trabajo contrapartea ese Cr Interim:
- En stock: SVL negativo dispara `_account_entry_move` sobre el `stock_move_id` de la capa padre
  → `Dr Interim / Cr Valuation`. Cancela la parte proporcional y baja valorización.
- Salida: `_prepare_pdiff_aml_vals` → `Dr Interim / Cr Expense`. Reduce COGS.
- La reconciliación anglosajona (`account_invoice.py:156`) concilia el Interim sin descuadre,
  siempre que la línea de NC caiga en *Stock Interim Recibido* (garantizado por el anglosajón
  estándar al estar ligada a la PO).

## standard_price / AVCO vs FIFO

- Recompute automático en `_post:134-137` (`value_svl / quantity_svl`). No tocar manualmente.
- AVCO: una capa; el promedio baja limpio.
- FIFO: `_get_layers_price_diff` devuelve todas las capas "in"; `_replay_history` reparte `Q_nc`;
  se ajusta `remaining_value` por capa (correcto para consumo FIFO futuro).
- **Costo estándar: excluido** (el core lo filtra en `:129`; no se revaloriza inventario).

## Casos borde

NC parcial · producto totalmente vendido (todo a COGS) · multi-recepción (reparto por
`_replay_history`) · multi-moneda (convertir `N` con `currency_rate`) · idempotencia
(`_post:125` + guarda propia) · descuento mayor que costo (validar/advertir, evitar costo negativo).

## Riesgos

- Opción A no toca la reversión legítima (01/02): nuestra rama solo actúa con `reversed_entry_id`
  vacío. Cero interferencia.
- Riesgo operativo: si crean la NC de descuento con "Revertir", reaparece el +50 → advertencia.
- `purchase_line_id` ausente → sin ajuste (silencioso) → advertencia.
- l10n_pe_edi / Catálogo 09: ortogonal; verificar que la NC independiente genere el DE SUNAT válido.
- l10n_pe_stock_ple: el SVL negativo aparecerá en el 13.1; confirmar clasificación como ajuste de costo.

## Estructura del módulo

```
l10n_pe_purchase_stock/
├── __manifest__.py      # depends: ["purchase_stock"]
└── models/account_move_line.py
```

Métodos (en `account.move.line`):
- `_is_purchase_price_adjustment_nc()`: `in_refund` and not `reversed_entry_id` and
  `purchase_line_id` and `cost_method != 'standard'`.
- `_generate_price_difference_vals()` (override): despacha.
- `_generate_pnc_adjustment_vals(layers)` (nuevo): calcula `d`, split in/out, arma SVL+AML.
- `_prepare_pnc_pdiff_vals(...)` (nuevo): espejo de `_prepare_pdiff_vals` con `unit_diff=−d`.

## Estimación

**18 h** (rango 14–26). Complejidad Alta (valorización + contabilidad anglosajona + reconciliación).

## Preguntas pendientes al cliente

1. ¿Se puede cambiar el workflow a NC independiente ligada a PO (sin "Revertir")? (base de Opción A)
2. ¿Una NC independiente sin `reversed_entry_id` sigue generando el DE SUNAT válido (Catálogo 09)?
3. ¿La NC de descuento referencia una sola factura/recepción o puede consolidar varias?
4. ¿Hay NC de descuento en moneda extranjera? Tratamiento de diferencia de cambio.
5. ¿Se usa FIFO en algún producto afectado o solo AVCO?
6. ¿El Formato 13.1 debe mostrar el SVL negativo como línea de ajuste específica?
