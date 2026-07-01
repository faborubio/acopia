# AUDIT.md — Auditoría por fase (Vista de halcón) · Acopia

> Cada fase cierra con una entrada aquí y un **sign-off**. La auditoría incluye, cuando aplica, **auditoría de forecast** (RMSE/MAPE vs baseline) y **validación de factibilidad** (0 violaciones de SoC/potencia). Lo pendiente pasa a deuda/roadmap, no se borra.

## Plantilla de entrada

```text
## Fase N — <nombre> — <estado: en curso | cerrada> — <fecha>
**Qué se entregó:** ...
**Verificación:** tests / property-tests / métricas (RMSE, MAPE, factibilidad, latencia)
**Vista de halcón (qué quedó débil):** ...
**Deuda generada:** ...
**Sign-off:** <responsable> — <fecha>
```

---

## Cierre de deuda (post-Fase 1, pre-Fase 2) — 2026-06-28

> Antes de avanzar a Fase 2 se atendió la deuda acumulada.

**Resuelto:**
- **Efecto fin de horizonte:** `PoliticaDespacho.precio_energia_final_mills_por_mwh` (opcional) valoriza la energía final; con él, la batería no se liquida solo porque el horizonte termina. Test `test_valor_energia_final_evita_liquidacion`.
- **Curtailment por límite de transmisión + voluntario a CMg negativo:** entidad `Planta` + variable de vertido en el LP. Tests de curtailment y `test_curtailment_voluntario_a_cmg_negativo`.
- **Estado inicial fuera de banda:** validación con `ValueError` claro (REST → 422). Test `test_estado_inicial_fuera_de_banda_es_error`.
- **Horizonte de un intervalo:** `test_horizonte_de_un_intervalo`.

**Verificación:** ruff OK · mypy --strict 40 files 0 issues · import-linter 2 KEPT · pytest **47 passed**.

**Deuda que queda (consciente, a fases futuras):**
- Optimización sobre un solo escenario (estocástico → Fase 3).
- Re-clamp del límite de retiro en la cuantización (hoy solo en el LP).
- Permitir converger a la banda cuando el SoC inicial está fuera (hoy se rechaza).
- Valor terminal por defecto sigue siendo `None` (liquidación posible si no se configura): es una decisión del operador.

---

## Fase 2 — Forecaster + escenarios — en curso — 2026-06-29

> Entrada interim por rebanada. La fase cierra cuando el forecaster se valide sobre datos chilenos reales (no solo sintéticos) y se persista el snapshot as-seen.

**Qué se entregó (datos reales + backtest — 2026-07-01):**
- **Primer entrenamiento sobre datos reales chilenos:** CMg S.GREGORIO____013 enero 2025 (Coordinador, XLSX) + generación PV TMY Antofagasta (Explorador Solar, CSV) → `datos/planta.csv` (744 h, git-ignored). Pipeline: `leer_serie_csv` con `fila_encabezado` (salta metadatos del TMY) + flag `--recortar`.
- **Servicio `application/backtest.py`** (`backtest_rodante`): ventana expansiva, orquesta `PuertoForecaster` + `MetricasForecast`, puro (sin infra). Subcomando `acopia-datos backtest` cablea los 3 forecasters (LSTM opcional si hay torch).
- **Resultado (backtest rodante 5 días, 24h, promedios):**
  - gen RMSE: LSTM 51.3 · naive 57.9 · SARIMAX 66.8
  - **CMg RMSE: LSTM 27.4k · SARIMAX 34.9k · naive 42.8k → LSTM −36% vs naive, −21% vs SARIMAX.** CMg MAPE: LSTM 31.8% · SARIMAX 41% · naive 50.8%.
  - Lectura honesta: el LSTM gana en el target difícil (CMg). El −36% roza el ~34% del paper, pero con reservas fuertes (1 mes, 1 barra, generación TMY, 5 folds): **direccional, no validación**.

