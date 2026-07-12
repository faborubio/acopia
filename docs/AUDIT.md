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

## Registro de deuda técnica (`AUD-NNN`)

> Regla del método: **todo trade-off aceptado tiene su `AUD-NNN`** — un trade-off sin entrada aquí es deuda invisible. Este registro numera la deuda viva y la pagada; el detalle narrativo sigue en el log por fase (abajo). Al pagar una deuda: cambiar el estado y anotar dónde se pagó, no borrar la fila.

### Deuda viva

| ID | Deuda | Origen | Estado / plan |
|---|---|---|---|
| AUD-001 | **Autodescarga de la batería** ignorada en `ModeloBateria` (documentado en `modelo_bateria.py`). | F0 | Pendiente — modelarla como pérdida por intervalo cuando haya datos de un BESS real. |
| AUD-002 | **C-rate implícito** en `potencia_max_*`; no es parámetro propio de `Bateria` (ADR-003 lo nombra). | F0 | Pendiente — explícito cuando se modele un activo real. |
| AUD-004 | **SoC inicial fuera de banda se rechaza** (`ValueError` → 422) en vez de permitir converger a la banda. | F1 | Pendiente — modo "converger" opt-in de la política. |
| AUD-005 | **Ventana régimen-local sin sweep**: 720 obs replica la config ganadora de enero; falta barrido de ventana/hiperparámetros y una regla de selección por régimen (hidrología/estación). | F3 | **Parcialmente pagada (2026-07-12)** — el sweep de ventana corrió (168/336/720/1440/2160/4320 h, anual 7 folds, mismas condiciones): **720 confirmada como mínimo** (CMg RMSE 20.3k) dentro de una **meseta 336–2160** que bate al naive completa (−17% a −23%); degradación clara en los extremos (168: 32.7k; 4320: 36.3k). Evidencia: enmienda ADR-002.2 y `docs/CASES.md`. **Sigue viva:** sweep de hiperparámetros del modelo (ventana de entrada/hidden/épocas) y regla de selección de ventana por régimen. |
| AUD-006 | **Backtest de política corre con naive**; falta la corrida con LSTM-ventana como forecaster de la política (~25 s/día). | F3 | Pendiente. |
| AUD-007 | **Escenarios del estocástico vienen del bootstrap del naive**, no del forecaster avanzado. | F3 | Pendiente — alimentar ADR-004 con escenarios del LSTM. |
| AUD-008 | **Gatillo de desvío mono-señal**: mira solo generación acumulada; no CMg ni estado de batería. | F3 | Pendiente. |
| AUD-009 | **LSTM/SARIMAX/DRL entrenan por llamada**; sin persistencia de pesos ni modo entrenar-una-vez (el PPO de `OptimizadorDRL` re-entrena en cada `optimizar`). | F2 (F4 lo extiende) | Pendiente — costoso a escala, aceptable en portafolio. |
| AUD-010 | **`RastroForecast` no se persiste** junto al `RastroDespacho` (enmienda ADR-007.1). | F2 | Pendiente — fase de persistencia real (Timescale). |
| AUD-011 | **El rastro no persiste la política completa** (batería/resolución llegan por inyección al servidor MCP). | F4 | Pendiente — fase de persistencia real, junto con AUD-010. |
| AUD-012 | **Telemetría de planta sintética** (plant-level no es pública, SAD §6.2): la reoptimización intradía se demuestra con desvíos sintéticos. | F3 | Aceptada para portafolio — datos reales exigen un activo real (fase 5). |
| AUD-013 | **Escenarios por ruido gaussiano** sobre el punto, no muestreo latente (MC dropout / ensembles). | F2 | Aceptada para el MVP. |
| AUD-014 | **Falta test del optimizador con garantía de throughput casi agotada** (el caso "agotada = 0" sí está cubierto). | F1 | Pendiente — test de borde. |
| AUD-015 | **Valor terminal por defecto `None`**: sin configurarlo, la batería puede liquidarse al fin de horizonte. | F1 | Aceptada — es una decisión del operador, documentada en `CASES.md` (precio plano). |
| AUD-023 | **El modo DRL no co-optimiza SSCC** (`politica.reserva` → error claro): el experimento de ADR-005 es arbitraje puro; añadir la banda al espacio de acción/recompensa es trabajo de fase 5 si el DRL lo justifica. | F4 | Aceptada — coherente con ADR-005 (experimento, no producto). |
| AUD-024 | **Valorización duplicada entre LP y DRL**: `_ingreso_esperado` y el recurso de vertido viven en ambos optimizadores (~40 líneas paralelas); extraer un helper común en `infrastructure/optimizacion/`. | F4 | Pendiente — refactor menor; se aceptó para no tocar el LP probado en la misma rebanada. |
| AUD-025 | **La observación del DRL no incluye el throughput restante** ni la banda SSCC; con garantía holgada es irrelevante, pero un agente cerca del límite de ciclado decidiría a ciegas. | F4 | Pendiente — añadir al vector de observación si el modo DRL pasa de experimento a opción real. |

