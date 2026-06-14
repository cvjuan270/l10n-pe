# Tagre.pe - Configuracion de proyecto

## Datos generales
- **Cliente**: Tagre.pe
- **Version Odoo**: 18
- **Puerto local**: 8069
- **BD local de pruebas**: o18_pe
- **Virtualenv**: /home/juand/work/odoo/18.0/.venv
- **Repo**: git@github.com:cvjuan270/l10n-pe.git

## Reglas del partner
Ver reglas globales en `/home/juand/Projects_odoo/CLAUDE.md`.

## Ejecucion local
```bash
# Activar virtualenv (si aplica)
source "/home/juand/work/odoo/18.0/.venv/bin/activate"

# Arrancar Odoo
cd /opt/Odoo/odoo-18.0+e
python -m odoo --http-port=8069 -d o18_pe
```

## Documentacion por ticket/tarea
Cada ticket o tarea vive en su propia carpeta dentro de `docs/`:

- `docs/ticket_XXX/` para tickets del sistema de gestion
- `docs/tarea_NNN/` para tareas internas sin ticket
- `docs/general/` para documentacion transversal

Dentro de cada carpeta se guarda `summary.md`, `work-plan.md`,
`qa-report.md`, `screenshots/` y cualquier PDF o nota asociada al ticket.
El codigo fuente va en los modulos, nunca en `docs/`.

## Modulos del proyecto
(Agrega aqui la lista de modulos propios del cliente)
