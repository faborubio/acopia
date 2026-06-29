# CLAUDE.md — Hub de contexto · Acopia

> **Lee esto primero.** Punto de entrada para cualquier sesión (humana o IA) que trabaje en Acopia.

## Qué es Acopia

Motor de optimización de despacho para una planta solar con batería (PV-BESS) en el mercado eléctrico chileno: pronostica generación PV y **costo marginal (CMg)** nodal y decide cuándo **cargar/descargar** para arbitrar el diferencial de CMg y rescatar energía que se vertería por congestión. Núcleo **determinista predict-then-optimize** (auditable); DRL como modo opcional medido. Capa **MCP** read-only para que un operador interrogue y simule el plan.

**Fuente de verdad de la arquitectura:** [`SAD_Acopia_energia.md`](./SAD_Acopia_energia.md).

## Cómo arranca una sesión (orden de lectura)

1. **`CLAUDE.md`** (este archivo) — cómo se trabaja aquí.
2. **`MEMORY.md`** — dónde quedamos y la próxima acción.
3. **`SAD_Acopia_energia.md`** — la arquitectura y los ADRs.
4. El `docs/` relevante a la tarea (`AUDIT.md`, `CASES.md`, `TROUBLESHOOTING.md`).

Al cerrar la sesión: escribe en `MEMORY.md` el estado y la próxima acción.

## Modo de trabajo (SDD)

Specification-Driven Development. Loop: **Especificar → Implementar → Verificar → Auditar → Sign-off** (ver §12 del SAD).

- La **spec se actualiza antes que el código**.
- **Ninguna fase cierra sin su entrada en `docs/AUDIT.md`**.
- El **dominio primero** (puro, stdlib-only), los adaptadores después.

## Convenciones

- **Idioma del dominio en español** (Planta, Bateria, Despacho, EstadoDeCarga, Precio/CMg, Escenario, PoliticaDeDespacho); técnico en inglés cuando es idiomático.
- **Determinismo:** mismo (política, forecast as-seen, semilla) → mismo plan. Property-test obligatorio.
- **El forecast se entrega con incertidumbre** (escenarios/bandas); nunca un número pelado.
- Energía en **Wh enteros**, potencia en **W enteros**, CMg en **mills enteros** donde el determinismo lo exija.
- `domain/` **sin** PyTorch, cvxpy ni DRL en las firmas. Frontera blindada con `import-linter`.

## Stack

Python 3.12+ · FastAPI · FastMCP · cvxpy/Pyomo + solver MILP · PyTorch (Seq2Seq-LSTM) · stable-baselines3 (DRL, opcional) · Pydantic v2 · SQLAlchemy 2.0 + PostgreSQL + TimescaleDB · injector · Docker · uv · ruff · mypy --strict · import-linter.

## Estado actual

Ver `MEMORY.md` (fuente de verdad del avance). Fases 0 y 1 cerradas (+ deuda saldada);
**Fase 2 (forecasting) en curso**: baseline estacional, SARIMAX, ingesta CSV y CLI
`acopia-datos` listos. Próximo: Seq2Seq-LSTM. Datos reales: ver bitácora del 2026-06-29.