### Deuda pagada

| ID | Deuda | Origen | Pagada en |
|---|---|---|---|
| AUD-016 | Puertos sin Protocols (paquete vacío). | F0 | F1 — `PuertoOptimizador`, `RepositorioPlanes` y sucesores. |
| AUD-017 | Efecto fin de horizonte (liquidación de la batería). | F1 | Cierre de deuda 2026-06-28 — `precio_energia_final_mills_por_mwh` opcional. |
| AUD-018 | Curtailment voluntario a CMg negativo sin cubrir. | F1 | Cierre de deuda 2026-06-28 — `test_curtailment_voluntario_a_cmg_negativo`. |
| AUD-019 | Optimización sobre un solo escenario (caso medio). | F1 | F3 rebanada 1 — estocástico de dos etapas (ADR-004). |
| AUD-020 | LSTM régimen-dependiente: pierde en el anual con config fija (hallazgo F2). | F2 | F3 cierre — ventana régimen-local 720 (enmienda ADR-002.1): CMg RMSE 20.3k vs 26.2k naive. |
| AUD-021 | SARIMAX anual impráctico (ventana expansiva). | F2 | F3 cierre — la misma ventana régimen-local lo baja a segundos (no bate al naive). |
| AUD-022 | Snapshot as-seen del forecast inexistente. | F2 | F2 — `RastroForecast` + huella SHA-256 (ADR-007.1). Persistirlo sigue vivo como AUD-010. |
| AUD-003 | Re-clamp del límite de retiro en la cuantización + repair a RETENER que anulaba el intervalo completo. | F1 | F4 rebanada DRL — `OptimizadorLP._accion_recortada`: la acción se recorta al máximo factible (SoC, potencia, throughput, nodo) en vez de anularse. Hallazgo: el experimento ADR-005 destapó que el repair perdía la descarga de la hora más cara del día (~15% del ingreso en días reales). |

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

## Fase 4 — Co-optimización SSCC + Capa MCP + modo DRL (MVP) — cerrada — 2026-07-09

> Entregable del SAD §13: "Co-optimización arbitraje + SSCC en una sola función objetivo; MCP read-only + simulación; modo DRL opcional medido contra el baseline" — **completo**. Con la Fase 4 cierra el alcance de portafolio recomendado por el SAD (fases 1–4).

**Qué se entregó (rebanada 3 — modo DRL, 2026-07-09):**
- **`OptimizadorDRL`** (PPO de stable-baselines3, extra `acopia[drl]`) detrás del mismo `PuertoOptimizador` que el LP (ADR-005): entrena por llamada sobre el escenario as-seen y produce un `PlanDespacho` con acciones enteras validadas contra `ModeloBateria` e ingreso calculado por la `FuncionObjetivo` del dominio — **cifras comparables una a una con el baseline**. Determinista (semillas numpy/torch/PPO, CPU); rechaza `politica.reserva` con error claro (AUD-023).
- **`EntornoDespacho`** (gymnasium): acción continua [-1,1] **recortada a lo físicamente factible** (SoC, potencia, throughput, nodo) — el agente no puede violar restricciones, solo perder ingreso; vertido como recurso analítico óptimo según el signo del CMg (la misma regla de recurso que el LP).
- **`comparar_modos`** (aplicación + herramienta MCP + CLI `acopia-datos comparar-modos`): ambos modos sobre el mismo rastro as-seen, sin persistencia.
- **Experimento medido (enero real S.GREGORIO, 3 días, forecast perfecto, PPO 30k timesteps/día, semilla 0):** captura DRL vs LP por día **97.7% / 95.1% / 94.9%** — total **96.1%**, el LP gana siempre. La postura de ADR-005 queda medida: para el arbitraje de una planta, el MILP es casi óptimo y el DRL no justifica la pérdida de interpretabilidad.
- **El hallazgo mayor fue del baseline, no del DRL:** la primera corrida daba al DRL **104.6%** — imposible contra un óptimo. La causa: la **deriva de floors** de la eficiencia entera dejaba la descarga de la hora más cara infactible por ~1 Wh y el repair a RETENER la **anulaba entera** (~15% del ingreso del día). Arreglado con `_accion_recortada` (recorta al máximo factible; paga AUD-003); el LP subió de 869 a 946 mills (+8.9%) en los mismos 3 días. Regresión fijada en `test_cuantizacion_lp.py`; caso en `CASES.md`. **Moraleja: si el experimento supera al óptimo, audita al óptimo.**

