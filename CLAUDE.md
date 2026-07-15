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

Specification-Driven Development. Loop: **Especificar → Implementar → Verificar → Auditar → Sign-off** (ver §12 del SAD). El proyecto se rige por el MANIFIESTO del Método (v1.3.0, `\\wsl.localhost\Ubuntu-24.04\home\faborubio\Workspace\metodo\MANIFIESTO.md`). Al reentrar, verificar la versión vigente del MANIFIESTO: sus enmiendas aplican a este repo (la v1.2.0 fijó el estándar profesional del README; la v1.3.0, la sección `## Próxima sesión` de este archivo).

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
Existe un **dashboard demo** en `GET /demo` (ADR-011) que comparte el día sembrado
con la demo MCP. El proyecto entró en **exploración de salida real** (2026-07-14):
la cara pública será el **Observatorio** (ADR-012) — sitio estático de datos del
mercado en GitHub Pages que además publica el snapshot de la demo —, con piloto
hardware casero y prospección de cliente en el Maule como frentes paralelos
(detalle y evidencia en la bitácora de `MEMORY.md`).

## Próxima sesión

Pendientes en orden de valor; ⏸ = espera una decisión del autor.

1. **Difundir el Observatorio v1** — construido y desplegado el 2026-07-15
   (https://faborubio.github.io/acopia/): enlazarlo en el README de acopia y el perfil
   de GitHub; primer contenido de LinkedIn con la página de vertimiento (la cuña de
   posicionamiento del ADR-012).
2. **Observatorio rebanada 3**: duck curve del CMg + valorización del desplazamiento
   a la punta. Bloqueo real: falta fuente de CMg automatizable para el Action (la
   descarga manual del XLS no sirve); evaluar la API v4 online por tramos chicos, y el
   mapeo central→zona vía info de instalaciones del Coordinador (AUD-026).
2. ⏸ **Prospección de cliente real (Maule, cerca de Curepto)** — candidatos mapeados
   (2026-07-14, bitácora): PMGD = calce directo del producto (Solek/Pencahue Este a
   ~40 km; oEnergy/El Tiuque, primer PMGD+BESS de Chile, en San Javier); viñas del
   Mataquito (Viñedos Puertas) = piloto behind-the-meter que exige adaptación.
3. **Especificar la adaptación behind-the-meter** si se persigue la viña: señal =
   tarifa horaria en vez de CMg + término de cargo por potencia (máximo leído, no
   energía) en el LP. Parte con su caso en `docs/CASES.md` y su ADR.
4. ⏸ **Piloto hardware paso 0** (costo ~USD 0): adaptador de ejecución/telemetría
   Modbus contra Venus OS (Victron) en modo demo, antes de comprar batería. Abre con ADR.
5. **Deuda viva del registro `AUD-NNN`**: hiperparámetros/regla por régimen (resto de
   AUD-005); backtest de política con LSTM (AUD-006, candidata natural).
6. Diferidas a propósito: dominios/INAPI (retomar con tracción); postulación Grupo
   Mariposa — la oferta de pulir el dashboard para el CV sigue abierta.
