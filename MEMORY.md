# MEMORY.md — Bitácora · Acopia

> Decisiones, hallazgos no obvios y estado actual. Se actualiza al final de cada sesión y ante cada decisión relevante. Lo más reciente arriba.

## Estado actual

- **Fase:** 2 en curso — rebanadas 1 (forecasting), 1b (ingesta CSV), 1c (CLI datos), 2 (SARIMAX) y **3 (Seq2Seq-LSTM)** completas. Fase 1 + deuda cerradas.
- **Próxima acción (Fase 2, cierre):** validar el forecaster sobre **datos chilenos reales** (descarga manual XLS de CMg + Explorador Solar, ver abajo) y persistir el **snapshot as-seen** del forecast (ADR-007) — es el gate de cierre de fase. Luego: comparación honesta LSTM vs SARIMAX sobre datos reales; deuda de persistencia de pesos (hoy se re-entrena por llamada).
- **Datos reales (cómo obtenerlos) — ver bitácora 2026-06-29 "API real del Coordinador":** la vía práctica es **descarga manual del XLS** de CMg (una barra, rango de fechas) + exportar generación del Explorador Solar, y unir con `acopia-datos alinear --por-posicion`. La API existe pero NO conviene para bulk (ver abajo).

## Bitácora

### 2026-07-01 — PRIMER entrenamiento sobre datos reales chilenos (hito Fase 2)
- **Datos reales alineados:** CMg **S.GREGORIO____013, enero 2025** (744 h, XLSX del Coordinador) + generación PV **TMY Antofagasta** (Explorador Solar, `pv` en kWh, planta 1 kW). En `datos/` (git-ignored). Comando: `alinear --por-posicion --recortar --col-hora-cmg Hora --col-cmg "S.GREGORIO" --escala-cmg 1000 --col-ts-gen "Fecha/Hora" --col-gen pv --escala-gen 1000 --fila-encabezado-gen 55`.
- **Perfil confirmado (la tesis de Acopia en datos reales):** generación pico ~693 W a las 13h; **CMg colapsa a ~3–8k mills/MWh a mediodía** (240 h a CMg=0 por sobreoferta solar) y se dispara a ~97k a las 21h. Ese diferencial es el arbitraje.
- **Backtest rodante 5 días (promedios, pronóstico 24h, ventana expansiva):**
  - gen RMSE: LSTM **51.3** · naive 57.9 · SARIMAX 66.8
  - **CMg RMSE: LSTM 27.4k · SARIMAX 34.9k · naive 42.8k** → LSTM **−36% vs naive**, −21% vs SARIMAX. CMg MAPE: LSTM 31.8% · SARIMAX 41% · naive 50.8%.
  - **El LSTM gana en el target difícil (CMg)**, que es el que importa para el arbitraje. El −36% está cerca del ~34% del paper, PERO con reservas fuertes: 1 mes, 1 barra, generación TMY (no telemetría real de planta), test de 5 días. **Direccional, no validación del número del paper.**
- **Ajustes de pipeline para lograrlo:** `leer_serie_csv` ahora acepta `fila_encabezado` (saltar los ~54 metadatos del TMY) y omite filas en blanco al final; flag CLI **`--recortar`** (opt-in) recorta ambas series al largo menor (CMg 1 mes vs gen 1 año) sin ocultar desfases.
- **Backtest versionado:** `application/backtest.py` (`backtest_rodante`, puro, sobre `PuertoForecaster`) + subcomando `acopia-datos backtest --planta datos/planta.csv --folds 5 --modelos naive,sarimax,lstm` (LSTM opcional si hay torch). Reproduce exactamente los números de arriba.
- Verde: ruff/mypy(61)/import-linter OK · pytest **104 passed**.
- **Próximo:** más datos reales de CMg (≥6–12 meses, misma barra) para un backtest serio; snapshot as-seen (ADR-007) para cerrar Fase 2.