**Qué se entregó (rebanadas 1 y 2, 2026-07-02):** co-optimización arbitraje + reserva de frecuencia (ADR-010; banda simétrica por disponibilidad; comportamientos emergentes fijados por test) y capa MCP read-only (`consultar_despacho`, `explicar_despacho`, `simular`; `ExplicadorDespacho` en dominio; `simular_escenario` sin persistencia). Detalle en la bitácora (`MEMORY.md` 2026-07-02).

**Verificación (todo en verde, al cierre):** ruff OK · mypy --strict 91 files 0 issues · import-linter 2 KEPT (gymnasium añadido a la frontera) · pytest **198 passed** (DRL +8, comparar_modos +4, MCP 4 herramientas +2, regresión cuantización +1) · pip-audit sin vulnerabilidades.

**Vista de halcón (qué quedó débil):**
- El PPO **entrena por llamada** (AUD-009 extendido): cada `optimizar` cuesta segundos-minutos según `total_timesteps`.
- La comparación usa **forecast perfecto** (mide el optimizador, no el pipeline completo); comparar con forecast real + ejecución (`SimuladorEjecucion`) daría la cifra de negocio.
- 3 días y una semilla: **direccional**, no estadística. El DRL con más presupuesto/tuning puede acercarse más al LP; nunca superarlo en el determinista.
- La observación del DRL no ve throughput restante ni banda SSCC (AUD-025); no co-optimiza SSCC (AUD-023).
- Valorización duplicada LP/DRL (~40 líneas, AUD-024).

**Deuda generada:** AUD-023 (DRL sin SSCC, aceptada), AUD-024 (valorización duplicada), AUD-025 (observación DRL incompleta). **Deuda pagada:** AUD-003 (repair de cuantización → recorte factible).
**Sign-off:** ✅ 2026-07-09 — entregable del SAD §13 completo; el DRL quedó donde ADR-005 lo puso: experimento medido que valida al baseline (y que de paso lo mejoró).

## Fase 3 — Robustez + backtest — cerrada — 2026-07-02

> Entregable del SAD §13: "Optimización sobre escenarios; backtest sobre histórico chileno; reoptimización intradía" — **completo**, con la deuda de Fase 2 saldada empíricamente.

**Qué se entregó:**
- **Optimizador estocástico de dos etapas (ADR-004):** `PuertoOptimizador.optimizar_escenarios` — programa de batería here-and-now común a todos los escenarios; vertido como recurso por escenario; factibilidad exigida en todos; objetivo = ingreso esperado ponderado por `probabilidad_bp` − ciclado. `optimizar` es el caso S=1 (equivalencia testeada). Test foto de ADR-004: sin retiro de red, el plan del caso medio carga PV que el escenario pesimista no tiene (inejecutable); el estocástico retiene.
- **`SimuladorEjecucion` (dominio, puro) + `backtest_politica` (§6.3):** por día, forecast as-seen → plan estocástico → **ejecución contra lo real** (repair conservador auditable, `acciones_reparadas`) → esperado vs realizado vs foresight (+`captura_vs_foresight_bp`); el estado de la batería se arrastra entre días. CLI `acopia-datos backtest-politica`.
- **`ReoptimizarIntradia` (§6.2) + `deteccion_desvio` (dominio):** gatillo por desvío de generación acumulada (bp); recalcula el resto del día desde el estado real sin re-versionar la política (ADR-008). Demo: día que se nubla → el plan obsoleto pierde ingreso; reoptimizar lo recupera con 0 reparaciones. Desvíos sintéticos (límite honesto §6.2: la telemetría plant-level no es pública).
- **Ventana de entrenamiento régimen-local** (`backtest_rodante(..., ventana_entrenamiento)` + flag CLI): salda la deuda de Fase 2.

