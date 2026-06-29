# Acopia

Motor de optimización de despacho para una planta solar con batería (PV-BESS) en el mercado eléctrico chileno: pronostica generación PV y **costo marginal (CMg)** nodal y decide cuándo **cargar/descargar** para arbitrar el diferencial de CMg y rescatar energía que se vertería por congestión. Núcleo **determinista predict-then-optimize** (auditable); DRL como modo opcional medido. Capa **MCP** read-only para interrogar y simular el plan.

> Arquitectura completa en [`SAD_Acopia_energia.md`](./SAD_Acopia_energia.md). Contexto de trabajo en [`CLAUDE.md`](./CLAUDE.md).

## Estado

**Fase 1 — Despacho determinista (cerrada).** Optimizador predict-then-optimize (cvxpy + HIGHS) que, dado un forecast, genera un plan de despacho **factible y rentable**, con ingreso auditable y API REST. Sobre el scaffolding de Fase 0 (capas, value objects, `ModeloBateria` puro, property-tests). Ver [`docs/AUDIT.md`](./docs/AUDIT.md).

```bash
uv run uvicorn acopia.interfaces.rest.app:app --reload   # API en http://127.0.0.1:8000/docs
```

## Estructura

```text
src/acopia/
├── domain/          # núcleo puro (stdlib-only): value objects, entidades, servicios, puertos
├── application/     # casos de uso (fase 1+)
├── infrastructure/  # adaptadores: forecaster, solver, repos, gateways (fase 1+)
└── interfaces/      # REST (FastAPI) y MCP (FastMCP) (fase 1+)
tests/               # pytest + hypothesis
```

## Desarrollo

Requiere Python 3.12+ y [uv](https://docs.astral.sh/uv/).

```bash
uv venv
uv pip install -e ".[dev]"

uv run ruff check .          # lint
uv run mypy                  # tipado estricto
uv run lint-imports          # fronteras de arquitectura (import-linter)
uv run pytest                # tests
```

Base de datos (TimescaleDB) para fases posteriores:

```bash
docker compose up -d db
```

## Datos reales (Chile)

El motor consume una serie horaria `timestamp,generacion_w,cmg_mills_por_mwh`
(la "planta modelo"), que se arma de dos fuentes:

1. **CMg por barra — Coordinador Eléctrico.** Vía práctica: **descargar el XLS**
   de [Costo Marginal Real](https://www.coordinador.cl/mercados/documentos/transferencias-economicas/costo-marginal-real/)
   filtrando una barra y un rango de fechas, y guardarlo como CSV.
   *(La API existe — `costo-marginal-online/v4/findByDate`, ver `MEMORY.md` — pero
   no filtra por barra y está rate-limited: inviable para bajar un año de una barra.)*
2. **Generación PV — Explorador Solar** ([solar.minenergia.cl](https://solar.minenergia.cl/exploracion)):
   exportar la serie horaria de generación de la ubicación de la planta -> `gen.csv`.

Como el Explorador es un "año típico" (2004–2016) y el CMg es de otro año, **no
comparten calendario**: se alinean **por posición** (hora a hora), con el timestamp del CMg:

```bash
acopia-datos alinear --por-posicion \
  --cmg cmg.csv --col-cmg "Costo Marginal [USD/MWh]" \
  --generacion gen.csv --col-gen generacion_kw --escala-gen 1000 \
  --salida planta.csv
```

Los lectores toleran **coma decimal chilena** (`"57,79"`). Luego
`GatewayCSV("planta.csv").cargar()` entrega la serie de `Observacion` que alimenta
el forecaster y el despacho.
