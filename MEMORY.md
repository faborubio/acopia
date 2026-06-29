# MEMORY.md — Bitácora · Acopia

> Decisiones, hallazgos no obvios y estado actual. Se actualiza al final de cada sesión y ante cada decisión relevante. Lo más reciente arriba.

## Estado actual

- **Fase:** 2 en curso — rebanadas 1 (forecasting), 1b (ingesta CSV), 1c (CLI datos) y 2 (SARIMAX) **completas**. Fase 1 + deuda cerradas.
- **Próxima acción (Fase 2, rebanada 3):** Seq2Seq-LSTM (PyTorch) detrás de `PuertoForecaster`, comparado vs SARIMAX y el baseline. Ojo: el LSTM real necesita datos para entrenar; sin datos chilenos reales se entrena sobre sintéticos (arquitectura + pipeline, no la promesa del ~34%).
- **Datos reales (cómo obtenerlos) — ver bitácora 2026-06-29 "API real del Coordinador":** la vía práctica es **descarga manual del XLS** de CMg (una barra, rango de fechas) + exportar generación del Explorador Solar, y unir con `acopia-datos alinear --por-posicion`. La API existe pero NO conviene para bulk (ver abajo).

## Bitácora

### 2026-06-29 — Fixes de datos reales (coma decimal + alineación por posición)
- **`parsear_decimal`** (en `infrastructure/ingesta/preparacion.py`): tolera coma decimal chilena (`"57,79415"` → 57.79415; `"1.234,56"` → 1234.56). Lo usan `GatewayCSV`, `leer_serie_csv` y `extraer_cmg`. Necesario porque TODO dato chileno trae coma.
- **`alinear_por_posicion`** + flag CLI **`--por-posicion`**: une CMg y generación por índice (hora a hora) usando el timestamp del CMg. Necesario porque el Explorador Solar es "año típico" (2004–2016) y el CMg es de otro año → no comparten calendario. Exige mismo largo (evita desfases).
- Verde: ruff/mypy/import-linter OK · pytest **81 passed** (+6).

### 2026-06-29 — API real del Coordinador (IMPORTANTE para la próxima sesión)
- El portal del desarrollador usa endpoints **v4** tipo microservicio, NO el `…/sipub/api/v2/recursos/…` documentado (obsoleto). El correcto es:
  - **`https://sipub.api.coordinador.cl/costo-marginal-real/v4/findByDate`** (real, definitivo, con rezago de meses)
  - **`https://sipub.api.coordinador.cl/costo-marginal-online/v4/findByDate`** (preliminar, al día)
  - Params: **`startDate`/`endDate`** (YYYY-MM-DD), `page`/`limit`; respuesta JSON con `data`, `page`, `limit`, `totalPages` (paginación por página, NO `next`).
  - Campos de cada registro: `fecha_hora` (`"2025-06-01 00:00"`, horario), `barra_transf` (mnemónico, ej. `S.GREGORIO____013`), `cmg_clp_kwh_` y `cmg_usd_mwh_` (**coma decimal**), `version`, etc.
  - La key debe ser del servicio **Información Pública (SIP)** (cada app/servicio tiene su propia key).
- **Por qué NO usar la API para bulk:** no filtra por barra en el servidor (ignora el param) → ~150.000 registros/día (todas las barras), y aparece **429 (rate limit)**. Para un año de UNA barra es inviable.
- **El `acopia-datos cmg` actual quedó OBSOLETO** (lo armé para el formato v2 `next`/`results`). Si se quiere vía API hay que reescribirlo para v4 (page/limit, `data`, filtrar barra en cliente, coma decimal). Baja prioridad: la descarga manual del XLS es mejor.
- Pendiente del usuario: **rotar la key de SIP** (estuvo expuesta en el chat).

### 2026-06-29 — Fase 2 rebanada 2 (forecaster SARIMAX)
- `ForecasterSARIMAX` (statsmodels) detrás de `PuertoForecaster`: ajusta un SARIMAX por serie (gen, CMg), escenario 0 = media, resto = media + N(0, se) con semilla fija (determinista).
- Test clave: SARIMAX **bate al estacional-naïve** en RMSE sobre datos con tendencia (el naïve repite la última estación y se queda corto).
- Dependencia: statsmodels 0.14.6 (+ mypy override). Warnings de convergencia silenciados en el fit.
- Verde: ruff/mypy/import-linter OK · pytest **75 passed** (+4).