**Qué se entregó (ingesta — lector XLSX):**
- `leer_serie_xlsx` (openpyxl, opcional `acopia[ingesta]`) + despacho por extensión en `leer_serie`: `acopia-datos alinear` acepta .csv o .xlsx (formato real del Coordinador / Explorador Solar). Maneja celdas nativas (datetime, número) y texto con coma chilena; `--hoja-*`/`--fila-encabezado-*` saltan metadatos.
- Nuevo flag `--escala-cmg` (CLP/kWh → mills/MWh con 1000); cierra un gap que un test destapó (antes solo había `--escala-gen`).
- **Desbloquea la ingesta de datos reales:** falta solo que el operador descargue los archivos.

**Qué se entregó (rebanada 3 — Seq2Seq-LSTM):**
- `ForecasterSeq2SeqLSTM` (PyTorch, CPU) detrás del mismo `PuertoForecaster`: encoder-decoder LSTM sobre 2 features estandarizadas (generación PV, CMg), entrenado por llamada (full-batch Adam + MSE, teacher forcing). Escenario 0 = pronóstico puntual; los demás suman `N(0, σ)` con σ de los residuos de entrenamiento. **Determinista** (semillas PyTorch + numpy, sin shuffle, CPU).
- `torch` como dependencia **opcional** (`[forecasting]`); rueda CPU. El núcleo determinista no la requiere. Frontera dura intacta: `import-linter` sigue prohibiendo `torch` en `domain/`.
- Rebanadas previas (1, 1b, 1c, 2): baseline estacional-naïve, gateway de ingesta CSV, CLI `acopia-datos`, SARIMAX. Ver bitácora en `MEMORY.md`.

**Verificación (todo en verde):** ruff OK · mypy --strict 61 files 0 issues · import-linter 2 KEPT · pytest **104 passed** (LSTM +7, XLSX +6, formato ancho/CSV +6, backtest +4).
- Tests del LSTM: forma/cantidad, **determinismo** (misma semilla → mismos escenarios), generación no negativa, historia insuficiente, escenario-0-sin-ruido, **learnability** (reproduce una señal periódica, RMSE < 5 sobre pico de 90) y **comparación**: bate al estacional-naïve en RMSE sobre datos con tendencia.
- Comparación 3-vías (set sintético período-4 + tendencia, RMSE gen / CMg): naive `8.00 / 2000` · SARIMAX `33.3 / 14283` · **LSTM `1.12 / 420`**.

**Vista de halcón (qué quedó débil):**
- **Honestidad de datos:** sin datos chilenos reales el LSTM se entrena sobre sintéticos. Esta rebanada entrega **arquitectura + pipeline determinista**, NO la cifra del paper (~34% menos RMSE). El objetivo verificable de ADR-002 ("batir al baseline en nuestro set") solo es honestamente exigible donde el baseline tiene sesgo estructural (tendencia); ahí el LSTM gana robustamente.
- **SARIMAX es sensible a la especificación de orden:** el `33.3` de arriba es con un orden sin componente estacional; con el orden adecuado mejora. La comparación seria contra SARIMAX se hará sobre datos reales, no sobre este set.
- **Entrenamiento por llamada:** consistente con SARIMAX, pero costoso para horizontes largos / históricos grandes. Un modo entrenar-una-vez / persistir-pesos es deuda futura.
- **Generación de escenarios por ruido gaussiano** sobre el punto, no muestreo del espacio latente (MC dropout / ensembles) — suficiente para el MVP.

**Deuda generada:** validar sobre datos chilenos reales; persistencia de pesos (no re-entrenar por llamada); snapshot as-seen del forecast (ADR-007, pendiente para cierre de fase); comparación honesta LSTM vs SARIMAX sobre datos reales.
**Sign-off:** (pendiente — fase en curso).

## Fase 1 — Despacho determinista — cerrada — 2026-06-28