**Resultados sobre datos reales (CMg S.GREGORIO 2025 + PV TMY):**
- **Backtest de política** (5 días, naive, planta solo-PV+BESS): 1 escenario → captura 93.3% del foresight con 12 reparaciones; **5 escenarios → 100.4% con 6** — la robustez de ADR-004 reduce a la mitad los planes inejecutables. (Captura >100% legítima: el foresight es por-día sin valor terminal; la política arrastra energía entre días.)
- **Deuda de Fase 2 saldada — anual (7 folds, ventana 720 obs = 30 días):**

  | Modelo | gen RMSE | CMg RMSE | CMg MAPE |
  |---|---|---|---|
  | naive | **36.2** | 26220 | 39.1% |
  | SARIMAX | 41.3 | 28165 | 39.2% |
  | LSTM | 46.5 | **20274** | 40.0% |

  El LSTM entrenado régimen-local **recupera la ventaja en CMg** (−23% RMSE vs naive; con historial completo perdía con 38.9k). La hipótesis del cierre de Fase 2 (régimen-dependencia, no defecto del modelo) queda **confirmada empíricamente**. SARIMAX anual ahora es viable en segundos (no bate al naive). Nota honesta: en MAPE de CMg los tres empatan (~39-40%) — la ganancia del LSTM es en magnitud absoluta del error, que es lo que pesa para el arbitraje; en generación el naive sigue ganando (la serie TMY es muy regular).

**Verificación (todo en verde):** ruff OK · mypy --strict 76 files 0 issues · import-linter 2 KEPT · pytest **163 passed** (estocástico +7, simulador/política +9, intradía/desvío +12, ventana +3).

**Vista de halcón (qué quedó débil):**
- La **ventana de 720 obs no fue barrida sistemáticamente**: se eligió porque replica la config que ganó en enero. Un sweep de ventana/hiperparámetros y una regla de selección por régimen (hidrología/estación) quedan pendientes.
- El backtest de política corre con **naive** (rápido); falta la corrida con LSTM-ventana como forecaster de la política (costo: ~25 s/día).
- La telemetría es **sintética** (§6.2); el gatillo de desvío mira solo generación, no CMg ni estado de la batería.
- Escenarios del estocástico vienen del bootstrap del naive; con escenarios del LSTM la cobertura de incertidumbre sería más fiel.
- Números de política sobre planta 1 kW TMY y 5 días: direccionales.

**Deuda generada (→ Fase 4):** sweep de ventana/hiperparámetros + selección por régimen; backtest de política con LSTM; escenarios del forecaster avanzado en el estocástico; gatillo de desvío multi-señal; persistencia de pesos del LSTM; integrar `RastroForecast` a la persistencia.
**Sign-off:** ✅ 2026-07-02 — entregable del SAD completo; el hallazgo honesto de Fase 2 quedó explicado y revertido con evidencia.

## Fase 2 — Forecaster + escenarios — cerrada — 2026-07-02

> Entregable del SAD §13: "Seq2Seq-LSTM + escenarios probabilísticos; baseline SARIMAX; snapshot" — **completo**. Cerrada con validación sobre datos chilenos reales (enero y año 2025) y snapshot as-seen (ADR-007).

**Qué se entregó (cierre — backtest anual + endurecimiento, 2026-07-02):**
- **Backtest anual** sobre `datos/planta_2025.csv` (8754 h reales de CMg S.GREGORIO 2025 + generación TMY), 7 folds × 24 h, vía `acopia-datos backtest`:

  | Modelo (anual) | gen RMSE | gen MAPE | CMg RMSE | CMg MAPE |
  |---|---|---|---|---|
  | naive | **36.2** | **12.9%** | **26.2k** | **39.1%** |
  | LSTM (config CLI fija) | 62.4 | 51.2% | 38.9k | 46.1% |