### 2026-06-29 — Fase 2 rebanada 1c (CLI acopia-datos)
- CLI `acopia-datos` (entry point) en `interfaces/cli`: subcomando `cmg` (descarga CMg de la API SIP v2 del Coordinador, sigue paginación `next`, requiere user_key en la URL) y `alinear` (cruza CMg + generación PV por timestamp → CSV de planta).
- Endpoint real CMg: `https://sipub.api.coordinador.cl/sipub/api/v2/recursos/costos_marginales_reales` (user_key gratuito de portal.api.coordinador.cl). Generación PV: sin API horaria pública → exportar del Explorador Solar y pasar a `alinear`.
- Helpers puros testeables en `infrastructure/ingesta/preparacion.py` (leer_serie_csv, extraer_cmg, alinear_series, escribir_*). HTTP con urllib (stdlib).
- Verde: ruff/mypy/import-linter OK · pytest **71 passed** (+7).

### 2026-06-29 — Fase 2 rebanada 1b (gateway de ingesta CSV)
- `PuertoHistoria` (puerto) + `GatewayCSV` (infra, stdlib `csv`): lee `timestamp,generacion_w,cmg_mills_por_mwh` → `tuple[Observacion]`, con validaciones que reportan el número de fila.
- Fixture `tests/infrastructure/datos/muestra_planta.csv` + tests (carga, columnas faltantes, archivo inexistente, valor inválido, generación negativa, integración con el forecaster).
- Es la pieza que conecta datos reales (Coordinador + Explorador Solar) con el pipeline sin meter datasets grandes al repo.
- Verde: ruff/mypy/import-linter OK · pytest **64 passed** (+7).

### 2026-06-29 — Fase 2 rebanada 1 (andamiaje de forecasting)
- `PuertoForecaster` (puerto) + entidad `Observacion` (serie histórica observada).
- `MetricasForecast` (servicio puro): RMSE y MAPE (MAPE omite reales nulos, p. ej. PV nocturna).
- `ForecasterEstacionalNaive` (infra, numpy): baseline estacional-naïve + bootstrap de residuos → escenarios probabilísticos **deterministas** (escenario 0 = puntual). Es el piso a batir por SARIMAX/LSTM (ADR-002).
- Integración demostrada: forecast → escenario → `OptimizadorLP` → plan factible.
- Verde: ruff/mypy/import-linter OK · pytest **57 passed** (+10).

### 2026-06-29 — Cierre de deuda pre-Fase 2

### 2026-06-28 — Cierre de deuda pre-Fase 2
- **SoC terminal:** `PoliticaDespacho.precio_energia_final_mills_por_mwh` (opcional) valoriza la energía final → no liquida la batería por fin de horizonte.
- **Estado inicial fuera de banda:** el optimizador valida y lanza `ValueError` (REST → 422).
- **Curtailment voluntario a CMg negativo:** confirmado por test (vierte PV en vez de inyectar a pérdida).
- **Horizonte de 1 intervalo:** test de borde.
- Verde: ruff/mypy/import-linter OK · pytest **47 passed**.
- Deuda restante (a futuro): escenario único (Fase 3), re-clamp de retiro en cuantización, converger a banda si SoC inicial fuera de rango.

### 2026-06-28 — Curtailment / límite de transmisión (post-Fase 1)
- Nueva entidad `Planta` (PV + batería + punto de conexión): `potencia_max_inyeccion` / `potencia_max_retiro`. La firma del optimizador, el caso de uso y el REST ahora usan `Planta` (antes `Bateria`).
- El optimizador LP modela `vertido` (curtailment) con restricción de inyección al nodo; el plan registra `energia_vertida_wh` por intervalo y la `FuncionObjetivo` lo descuenta.
- Demostrado: la batería carga el exceso de PV para reducir vertimiento y vende en la tarde cara; el sobrante real se vierte (es el problema de los 6 TWh chilenos).
- Verde: ruff/mypy/import-linter OK · pytest **43 passed**.
- Deuda nueva: re-clamp del límite de retiro en la cuantización; curtailment voluntario a CMg negativo.

### 2026-06-28 — Fase 1 cerrada (despacho determinista + REST)
- Entidades del problema (Escenario, PoliticaDespacho versionada, PlanDespacho, Rastro) + `Precio` (CMg mills/MWh, admite negativos).
- `OptimizadorLP` predict-then-optimize con **cvxpy + HIGHS**; salida cuantizada a enteros y validada contra `ModeloBateria` → siempre factible. `FuncionObjetivo` da el ingreso auditable.
- Caso de uso `PlanificarDespacho` (fija política + persiste snapshot). REST FastAPI (`POST /planes`, `GET /planes/{id}`, `/salud`) con DTOs Pydantic v2.
- Verde: ruff OK · mypy 39 files 0 issues · import-linter 2 KEPT · pytest **35 passed**.
- **Deuda:** efecto fin de horizonte (SoC terminal sin valor → puede liquidar batería); escenario único (estocástico en Fase 3); repair conservador a RETENER.
- **Incidente:** disco C: llegó a 0 GB libres (corrompió cachés mypy/import-linter); liberado con `pip cache purge`. OJO: disco crítico, el usuario debe liberar espacio.
- Dependencias nuevas: cvxpy 1.9.2 (HIGHS), fastapi, uvicorn, pydantic, httpx (dev).

