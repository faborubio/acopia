# Acopia

**Motor de optimización de despacho para plantas solares con batería (PV-BESS) en el mercado eléctrico chileno.** Pronostica la generación PV y el **costo marginal (CMg)** nodal con incertidumbre explícita, y decide cuándo **cargar/descargar** la batería para arbitrar el diferencial de CMg y rescatar energía que se vertería por congestión. El núcleo es **determinista predict-then-optimize**: mismo forecast, misma semilla → el mismo plan, bit a bit, con el motivo de cada decisión explicable hora por hora.

> **El problema que ataca:** Chile vertió **6.084 GWh** de energía renovable en 2025 (+7,8% vs 2024); entre 2022 y mediados de 2025 el vertimiento acumulado ronda los **11.900 GWh ≈ US$562M** perdidos, con el CMg colapsando a 0 a mediodía por sobreoferta solar y disparándose en la punta vespertina. Ese diferencial es exactamente lo que una batería bien despachada captura.

Arquitectura completa y decisiones (ADRs) en [`SAD_Acopia_energia.md`](./SAD_Acopia_energia.md) · Contexto de trabajo en [`CLAUDE.md`](./CLAUDE.md).

## Resultados medidos

Todo número de abajo sale de backtests reproducibles sobre **datos reales chilenos** (CMg horario de la barra S.GREGORIO, año 2025, del Coordinador Eléctrico; generación PV TMY de Antofagasta, Explorador Solar):

| Qué se midió | Resultado |
|---|---|
| Forecast de CMg (backtest anual, 7 folds) | Seq2Seq-LSTM régimen-local: **RMSE −23% vs baseline estacional-naïve** (20.3k vs 26.2k mills/MWh) |
| Elección de ventana de entrenamiento | Sweep de 6 ventanas: curva en U con mínimo en 720 h — la config no es frágil (enmienda ADR-002.2) |
| Robustez del plan en ejecución | Optimización estocástica con 5 escenarios: **~100% de captura del ingreso foresight** (vs 93% con escenario único) |
| Modo DRL (PPO) vs núcleo determinista | El DRL captura el **96.1%** del LP — el determinista gana y queda **medido**, no asumido (ADR-005) |
| Honestidad del experimento | La primera corrida DRL "superó" al óptimo → se auditó el baseline y se encontró un bug real de cuantización que valía **+8.9% de ingreso** del LP (AUD-003, pagada) |

## Cómo funciona

1. **Pronostica con incertidumbre** (nunca un número pelado): estacional-naïve, SARIMAX y Seq2Seq-LSTM detrás de un mismo puerto producen escenarios probabilísticos deterministas.
2. **Optimiza el despacho**: LP estocástico de dos etapas (cvxpy + HIGHS) que co-optimiza **arbitraje de CMg + reserva de frecuencia (SSCC)** en una sola función objetivo, respetando la física de la batería (SoC, eficiencias, throughput) como restricciones duras.
3. **Deja rastro auditable**: cada plan persiste su snapshot as-seen (forecast, estado, política versionada, semilla, huella SHA-256 del histórico) — un auditor regenera el plan bit a bit.
4. **Se explica y se simula** vía una capa **MCP read-only**: `consultar_despacho`, `explicar_despacho` ("¿por qué cargaste a mediodía?"), `simular` ("¿y si el CMg colapsa en la punta?") y `comparar_modos` — nada se ejecuta ni persiste.
5. **Se corrige intradía**: detección de desvío de generación + reoptimización desde el estado real de la batería, sin re-versionar la política.

El dominio es **puro y stdlib-only** (Clean Architecture con frontera verificada por `import-linter`): PyTorch, cvxpy y DRL viven en adaptadores, nunca en las firmas del núcleo.

## Demo en 60 segundos

```bash
uv run uvicorn acopia.interfaces.rest.app:app   # → http://127.0.0.1:8000/demo
python -m acopia.interfaces.mcp.servidor        # servidor MCP (stdio) con el mismo día sembrado
```

**`GET /demo`** sirve el dashboard del día típico chileno (ADR-011): el plan de despacho sobre la duck curve — CMg con anotaciones, PV y acciones de la batería, SoC — con el **motivo de cada decisión** en el tooltip, y el pipeline de datos que alimenta al motor. HTML autocontenido: sin CDN, sin framework de frontend, legible sin JavaScript, modo claro/oscuro. Es el mismo día que interroga la demo MCP.

![Dashboard demo de Acopia](./docs/img/dashboard_demo.png)

## Estado

**Fases 0–4 cerradas — el alcance de portafolio del SAD está completo** (sign-offs en [`docs/AUDIT.md`](./docs/AUDIT.md)):

