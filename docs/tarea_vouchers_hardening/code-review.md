# Code Review Final - Endurecimiento familia voucher (CUO)

**Fecha**: 2026-07-21
**Revisor**: odoo-code-reviewer
**Módulos revisados**: `l10n_pe_voucher`, `l10n_pe_voucher_pos`, `l10n_pe_voucher_reconcile`
**Versión Odoo**: 18.0
**Core verificado contra**: `/home/juand/work/odoo/18.0/odoo` (`/opt/Odoo/odoo-18.0+e` no existe)

## Resumen ejecutivo

- Archivos de producción revisados: 12 · Archivos de test revisados: 6
- BLOQUEANTES: **0** · IMPORTANTES: 6 · SUGERENCIAS: 7
- **VEREDICTO: SE PUEDE LIBERAR** (aprobado con observaciones). Ninguna
  observación impide el despliegue; IMP-01 e IMP-02 exigen un runbook escrito
  antes de tocar producción.

---

## Criterio sobre los puntos consultados

### 1. Retry optimista (`_l10n_pe_create_or_recover`) - CORRECTO

Verificado contra `odoo/sql_db.py:123-140`:

- `cr.savepoint()` devuelve `_FlushingSavepoint`, cuyo `__init__` hace
  `cr.flush()` **antes** del `SAVEPOINT`. Esto elimina el riesgo clásico del
  patrón: los cambios pendientes previos ya están en la BD antes del savepoint,
  así que el `ROLLBACK TO SAVEPOINT` no puede perderlos. El `flush_all()`
  explícito solo empuja el INSERT propio. Correcto.
- En el rollback, `_FlushingSavepoint.rollback()` llama `self._cr.clear()` antes
  del `ROLLBACK TO SAVEPOINT`, así que la caché ORM queda limpia y el `search`
  posterior va realmente a la base.
- La transacción **no queda abortada**: el `ROLLBACK TO SAVEPOINT` se ejecuta en
  el `__exit__` antes de que la excepción llegue al `except`. Probado en
  `test_duplicate_origin_create_raises_integrity_error`, que reusa el cursor.
- **Re-lanzado de violaciones ajenas**: correcto y probado
  (`test_create_or_recover_reraises_unrelated_unique_violation`). El filtro por
  `pgcode` más el "si el search no encuentra nada, `raise`" es la discriminación
  correcta. `psycopg2.errors.UniqueViolation` hereda de `IntegrityError`.
- **Bucle infinito**: imposible, es un único reintento, no un `while`.
- **Correlativo `no_gap`**: no se quema. `_update_nogap`
  (`ir_sequence.py:54-60`) hace el `UPDATE` dentro del savepoint y el rollback
  lo deshace. Verificado en test sobre `number_next_actual`.

**Matiz (IMP-04)**: bajo concurrencia real *simultánea*, `_update_nogap` usa
`SELECT ... FOR UPDATE NOWAIT`: la segunda transacción revienta con
`LockNotAvailable` (55P03) **antes** del INSERT, o sea antes de que el retry de
`origin_uniq` pueda actuar. Eso lo cubre el reintento de Odoo
(`service/model.py:24-26`, 5 intentos) solo en llamadas RPC. El retry nuevo
cubre bien el caso "la ganadora ya commiteó" (el más frecuente en POS y
conciliación), no el solape exacto. No es defecto del cambio, es un límite a
documentar.

### 2. `init()` que hace DDL y puede ABORTAR - funciona, pero lugar equivocado (IMP-01)

Orden real de carga: `pre-migrate` -> `_auto_init`/`init()` -> data ->
`post-migrate`. El `pre-migrate.py` sí corre antes de que el ORM cree
`origin_uniq`. Bien.

El problema es la **asimetría**: los duplicados de `ir_sequence` se chequean en
`init()`, no en `pre-migrate.py`. Consecuencias:

- `init()` corre en **toda** instalación/actualización. Una BD con secuencias
  duplicadas queda bloqueada para *cualquier* `-u l10n_pe_voucher`, incluso para
  instalar una versión futura que traiga el arreglo. Única salida: SQL manual.
- Agravante: las `ir.sequence` de voucher se crean por código, sin `xml_id`, por
  lo que sobreviven a un desinstalar. Un ciclo instalar -> usar -> desinstalar ->
  reinstalar puede toparse con este `ValueError` en una "instalación limpia".
- `raise ValueError` en `init()` aborta el arranque. En Odoo.sh es una build
  fallida, no un mensaje al usuario.

No es bloqueante porque solo dispara con datos ya corruptos y el mensaje indica
qué hacer, pero exige runbook.

### 3. Iterar por orden en `_apply_invoice_payments` - CORRECTO