- **Hallazgo honesto (el resultado importante de la fase):** el LSTM que ganaba en enero (−36% CMg RMSE vs naive) **pierde contra el naive en el test anual** con los mismos hiperparámetros del CLI (ventana 48, hidden 32, 250 épocas). Es el riesgo que ADR-002 anticipó: el CMg es **régimen-dependiente** y una config fija que sirve para 1 mes de historia queda subentrenada/mal calibrada para 12 meses. Conclusión operativa: **el forecaster necesita evaluación por régimen y tuning por volumen de datos** — trabajo natural de la Fase 3 ("Robustez + backtest"). SARIMAX anual no se corrió: con estacionalidad 24 sobre ~8000 puntos en ventana expansiva es impráctico (queda como deuda).
- **+20 casos borde** (endurecimiento pre-cierre): forecasters con serie degenerada (gen=0, todo constante), CMg negativo admisible, horizonte 1, largo mínimo del LSTM; ingesta (negativos, columna ambigua, series vacías); huella de 1 observación; backtest folds=1. Destaparon y corrigieron un footgun real: el XLSX ancho sin fecha configurada devolvía 0 filas en silencio (ahora error claro).

**Qué se entregó (snapshot as-seen del forecast — ADR-007, 2026-07-01):**
- `RastroForecast` (dominio): procedencia reconstruible de un pronóstico (forecaster, horizonte, n_escenarios, semilla, n_observaciones, **huella SHA-256 de la historia**, escenarios). `domain/services/huella.py` (stdlib).
- `application/pronosticar.py`: `pronosticar_con_rastro` (forecast + snapshot atómicos) y `reproduce_el_rastro` (auditoría de reproducibilidad bit a bit). Complementa `RastroDespacho` (plan) de Fase 1.
- Año 2025 completo de S.GREGORIO (3 XLSX concatenados vía `--cmg` multi-archivo) → `datos/planta_2025.csv` (8754 h; faltan ~6 h del año, prob. DST → desfase ≤6 h en la cola con `--recortar`, 0.07%).

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

**Verificación (todo en verde, al cierre):** ruff OK · mypy --strict 67 files 0 issues · import-linter 2 KEPT · pytest **132 passed** (LSTM +7, XLSX +6, formato ancho/CSV +6, backtest +4, snapshot/huella +7, multi-cmg +1, bordes +20, resto acumulado de Fase 1).
- Tests del LSTM: forma/cantidad, **determinismo** (misma semilla → mismos escenarios), generación no negativa, historia insuficiente, escenario-0-sin-ruido, **learnability** (reproduce una señal periódica, RMSE < 5 sobre pico de 90) y **comparación**: bate al estacional-naïve en RMSE sobre datos con tendencia.
- Comparación 3-vías (set sintético período-4 + tendencia, RMSE gen / CMg): naive `8.00 / 2000` · SARIMAX `33.3 / 14283` · **LSTM `1.12 / 420`**.

**Vista de halcón (qué quedó débil):**
- **El resultado del LSTM es régimen/config-dependiente:** gana con claridad en enero (−36% CMg RMSE) y pierde contra el naive en el test anual con hiperparámetros fijos. La cifra del paper (~34%) **no está validada**; lo que hay es evidencia mixta y el aprendizaje de que el tuning debe escalar con el volumen de historia. No se maquilló: ambas cifras quedan en esta auditoría.
- **Generación TMY, no telemetría real de planta:** la serie PV es un año meteorológico típico (2004–2016) apareada por posición con CMg 2025. Suficiente para el pipeline y el forecaster; insuficiente para afirmar ingresos reales.
- **SARIMAX no tiene cifra anual:** estacionalidad-24 sobre ~8000 puntos en ventana expansiva es impráctico (minutos por fit × folds). Falta submuestreo o fit incremental.
- **Entrenamiento por llamada** (LSTM y SARIMAX): costoso a escala; falta modo entrenar-una-vez / persistir pesos.
- **Escenarios por ruido gaussiano** sobre el punto, no muestreo del espacio latente (MC dropout / ensembles) — suficiente para el MVP.
- 8754 vs 8760 h en el año alineado (≤6 h de desfase en la cola con `--recortar`).

**Deuda generada (→ Fase 3 "Robustez + backtest"):** re-evaluación del LSTM por régimen + tuning por volumen de datos (el hallazgo anual); SARIMAX anual (submuestra/fit incremental); persistencia de pesos; escenarios por muestreo latente; telemetría real de planta (o planta modelo sintética documentada, §7 del SAD); integrar `RastroForecast` a la persistencia junto al `RastroDespacho`.
**Sign-off:** ✅ 2026-07-02 — entregable del SAD completo, validado sobre datos reales chilenos, con evidencia mixta del LSTM documentada sin maquillaje.

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
