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

## Modo de trabajo (SDD + el Método)

Specification-Driven Development. Loop: **Especificar → Implementar → Verificar → Auditar → Sign-off** (ver §12 del SAD). El proyecto se rige por el MANIFIESTO del Método (v1.1.0, `\\wsl.localhost\Ubuntu-24.04\home\faborubio\Workspace\metodo\MANIFIESTO.md`).

- La **spec se actualiza antes que el código** (el SAD cambia solo por ADR nuevo o enmienda versionada; historial al final del SAD).
- **Ninguna fase cierra sin su entrada en `docs/AUDIT.md`**; todo trade-off aceptado tiene su **`AUD-NNN`** en el registro de deuda.
- Antes de tocar una heurística/config, el caso real se documenta en `docs/CASES.md` (evidencia, no intuición).
- El **dominio primero** (puro, stdlib-only), los adaptadores después.
- **Proporcionalidad:** el rigor de más es deuda, no virtud.

### Definition of Done (obligatorio, en orden, al cerrar cada fase)

1. **Ronda crítica (vista de halcón)** — dos preguntas, en este orden:
   1. **¿Hay una idea mejor?** Releer las *decisiones* de la fase: ¿algún ADR, heurística o diseño tiene hoy una alternativa superior a la luz de lo aprendido? Si sí, se decide ahora — enmendar (ADR nuevo / enmienda versionada) o diferir con su `AUD-NNN` — porque después de cerrar, el costo de cambiar solo sube.
   2. **¿Hay bugs?** Releer el *código* de la fase cazando bugs y bordes; corregir los de riesgo real, diferir el resto como `AUD-NNN`.
2. **Casos borde → `docs/CASES.md`** (sobre todo tras datos reales).
3. **Deuda → `docs/AUDIT.md`** — todo trade-off aceptado obtiene su `AUD-NNN`.
4. **Incidentes → `docs/TROUBLESHOOTING.md`** — toda falla resuelta durante la fase.
5. **Contexto → `CLAUDE.md` + `README.md` + `MEMORY.md`** en sincronía con el resto.
6. **Verde** — ruff · mypy --strict · lint-imports · pytest · **pip-audit**.
7. **Commit + push.**

## Convenciones

- **Idioma del dominio en español** (Planta, Bateria, Despacho, EstadoDeCarga, Precio/CMg, Escenario, PoliticaDeDespacho); técnico en inglés cuando es idiomático.
- **Determinismo:** mismo (política, forecast as-seen, semilla) → mismo plan. Property-test obligatorio.
- **El forecast se entrega con incertidumbre** (escenarios/bandas); nunca un número pelado.
- Energía en **Wh enteros**, potencia en **W enteros**, CMg en **mills enteros** donde el determinismo lo exija.
- `domain/` **sin** PyTorch, cvxpy ni DRL en las firmas. Frontera blindada con `import-linter`.

## Stack

Python 3.12+ · FastAPI · FastMCP · cvxpy/Pyomo + solver MILP · PyTorch (Seq2Seq-LSTM) · stable-baselines3 (DRL, opcional) · Pydantic v2 · SQLAlchemy 2.0 + PostgreSQL + TimescaleDB · injector · Docker · uv · ruff · mypy --strict · import-linter.

## Estado actual

Ver `MEMORY.md` (fuente de verdad del avance). **Fases 0–4 cerradas** (sign-offs en
`docs/AUDIT.md`): **el alcance de portafolio del SAD §13 está completo** — despacho
determinista, forecaster + escenarios, robustez + backtest, co-optimización SSCC,
capa MCP y modo DRL medido (captura 96% del LP; el experimento destapó y pagó una
debilidad de la cuantización del baseline, AUD-003). La Fase 5 (potencia de
suficiencia, multi-planta, nube) es **"solo con tracción"** por regla del Método.
**Próxima acción:** no hay trabajo de fases pendiente; quedan las decisiones abiertas
de `MEMORY.md` (rotar la key SIP — seguridad, pendiente del usuario —, renombrar la
carpeta local `ergia` → `acopia`, dominios/INAPI) y, si se retoma, la deuda viva
priorizada del registro `AUD-NNN` (AUD-005 sweep de ventana es la primera).