Verificado contra `point_of_sale/models/pos_order.py`:

- :1034 el único caller del core, `_generate_pos_order_invoice`, **ya llama
  orden por orden**. Iterar no cambia nada para ese caller.
- :1067-1081 la implementación core es mono-registro por construcción
  (`self.partner_id`, `self.account_move`, `self.payment_ids`). Llamarla con
  multi-registro siempre estuvo mal definido; iterar es *más* correcto.
- Sin otros callers: 0 coincidencias en `enterprise`, 1 en `community`.
- Firma y tipo de retorno preservados. El
  `payment_moves._context.get('credit_line_ids')` que lee el core (:1073) se
  consume **dentro** de `super()`, antes de reenvolver el recordset.
- Reenvolver el retorno en el env del caller (perdiendo el flag) es deliberado y
  correcto: `_create_misc_reversal_move` no debe heredarlo.

### 4. Índice parcial en `account_move_line.init()` - bloqueo aceptable (IMP-02)

`CREATE INDEX` sin `CONCURRENTLY` toma lock `SHARE`: bloquea escrituras mientras
se construye. En el instante del `-u` el predicado `WHERE l10n_pe_voucher_id IS
NULL` matchea el **100%** de las filas, o sea es prácticamente un índice full
sobre la tabla más grande de contabilidad. En ventana de mantenimiento es
aceptable, pero hay que dimensionarlo antes. Adicional: el índice **nunca se
dropea**; al terminar el backfill queda vivo y vacío, y su predicado se evalúa
en cada INSERT/UPDATE. Coste permanente pequeño pero real.

### 5. ¿Camino que cree voucher sin `_l10n_pe_get_or_create`? - SÍ, uno (IMP-03)

Todo el código de producción pasa por `_l10n_pe_get_or_create`. Pero
`security/ir.model.access.csv:3` da `perm_create=1` al
`account.group_account_manager`, y `views/l10n_pe_voucher_views.xml:92-97` no
lleva `context="{'create': False}"`. Un jefe de contabilidad puede pulsar
"Nuevo", guardar un voucher **sin origen**, y eso (a) quema un correlativo
`no_gap` en un voucher vacío y (b) **no lo detiene `origin_uniq`**, porque
PostgreSQL no compara NULLs en un UNIQUE. Contradice el comentario de
`l10n_pe_voucher.py:82-85`.

### 6. `noupdate="1"` en el cron - correcto

El xmlid sigue siendo
`l10n_pe_voucher_reconcile.ir_cron_backfill_deferred_vouchers`: **el `<data>` no
participa del xmlid**. En la actualización, `_tag_root` procesa `<data>` igual
que `<odoo>`, encuentra el `ir.model.data` existente y con `noupdate=1` respeta
el registro tal como está, incluido el `active` que el cliente haya puesto. Es
exactamente el comportamiento buscado. Sin regresión.

---

## Hallazgos clasificados

### BLOQUEANTES

Ninguno.

### IMPORTANTES

- **[IMP-01]** `l10n_pe_voucher/models/l10n_pe_voucher.py:96-146` - La detección
  de secuencias duplicadas vive en `init()` en vez de en `pre-migrate.py`. Una
  BD sucia queda permanentemente inactualizable y solo se recupera con SQL
  manual. **Antes de liberar**: runbook con la consulta de diagnóstico y el
  procedimiento de fusión manual. **Próxima iteración**: mover la detección al
  `pre-migrate.py` y dejar `init()` solo con el `CREATE UNIQUE INDEX`.
- **[IMP-02]** `l10n_pe_voucher/models/account_move_line.py:31-63` - `CREATE
  INDEX` no concurrente sobre `account_move_line` durante el `-u`. **Acción**:
  medir `count(*)` en producción y, si supera unos pocos millones, crear el
  índice manualmente con `CONCURRENTLY` antes del `-u` (el `index_exists()` hará
  que `init()` lo salte). Considerar dropearlo tras el backfill.
- **[IMP-03]** `security/ir.model.access.csv:3` + `views/l10n_pe_voucher_views.xml:92`
  - Creación manual de vouchers desde la UI escapa a `origin_uniq` y quema
  correlativo. Sugerencia: `perm_create=0,perm_unlink=0` o
  `context="{'create': False}"` en la acción.
- **[IMP-04]** `l10n_pe_voucher/models/l10n_pe_voucher.py:162-200` - El retry no
  cubre la carrera simultánea exacta (`LockNotAvailable` de `FOR UPDATE
  NOWAIT`). Odoo reintenta 5 veces **solo en RPC**: un `ir.cron` o un script de
  shell fallan el job. Impacto acotado (el cron reintenta en la siguiente
  pasada), pero no vender el fix como cobertura total de concurrencia.
