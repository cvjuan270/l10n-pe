# Documentacion del Proyecto

## Organizacion por ticket/tarea

Cada ticket o tarea tiene su propia subcarpeta dentro de `docs/`:

```
docs/
├── ticket_XXX/           ← Ticket del sistema de gestion
│   ├── summary.md        ← Analisis, decisiones, resumen
│   ├── work-plan.md      ← Plan de trabajo
│   ├── qa-report.md      ← Reporte de QA
│   └── screenshots/      ← Capturas de pruebas funcionales
├── tarea_NNN/            ← Tareas internas sin ticket
│   └── ...
└── general/              ← Documentacion que no pertenece a un ticket
```

## Convencion

- `ticket_XXX` — X es el numero del ticket (ej. `ticket_626`)
- `tarea_NNN` — N es un correlativo interno
- Cada carpeta contiene SOLO lo especifico del ticket: analisis, capturas,
  PDFs, notas
- Los cambios de codigo van en los modulos, NO aca
- Los agentes de Claude Code guardaran memoria de la tarea dentro de la
  carpeta del ticket