**Qué se entregó:**
- Entidades del problema: `Escenario`/`PuntoPronostico`, `PoliticaDespacho` (versionada), `PlanDespacho`, `RastroDespacho`; value object `Precio` (CMg en mills/MWh, admite negativos).
- `FuncionObjetivo` pura: ingreso bruto auditable de un plan + costo de ciclado.
- Puertos `PuertoOptimizador` y `RepositorioPlanes` (Protocols en el dominio).
- `OptimizadorLP` (infra): predict-then-optimize determinista con **cvxpy + HIGHS**; el plan continuo se **cuantiza a enteros y se valida contra `ModeloBateria`** (factibilidad garantizada).
- Caso de uso `PlanificarDespacho`: fija política, optimiza, persiste plan + rastro (snapshot as-seen).
- Repositorio en memoria.
- **REST (FastAPI):** `POST /planes`, `GET /planes/{id}`, `GET /salud`; DTOs Pydantic v2 con mapeo DTO<->dominio en `interfaces/`.

**Verificación (todo en verde):**
- `ruff` OK · `mypy --strict` 39 files 0 issues · `lint-imports` 2 contratos KEPT · `pytest` **35 passed**.
- Tests clave: arbitraje "compra barato/vende caro" (ingreso 49.000 mills exacto), plan factible (replay con ModeloBateria), determinismo (mismo plan), ingreso auditable, persistencia con rastro, y REST (200/422/404).

**Vista de halcón (qué quedó débil / deuda):**
- **Efecto fin de horizonte:** el modelo aún no valoriza el SoC terminal, así que con precio positivo y sin diferencial puede liquidar la batería al final del horizonte. Deuda Fase 2/3: valor o restricción de SoC terminal.
- Optimización sobre **un solo escenario** (caso medio); la programación estocástica sobre escenarios llega en Fase 3.
- Cuantización entera con repair conservador a RETENER ante violaciones de redondeo: correcto pero puede dejar ingreso marginal sobre la mesa en bordes.
- Warning cosmético de deprecación httpx/starlette en TestClient (no afecta).

**Incidente de entorno:** durante la verificación el disco C: llegó a **0 GB libres**, corrompiendo cachés de mypy/import-linter. Se liberó espacio con `pip cache purge` (~132 MB). **Acción pendiente del usuario:** liberar disco; queda muy ajustado.

**Deuda generada:** SoC terminal, escenario único, repair conservador.
**Sign-off:** ✅ 2026-06-28.

## Fase 0 — Scaffolding — cerrada — 2026-06-28

**Qué se entregó:**
- Documentación viva (`CLAUDE.md`, `MEMORY.md`, `docs/`); SAD revisado y endurecido (mercado chileno, SSCC en MVP, cifras verificadas).
- Andamiaje: `pyproject.toml` (hatchling) con toolchain uv·ruff·mypy --strict·import-linter; `.gitignore`; `README.md`.
- Esqueleto de capas Clean Architecture: `domain/` (puro), `application/`, `infrastructure/`, `interfaces/`.
- Value objects enteros (deterministas): `Energia`, `Potencia`, `Eficiencia`, `Soc`, `Intervalo`.
- Entidades: `Bateria`, `EstadoBateria`, `AccionDespacho`.
- Servicio `ModeloBateria` puro: dinámica de SoC, eficiencia carga/descarga, límites de potencia y **throughput de garantía**.
- `docker-compose.yml` con TimescaleDB (pg16).

**Verificación (todo en verde):**
- `ruff check .` → All checks passed.
- `mypy --strict` → Success, 20 source files, 0 issues.
- `lint-imports` → 2 contratos KEPT (dominio puro sin libs pesadas/capas; aplicación sin adaptadores).
- `pytest` → 23 passed (incluye property-tests de **determinismo**, **factibilidad** —0 violaciones de SoC/potencia— y reproducibilidad de secuencias, con hypothesis).

**Vista de halcón (qué quedó débil / deuda):**
- Autodescarga de la batería ignorada a esta fidelidad (documentado en `modelo_bateria.py`; deuda de §11).
- C-rate implícito en `potencia_max_*`; aún no es un parámetro propio.
- Puertos (`ports/`) declarados como paquete pero sin Protocols todavía (llegan en Fase 1 con los casos de uso).
- Toolchain corre con Python 3.13 local (no 3.12); `requires-python>=3.12` se respeta.

**Deuda generada:** autodescarga, C-rate explícito, Protocols de puertos — todo trasladado a Fase 1+.
**Sign-off:** ✅ 2026-06-28.