- **[IMP-05]** `l10n_pe_voucher_pos/models/pos_session.py:100` -
  `displaced.filtered(...).unlink()` **borra vouchers ya numerados**, abriendo
  huecos en un correlativo que el resto del diseño declara gap-less (ver
  `l10n_pe_voucher_reconcile/models/account_move_line.py:35-36`). Es
  **preexistente**, no introducido aquí, pero es inconsistencia de diseño con
  impacto contable en el Libro Diario. Ningún test lo cubre. Abrir tarea propia.
- **[IMP-06]** `l10n_pe_voucher_sale_purchase` y `l10n_pe_voucher_analytic_target`
  dependen de `l10n_pe_voucher`, cuyo comportamiento de creación cambió, y no
  entraron en la corrida de QA. **Antes de liberar**: correr sus suites.

### SUGERENCIAS

- **[SUG-01]** DDL con formateo `%` en vez de los helpers de `odoo.tools.sql`.
  No hay inyección (valores constantes del módulo), pero `create_index(...)`
  (`tools/sql.py:548`) usa `SQL.identifier` y ya incorpora el `index_exists`.
- **[SUG-02]** `raise ValueError` con mensaje largo sin `_()`. Una excepción
  propia (`MigrationError`) sería más diagnosticable.
- **[SUG-03]** `pos_order.py:51` - `order.session_id.state == "closed"` duplica
  la semántica del parámetro `is_reverse` que el core ya calcula igual
  (:1034). Usar `is_reverse` evitaría divergencia futura.
- **[SUG-04]** `l10n_pe_voucher_pos/models/account_move.py:34-86` -
  `_l10n_pe_voucher_move_key` no contempla `reversed_pos_order_id`. El asiento de
  reversión de `_create_misc_reversal_move` (justo el flujo que arregla esta
  iteración) cae al fallback y se lleva un CUO propio, separado del de la
  `pos.order`. Revisar si es lo contablemente deseado.
- **[SUG-05]** `pos_session.py:83-99` - el cache resuelve el N+1 de *lectura*,
  pero la escritura sigue línea a línea. Agrupar por voucher y hacer un `write()`
  por grupo reduciría los UPDATE de cientos a un puñado.
- **[SUG-06]** `ir_cron.xml:10-19` - el `<record>` no se re-indentó al añadir el
  `<data>`. Cosmético.
- **[SUG-07]** `views/l10n_pe_voucher_views.xml:81` - `<group expand="0">` dentro
  del `<search>`; en Odoo 18 el core ya no lo usa.

---

## Revisión de los tests

**Los tests preexistentes NO fueron ablandados. Uno fue reforzado.**

| Fichero | Cambio | Veredicto |
|---|---|---|
| `l10n_pe_voucher/tests/test_voucher.py` | mixin + `assertTrue(all(mapped(m2o)))` -> `assertFalse(filtered(...))` (:86-89) | **Refuerzo real**. `all()` sobre recordset vacío es `True`: el assert anterior era vacuo. Ningún otro assert se relajó. |
| `l10n_pe_voucher_pos/tests/test_voucher_pos.py` | mixin + DNI al cliente POS | Solo fixture. Asserts de fondo intactos. |
| `l10n_pe_voucher_reconcile/tests/test_voucher_reconcile.py` | solo mixin | Sin tocar asserts. Sigue siendo la suite más exigente. |

**Tests nuevos** sólidos. Destacan tres asserts difíciles de falsear: la
verificación en `pg_constraint`/`pg_indexes`, el `INSERT` crudo saltándose el
ORM, y `number_next_actual` antes/después para probar que el rollback no quema
correlativo. La mutación temporal documentada por QA confirma sensibilidad.

**Limitaciones declaradas**: la "carrera" se simula cegando el primer `search`
dentro de una misma transacción (no prueba visibilidad cross-transacción ni
`LockNotAvailable`); y la **rama de aborto del `pre-migrate.py` nunca se
ejecutó** - es la brecha más relevante y la que más duele si falla en Odoo.sh.

### Mixin `l10n_pe_voucher/tests/common.py` - workaround legítimo

1. `patch.object(BaseAutomation, "_get_actions")`: la regla que estorba es de la
   BD `o18_cms`, ajena a la familia voucher, y se dispara dentro de
   `super().setUpClass()`. Ninguno de los tres módulos define ni consume
   `base.automation`, así que no puede enmascarar un fallo suyo. Observación:
   es más amplio de lo necesario (desactiva TODAS las automatizaciones en vez de
   la regla concreta).