### 2026-06-28 — Fase 0 cerrada (scaffolding + dominio)

### 2026-06-28 — Fase 0 cerrada (scaffolding + dominio)
- Andamiaje completo: `pyproject.toml` (uv·ruff·mypy --strict·import-linter), capas Clean Architecture, value objects enteros, entidades y `ModeloBateria` puro (SoC, eficiencia, throughput de garantía).
- Property-tests con hypothesis: determinismo, factibilidad (0 violaciones SoC/potencia), reproducibilidad de secuencias.
- Verificación verde: ruff OK · mypy 20 files 0 issues · import-linter 2 contratos KEPT · pytest 23 passed.
- Toolchain corre con Python 3.13 local (no había 3.12; requires-python>=3.12 respetado). uv no instalado en la máquina — se usó venv directo con py -3.13.
- Deuda a Fase 1+: autodescarga, C-rate explícito, Protocols de puertos.

### 2026-06-28 — Rename Ergia → Acopia
- "Ergia" descartado: colisión con **Ergia.ai** (ya existe) y cercanía fonética con **ENGIE** (gran actor BESS en Chile, dueño de BESS Coya).
- Nuevo nombre **Acopia** (de "acopio" = almacenamiento), verificado sin colisión obvia en energía-IA. Identificador técnico: `acopia`.
- Pendiente: confirmar dominios .ai/.cl e INAPI. Archivo del SAD renombrado a `SAD_Acopia_energia.md`.

### 2026-06-28 — SAD revisado y endurecido + documentación viva creada
- Revisión "vista de halcón" del SAD orientada a integrador BESS / energytech chilena.
- **Reencuadre de mercado:** Chile es despacho centralizado por costos (CMg), no ofertas por precio. Se pronostica/arbitra CMg, no se oferta. Añadida §3.0 (Modelo de mercado eléctrico, Ley 21.505, revenue stacking).
- **Decisión de alcance:** el MVP **co-optimiza arbitraje + servicios complementarios (SSCC)** en una sola función objetivo (fase 4). Potencia de suficiencia queda en fase 5.
- **Cifras de curtailment verificadas (fuentes 2025/2026):** 2025 = 6.084 GWh vertidos (+7,8 % vs 2024); ene-2022–may-2025 ≈ 11.900 GWh ≈ US$562 M perdidos; sin BESS habría llegado a ~8 TWh.
- **Ajustes técnicos:** programación estocástica (MILP dos etapas) nombrada; batería con C-rate + throughput de garantía; 34% RMSE etiquetado como referencia del paper, no promesa; DRL reposicionado como experimento de investigación.
- **Honestidad de datos:** telemetría plant-level no es pública → reoptimización intradía se demuestra con planta modelo sintética.
- **Creada la documentación viva:** `CLAUDE.md`, `MEMORY.md`, `docs/AUDIT.md`, `docs/CASES.md`, `docs/TROUBLESHOOTING.md`.

## Decisiones abiertas / pendientes
- **Renombrar la carpeta local `ergia` → `acopia`** (solo cosmético; paquete/repo/GitHub ya son `acopia`). Se hace al cerrar la sesión y reabrir VSCode/Claude en la nueva ruta (no se puede en caliente).
- Confirmar dominios **acopia.ai / acopia.cl** con WHOIS en vivo (búsqueda web no mostró registro, pero no es prueba). `acopia.com` probablemente tomado (hipotecaria usa myacopia.com).
- **INAPI:** registrar marca en clase software/energía (Niza 9/42/39-40). Homónimos en otros sectores no bloquean: Acopia Networks (IT, muerta tras compra de F5 en 2007), Acopia LLC (hipotecaria US), Acopia Ventures (VC), ACOPIA (ONG). Cero colisión en energía/energytech/Chile.
- ¿Modelar SSCC con un solo producto (reserva de frecuencia) en fase 4 o varios desde el inicio?
- Fuente concreta de datos: API del Coordinador Eléctrico Nacional para CMg + Explorador Solar para irradiancia.