- **F0 — Cimientos:** capas Clean Architecture, value objects enteros, `ModeloBateria` puro, property-tests (determinismo y factibilidad).
- **F1 — Despacho determinista:** optimizador predict-then-optimize (cvxpy + HIGHS) con plan factible, ingreso auditable y API REST.
- **F2 — Forecasting + escenarios:** tres forecasters intercambiables, snapshot as-seen del forecast (huella SHA-256), pipeline de ingesta de datos chilenos reales.
- **F3 — Robustez + backtest:** optimizador estocástico de dos etapas, backtest de política contra el día real (esperado vs realizado vs foresight), reoptimización intradía.
- **F4 — SSCC + MCP + DRL:** co-optimización arbitraje + reserva de frecuencia (ADR-010), servidor MCP read-only, modo DRL medido contra el baseline (ADR-005).

La Fase 5 (potencia de suficiencia, multi-planta, nube) se reserva **"solo con tracción"** — no se construye a futuro sin señal real de demanda.

## Estructura

```text
src/acopia/
├── domain/          # núcleo puro (stdlib-only): value objects, entidades, servicios, puertos
├── application/     # casos de uso: planificar, backtest, reoptimizar, comparar modos
├── infrastructure/  # adaptadores: forecasters, solver LP, DRL, ingesta, repositorios
└── interfaces/      # REST (FastAPI), MCP (FastMCP), CLI (acopia-datos), dashboard demo
tests/               # pytest + hypothesis (204 tests)
```

## Desarrollo

Requiere Python 3.12+ y [uv](https://docs.astral.sh/uv/).

```bash
uv venv
uv pip install -e ".[dev]"

uv run ruff check .          # lint
uv run mypy                  # tipado estricto (mypy --strict)
uv run lint-imports          # fronteras de arquitectura (import-linter)
uv run pytest                # tests
uv run pip-audit             # vulnerabilidades conocidas en dependencias
```

Extras opcionales: `.[forecasting]` (torch CPU, LSTM), `.[ingesta]` (openpyxl, XLSX del
Coordinador), `.[mcp]` (FastMCP, servidor MCP), `.[drl]` (stable-baselines3 + gymnasium).

Base de datos (TimescaleDB) para la fase de persistencia real:

```bash
docker compose up -d db
```

## Datos reales (Chile)

El motor consume una serie horaria `timestamp,generacion_w,cmg_mills_por_mwh`
(la "planta modelo"), que se arma de dos fuentes:

1. **CMg por barra — Coordinador Eléctrico.** Vía práctica: **descargar el XLS**
   de [Costo Marginal Real](https://www.coordinador.cl/mercados/documentos/transferencias-economicas/costo-marginal-real/)
   filtrando una barra y un rango de fechas.
   *(La API existe — `costo-marginal-online/v4/findByDate`, ver `MEMORY.md` — pero
   no filtra por barra en el servidor y está rate-limited: inviable para un año de una barra.)*
2. **Generación PV — Explorador Solar** ([solar.minenergia.cl](https://solar.minenergia.cl/exploracion)):
   exportar la serie horaria de generación de la ubicación de la planta → `gen.csv`.

Como el Explorador entrega un "año típico" (2004–2016) y el CMg es de otro año, **no
comparten calendario**: se alinean **por posición** (hora a hora), con el timestamp del CMg.
Los lectores toleran el formato real del Coordinador (XLSX ancho, celdas combinadas,
**coma decimal chilena**):

```bash
acopia-datos alinear --por-posicion \
  --cmg cmg.xlsx --col-ts-cmg Fecha --col-hora-cmg Hora --col-cmg "S.GREGORIO" --escala-cmg 1000 \
  --generacion gen.csv --col-gen pv --escala-gen 1000 \
  --salida planta.csv
```

Con la planta modelo armada, los backtests que respaldan la tabla de resultados:

```bash
acopia-datos backtest --planta datos/planta.csv --folds 7 \
  --modelos naive,sarimax,lstm --ventana-entrenamiento 720   # error de forecast por modelo
acopia-datos backtest-politica --planta datos/planta.csv     # ingreso esperado vs realizado vs foresight
acopia-datos comparar-modos --planta datos/planta.csv        # ADR-005: DRL (PPO) vs baseline LP
```

## Ingeniería a la vista

El proyecto se rige por un método explícito (SDD + documentación viva): la spec cambia
antes que el código, toda decisión tiene su ADR, todo trade-off aceptado tiene su entrada
numerada de deuda, y ninguna fase cierra sin auditoría.

- [`docs/AUDIT.md`](./docs/AUDIT.md) — sign-offs por fase y el registro de deuda `AUD-NNN` (viva y pagada).
- [`docs/CASES.md`](./docs/CASES.md) — los casos reales del dominio que calibraron cada heurística.
- [`docs/TROUBLESHOOTING.md`](./docs/TROUBLESHOOTING.md) — incidentes reales y cómo se resolvieron.