2. `get_default_groups()`: los grupos añadidos son ortogonales a
   `account.group_account_user/manager`, que son los que gobiernan
   `l10n.pe.voucher`. No oculta nada.
3. Desactivar `tgr_hms_base.view_move_form`: `physician_id` es obligatorio a
   nivel de **vista**, no de modelo, y rompe `init_invoice`. Solución estándar.

**Deuda anotada**: un módulo de localización pensado para publicarse referencia
en su código de test el módulo cliente `tgr_hms_base` y asume ACLs de `o18_cms`.
La suite solo pasa en esa BD. Habrá que parametrizarlo si se publica.

**Nota**: `test_voucher.py::test_payment_inherits_invoice_voucher` y
`test_payment_of_several_vouchers_keeps_own` viven en `l10n_pe_voucher` pero
solo pasan si `l10n_pe_voucher_reconcile` está instalado (acoplamiento
preexistente). Y `test_voucher_pos.py:94` /
`test_voucher_pos_invoice_timing.py:144` asertan sobre
`_l10n_pe_moves_to_backfill()` **global de la BD**: hoy pasa porque `o18_cms` no
tiene asientos posteados pendientes, pero es un assert dependiente del entorno.

---

## Convenciones validadas

- [x] Código íntegramente en inglés (strings, help, docstrings, comentarios).
- [x] PEP8, imports ordenados (stdlib / psycopg2 / odoo / addons).
- [x] Nomenclatura correcta; constantes en mayúsculas.
- [x] Estructura estándar de módulo, incluida `migrations/`.
- [x] Manifests con author/website/license correctos y coherentes.
- [x] Odoo 18: `<list>`, `view_mode="list,form"`, sin `attrs`/`states`.
- [x] `depends` completo (`account` añadido en `l10n_pe_voucher_pos`).
- [x] Orden de `data` correcto: security -> wizard -> views -> menuitems.
- [x] `ir.model.access.csv` + record rule multi-compañía presentes.
- [x] `sudo()` usado con criterio y justificado.
- [x] Excepciones tipadas; sin `except` desnudos. El único `except` amplio
      (`psycopg2.IntegrityError`) está discriminado por `pgcode` y re-lanza.
- [ ] **Traducciones**: los tres módulos carecen de `i18n/`. Todos los mensajes
      de usuario llegarán en inglés a un usuario peruano. No bloqueante, pero
      corresponde generar el `.pot` y traducirlo.

## Verificación del campo `version`

| Módulo | `version` | Estado |
|---|---|---|
| `l10n_pe_voucher` | `18.0.1.1.0` | Bump presente y **autorizado**, registrado en el work-plan. Necesario para que corra `migrations/18.0.1.1.0/pre-migrate.py`. Verificado que la carpeta coincide con la versión y que el fichero cumple el patrón `pre-*` que exige `odoo/modules/migration.py:189`. Correcto. |
| `l10n_pe_voucher_pos` | `18.0.1.0.0` | Sin tocar. OK |
| `l10n_pe_voucher_reconcile` | `18.0.1.0.0` | Sin tocar. OK |

Nadie tocó versiones fuera de lo autorizado.

---

## VEREDICTO FINAL

**SE PUEDE LIBERAR - APROBADO CON OBSERVACIONES.**

Los siete hallazgos de la revisión previa están efectivamente cerrados, con
implementaciones correctas y no meramente cosméticas. El retry optimista es
sólido: verificado línea por línea contra `sql_db.py` que el savepoint no deja
la transacción abortada, que re-lanza correctamente las violaciones ajenas y que
no quema correlativo. La iteración en `_apply_invoice_payments` respeta el
contrato del core. El `noupdate="1"` no cambia el xmlid ni rompe el cron
instalado. Los tests preexistentes no fueron ablandados y el mixin de fixtures
es un workaround legítimo del entorno `o18_cms`.

**Condiciones previas al despliegue** (ninguna implica cambiar código):

1. Escribir el runbook de recuperación para el aborto de `init()` y del
   `pre-migrate` (IMP-01), y probar la rama de aborto una vez sobre un clon
   desechable - es la única ruta crítica sin cobertura.
2. Medir el tamaño de `account_move_line` en producción y decidir si el índice
   se crea `CONCURRENTLY` antes del `-u` (IMP-02).
3. Correr las suites de `l10n_pe_voucher_sale_purchase` y
   `l10n_pe_voucher_analytic_target` contra el nuevo `l10n_pe_voucher` (IMP-06).

**Para la siguiente iteración** (no bloquean): IMP-03, IMP-05 y la generación de
los `.po`.

Este reporte es informativo. No se modificó ningún archivo ni se ejecutó ninguna
operación git.