### 2026-07-01 — Lector del formato ANCHO real del Coordinador (CMg XLSX)
- El usuario mostró el .xlsx real de CMg: columnas **`Fecha | Día | Hora | Barra | <NOMBRE_BARRA>`**. Peculiaridades: (1) el timestamp está **partido** en `Fecha` + `Hora` (0..23); (2) `Fecha` es **celda combinada por día** (openpyxl read_only devuelve el valor en la fila superior/ancla, `None` en el resto → forward-fill); (3) la columna de CMg **se titula con el mnemónico de la barra** (ej. `S.GREGORIO____013`), y la columna `Barra` va vacía; (4) valores con **coma chilena** y `0,00` a mediodía (CMg colapsa por sobreoferta solar).
- `leer_serie_xlsx` ahora acepta **`columna_hora`**: trata `columna_ts` como fecha, forward-fill de la celda combinada, y arma `YYYY-MM-DDTHH:00`. Nuevo **matching tolerante** de columnas (`_indice_columna`): `--col-cmg "S.GREGORIO"` calza con `S.GREGORIO____013` sin adivinar los guiones bajos. CLI: `--col-hora-cmg` / `--col-hora-gen`.
- **Comando para el CMg real:** `acopia-datos alinear --por-posicion --cmg CMg.xlsx --col-ts-cmg Fecha --col-hora-cmg Hora --col-cmg "S.GREGORIO" --escala-cmg 1000 --generacion <gen> ... --salida planta.csv`.
- Verde: ruff/mypy(59)/import-linter OK · pytest **97 passed** (+3, con fixture que emula el formato ancho + celdas combinadas).
- **Falta:** ver el formato del export del Explorador Solar (generación) para fijar `--col-ts-gen`/`--col-gen`/`--col-hora-gen`/`--escala-gen`.

### 2026-06-29 — Lector XLSX en el pipeline de ingesta (datos reales)
- **Por qué:** las descargas del Coordinador (CMg) y del Explorador Solar (generación) vienen en **.xlsx**; antes había que convertir a CSV a mano. Ahora `acopia-datos alinear` acepta .csv **o** .xlsx directo.
- **`leer_serie_xlsx`** (openpyxl, `infrastructure/ingesta/preparacion.py`): lee una hoja a `Serie`, maneja celdas **nativas** (datetime → ISO, número float/int) y **texto con coma chilena** (reusa `parsear_decimal`). Flags `--hoja-*` y `--fila-encabezado-*` para saltar metadatos sobre la tabla. `leer_serie` despacha por extensión.
- **Gap real encontrado por un test:** `alinear` no tenía escala para CMg. Agregado **`--escala-cmg`** (default 1.0; usar **1000** porque el Coordinador da CLP/kWh y el dominio quiere mills/MWh). Antes solo existía `--escala-gen`.
- `openpyxl` es extra **opcional** `acopia[ingesta]` (+ override mypy). Si falta, `leer_serie_xlsx` lanza un error claro.
- Verde: ruff/mypy(59)/import-linter OK · pytest **94 passed** (+6).
- **Próximo paso operativo:** el usuario baja el XLS de CMg de UNA barra (rango de fechas) y exporta la generación del Explorador Solar; luego `acopia-datos alinear --por-posicion --escala-cmg 1000 ...` → CSV de planta → entrenar/validar el forecaster sobre datos reales.

### 2026-06-29 — Fase 2 rebanada 3 (forecaster Seq2Seq-LSTM)
- `ForecasterSeq2SeqLSTM` (PyTorch CPU, `infrastructure/forecasting/forecaster_lstm.py`) detrás del mismo `PuertoForecaster`: encoder-decoder LSTM sobre 2 features estandarizadas (gen, CMg), entrena por llamada (full-batch Adam+MSE, teacher forcing). Escenario 0 = puntual; resto = punto + `N(0, σ)` con σ de residuos de entrenamiento.
- **Determinismo:** `torch.manual_seed(semilla)` antes de crear el modelo y entrenar + `np.random.default_rng(semilla)` para el ruido, sin shuffle (full-batch), CPU. Misma `(historia, semilla)` → mismos escenarios (test lo verifica).
- `torch` es dependencia **opcional** (`pip install -e ".[forecasting]"`, rueda CPU `--index-url https://download.pytorch.org/whl/cpu`). Frontera dura intacta: import-linter sigue prohibiendo torch en `domain/`. torch 2.12.1+cpu instalado en `.venv` (Python 3.13).
- **Honestidad (clave):** con datos sintéticos el LSTM **no** bate al naive cuando la señal es limpia (el naive es casi perfecto); solo gana de forma robusta cuando el baseline tiene **sesgo estructural** (tendencia). Por eso el test de comparación usa datos con tendencia, y hay un test de *learnability* (reproduce señal periódica). NO se tuneó la data para fabricar un verde. La cifra del paper (~34%) NO está demostrada (faltan datos reales).
- Comparación 3-vías (set tendencia, RMSE gen/CMg): naive `8/2000` · SARIMAX `33/14283` (orden sin estacional, sensible) · LSTM `1.12/420`.
- Verde: ruff/mypy(59)/import-linter OK · pytest **88 passed** (+7). ~11.7s (el LSTM entrena por test).
- Deuda: validar sobre datos reales, persistir pesos (no re-entrenar por llamada), snapshot as-seen (ADR-007), MC-dropout/ensembles para escenarios.

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
