# MEMORY.md — Bitácora · Acopia

> Decisiones, hallazgos no obvios y estado actual. Se actualiza al final de cada sesión y ante cada decisión relevante. Lo más reciente arriba.

## Estado actual

- **Fase:** 2 **CERRADA** (sign-off 2026-07-02 en `docs/AUDIT.md`). Fases 0, 1 y 2 completas.
- **Fase 3 CERRADA** (sign-off 2026-07-02 en `docs/AUDIT.md`). Fases 0–3 completas. **Hallazgo estrella:** el LSTM entrenado régimen-local (ventana 720 obs) recupera la ventaja en el anual — CMg RMSE **20.3k vs 26.2k naive (−23%)**; con historial completo perdía (38.9k). La régimen-dependencia de Fase 2 quedó explicada y revertida.
- **Fase 4 CERRADA (sign-off 2026-07-09 en `docs/AUDIT.md`). El alcance de portafolio del SAD §13 (fases 1–4) está COMPLETO.** Rebanada 3 (modo DRL, ADR-005) entregada: PPO tras `PuertoOptimizador`, `comparar_modos` (app + MCP + CLI), experimento medido: **DRL captura 96.1% del LP** en días reales de enero. **Hallazgo estrella: el experimento destapó que el repair a RETENER de la cuantización del LP anulaba la hora más cara del día** (deriva de floors de eficiencia, ~15% del ingreso) → `_accion_recortada` recorta al factible y el LP subió +8.9% (paga AUD-003). Bitácora abajo.
- **Alineación con el Método: EJECUTADA (2026-07-09, bitácora abajo).** TROUBLESHOOTING/CASES poblados, SAD v1.1.0 (ADR-010 + enmiendas ADR-002.1/007.1 + historial), registro `AUD-NNN`, README al día, DoD en CLAUDE.md, pip-audit.
- **Observatorio v1 (ADR-012): CONSTRUIDO Y DESPLEGADO** (rebanadas 1 y 2, 2026-07-15, bitácora abajo): parser Reducciones ERV + agregados + página de vertimiento + snapshot de la demo + Action mensual + Pages. **Sitio: https://faborubio.github.io/acopia/**
- **PRÓXIMA ACCIÓN (candidatas, en orden de valor):** (1) **difusión** — enlazar el Observatorio en el README de acopia y en el perfil de GitHub; primer post de LinkedIn con la página de vertimiento (la cuña de posicionamiento del ADR); (2) **rebanada 3 del Observatorio**: duck curve del CMg + valorización del desplazamiento a la punta (exige fuente de CMg automatizable; la descarga manual del XLS no sirve para el Action — evaluar API v4 online para un día/mes, o el mapeo central→zona vía info de instalaciones del Coordinador, AUD-026); (3) prospección Maule con el Observatorio como artefacto de venta (bitácora 2026-07-14); (4) deuda AUD-NNN. La postulación a Junior Data Engineer (Grupo Mariposa) sigue en curso; la oferta de pulir el dashboard para el CV queda abierta. ✅ Key SIP rotada (2026-07-09). ✅ Carpeta renombrada `ergia`→`acopia` (2026-07-11). ✅ Sweep de ventana + dashboard demo (2026-07-12).
- **Ojo (local):** al cierre de la sesión del 2026-07-12 quedó un uvicorn de la demo corriendo en el puerto 8123 (PID 23792 de esa sesión; si estorba: `Stop-Process`, o ya murió con el reinicio). Para levantarlo de nuevo: `uvicorn acopia.interfaces.rest.app:app` → `http://127.0.0.1:8000/demo`.
- **Servidor MCP activo:** `.mcp.json` local (git-ignored) apunta a `python -m acopia.interfaces.mcp.servidor` (demo stdio con plan sembrado). Herramientas: `consultar_despacho`, `explicar_despacho`, `simular`.
- **Deuda conocida de la capa MCP:** el rastro no persiste la batería/resolución (el servidor las recibe por inyección); persistir la política completa junto al rastro es deuda para la fase de persistencia real (Timescale).
- **Datos disponibles:** `datos/planta.csv` (enero, 744 h) y `datos/planta_2025.csv` (año, 8754 h). Comandos reproducibles: `acopia-datos backtest --ventana-entrenamiento 720` y `acopia-datos backtest-politica` (ver bitácora).
- **Datos disponibles:** `datos/planta.csv` (enero, 744 h) y `datos/planta_2025.csv` (año completo, 8754 h) — CMg real S.GREGORIO 2025 + generación TMY Antofagasta. Git-ignored; se regeneran con `acopia-datos alinear` (comando exacto en bitácora 2026-07-01).
- **Datos reales (cómo obtenerlos) — ver bitácora 2026-06-29 "API real del Coordinador":** la vía práctica es **descarga manual del XLS** de CMg (una barra, rango de fechas) + exportar generación del Explorador Solar, y unir con `acopia-datos alinear --por-posicion`. La API existe pero NO conviene para bulk (ver abajo).

## Bitácora

### 2026-07-15b — Observatorio rebanada 2: la página de vertimiento + sitio completo + Pages
- **`render_vertimiento`** (`interfaces/observatorio/sitio.py`): página estática autocontenida — KPIs (2.463 GWh ene–may 2026, 73% solar, hora pico 17:00, 300 centrales), barras mensuales apiladas, **perfil horario** (la foto de la tesis: todo el vertimiento entre las 9 y las 18h) y top 10 centrales (100% PFV) + tabla mensual de respaldo. SVG renderizado **server-side** (testeable sin navegador), tooltip JS mínimo (textContent, teclado incluido), claro/oscuro por `prefers-color-scheme`.
- **Método dataviz aplicado completo:** paleta categórica = slots 1–4 de la referencia en orden de apilado (solar amarillo, eólica azul, hidro pasada verde, embalse magenta), **validada con el script en ambos modos** (PASS todas las puertas; el WARN de contraste del amarillo/magenta en claro se releva con etiquetas directas + tabla). Barras ≤24px, tope redondeado 4px solo en el extremo, gap de 2px de superficie entre segmentos, leyenda siempre, etiquetas selectivas (todas las columnas mensuales; solo el pico en el perfil), hit targets de banda completa. Renderizado y **revisado a ojo en ambos temas** (Edge headless).
- **`acopia-datos observatorio --reducciones *.xlsx --salida dir`**: sitio completo — `index.html` + `demo.html` (snapshot del dashboard ADR-011; `--sin-demo` lo omite y quita el enlace). 76 KB totales para 45.586 registros.
- **`.github/workflows/observatorio.yml`**: el plan de descargar en CI murió al primer despliegue — **Cloudflare desafía a las IPs de datacenter** ("Just a moment...", HTTP 403; incidente en TROUBLESHOOTING). Pivote = **enmienda ADR-012.1** (SAD → v1.3.1): caché versionado `datos/erv/*.xlsx` (excepción al git-ignore de `datos/`), el Action construye desde el repo y se redespliega al pushear el caché; refresco mensual **local** con el snippet del encabezado del workflow. Deuda AUD-027 (peso del caché). **Pages habilitado vía API (`build_type=workflow`)**: https://faborubio.github.io/acopia/
- Gotchas de la sesión: PowerShell here-string (`@'...'@`) NO es sintaxis de Git Bash (commit con título basura → amend + force-with-lease); el guión largo tipográfico en tests se escribe `–` (RUF001); `dict` es invariante en mypy → `Mapping` para parámetros; `10 ** int` es `Any` para mypy → `10.0 **`.
- Verde: ruff OK · mypy 102 OK · import-linter KEPT · pytest **224 passed** (+8).

### 2026-07-15 — Observatorio rebanada 1: parser de Reducciones ERV + agregados (validado contra el archivo real)
- **`leer_reducciones_erv`** (`infrastructure/ingesta/reducciones_erv.py`): aplana las hojas `Resumen-DiarioHorario-*` a registros `(tecnologia, central, fecha, 24 MWh)`. Bloques por día (fecha = fórmula, se lee el valor cacheado con `data_only`), header `Central/Hora` 1..24, fila `Total` omitida (todo se recalcula, nunca se confía en fórmulas del libro).
- **El archivo real mordió dos veces (a CASES):** (1) `"-"` (guión contable) por "sin reducción" en la hoja eólica → cuenta como 0.0; (2) **typo en el header oficial** — un `|` donde iba el `2` (hoja solar, día 10) → reparación por posición solo si hay ≥20 horas contiguas (menos = header trunco → error, no desfase silencioso). Moraleja repetida: el smoke contra el archivo real encuentra lo que la fixture no imagina.
- **Validación:** mayo 2026 completo (31 días, 9238 registros) cuadra **exacto** con su `Resumen-Mensual`: solar 137.548 · eólica 57.830 · hidro pasada 1.708 · embalse 0 GWh.
- **Agregados** (`interfaces/observatorio/agregados.py`, puros): `total_mensual_gwh`, `perfil_horario_mwh` (la foto de la tesis: el vertimiento solar se concentra a mediodía, cuando el CMg colapsa), `top_centrales` (orden determinista).
- **Hallazgo de alcance:** el XLSX **no trae zona** — el "agregado por zona" del plan necesita mapeo central→zona externo (¿info de instalaciones del Coordinador?); v1 nacional + por central, coherente con AUD-026.
- Gotcha de toolchain: `ws.cell(row, col, value=None)` de openpyxl es **no-op** (solo asigna si value no es None) — mordió en un test.
- Verde: ruff OK · mypy 100 archivos OK · import-linter KEPT · pytest **216 passed** (+12).

### 2026-07-14b — ADR-012: el Observatorio es la cara pública (absorbe la publicación de la demo)
- **El usuario propuso el enfoque "Acopia Observatorio":** antes de vender nada, ser el sitio que muestra lo que nadie muestra bien — vertimiento por zona, duck curve del CMg, plata botada, pipeline BESS. Cuña de posicionamiento, no negocio: costo fines de semana, riesgo cero. Patrón ya ejecutado 2 veces por el autor (panel de GitHub, faro).
- **Spike de evidencia (esta sesión, regla "evidencia, no intuición"):** el Coordinador publica **"Reducciones ERV"** — XLSX mensual, curtailment **por central × hora × día**, hojas por tecnología (`Resumen-DiarioHorario-Solar/Eólico/HP/HE` + acumulados anuales), rezago ~2 meses (mayo-26 publicado en julio). Verificado descargando y abriendo el de mayo 2026 (1.9 MB, headers en fila 7, matriz Central/Hora 1–24, celdas combinadas — el estilo hostil que la ingesta ya doma). URL patrón: `coordinador.cl/wp-content/uploads/YYYY/MM/Reducciones-de-Energia-Eolica-Solar-Hidro-en-el-SEN_<Mes>-YY-PE-PFV_Publicar.xlsx`; el sitio devuelve 403 sin User-Agent de navegador. Muestra en scratchpad de la sesión; página índice: `/operacion/documentos/reducciones-de-generacion-renovable/reducciones-erv-2026/`. Complemento: API datos abiertos CNE (energiaabierta.cl, requiere key).
- **Decisiones del autor (2 preguntas):** el Observatorio vive **dentro de acopia** (reusa `leer_serie_xlsx`/`parsear_decimal`; rechazado repo nuevo) y **absorbe el pendiente #1**: un solo sitio público con el Observatorio + snapshot estático del dashboard demo (rechazada la app viva en free tier). Todo en **ADR-012** (SAD → v1.3.0).
- **Regla de honestidad fijada en el ADR:** valorizar el vertimiento "a spot" es tramposo (se vierte justo cuando CMg ≈ 0 — daría casi cero); se publica la valorización del **desplazamiento a la punta**, que es la tesis de Acopia contada con datos públicos. Rezago de la fuente declarado en el sitio.
- **Deuda nueva: AUD-026** — sin mapeo central→barra; v1 valoriza con barra representativa por zona, limitación declarada.
- (Aparte, fuera de acopia: README del perfil de GitHub actualizado — acopia a Beta con topic `fase-beta`, faro agregado, telar fuera — y portafolio migrado a faborubio.dev, incl. redirección de faborubio.github.io.)

### 2026-07-14 — Exploración de salida real (demo pública, hardware, cliente) + docs al MANIFIESTO v1.3.0
- **Sesión de exploración, sin código.** Tres frentes conversados con el usuario, todos quedan como pendientes accionables en `## Próxima sesión` de `CLAUDE.md`:
  1. **Publicar la demo:** la app corre local sin dependencias externas (verificado en vivo: `/salud` ok, `/demo` HTTP 200 ~28 KB). Dos rutas: snapshot estático en GitHub Pages (recomendada — el HTML es autocontenido, conserva interactividad, cero superficie de ataque) vs app viva en free tier (exige Dockerfile, que no existe, y proteger `POST /planes`: optimiza un LP por request, vector de abuso sin auth). Decisión del usuario pendiente; al decidir, ADR.
  2. **Piloto hardware casero:** Acopia hoy no habla con hardware (puertos existentes: forecaster/optimizador/historia/repos; `deteccion_desvio` y `reoptimizar_intradia` quedaron listos para telemetría real a propósito). Prueba 1 = lazo cerrado de 24 h con inversor híbrido + LiFePO4 (~USD 800–1.500, ecosistema Victron por Modbus/MQTT abiertos; PV no necesario). **Paso 0 gratis:** desarrollar el adaptador contra Venus OS en modo demo (corre en Raspberry Pi) antes de comprar. Honestidad: en casa no se ve CMg (tarifa plana/netbilling) — la prueba valida ingeniería, no ingreso.
  3. **Cliente real cerca de Curepto (búsqueda web 2026-07-14):** el calce directo del producto son los **PMGD** — Solek opera *Pencahue Este* (3 MWp, ~40 km) y oEnergy opera *El Tiuque* (San Javier, **primer PMGD+BESS de Chile**, Huawei Luna2000 2 MWh); *Sol de Caone* (Itahue/Sphera, ~17 km al este de Hualañé, 390–420 MW) está en evaluación ambiental. Las **viñas** (Viñedos Puertas en Sagrada Familia ~35–40 km; Bouchon en Mingre) son piloto behind-the-meter: exige adaptar la señal (tarifa horaria en vez de CMg) y sumar el cargo por potencia (por máximo leído, estructura nueva en el LP) — trabajo real, no un rename.
- **MANIFIESTO avanzó a v1.3.0 (2026-07-13) sin que este repo lo supiera** (la alineación del 07-09 fue contra v1.1.0). Se aplicaron las dos enmiendas nuevas: **v1.2.0** → README reescrito como cara pública profesional (lead con el problema del vertimiento, tabla "Resultados medidos", sección "Ingeniería a la vista"); **v1.3.0** → `CLAUDE.md` ahora cierra con `## Próxima sesión` (pendientes en orden de valor, ⏸ marca lo que espera decisión del autor). Además `CLAUDE.md` ahora advierte verificar la versión del MANIFIESTO al reentrar.
- Sin ADR nuevo: no se tomó ninguna decisión de arquitectura (todo quedó como decisión abierta).

### 2026-07-12 — Dashboard demo (ADR-011) + sweep de ventana (AUD-005 parcialmente pagada)
- **Contexto:** el usuario postula a un puesto de Junior Data Engineer (Grupo Mariposa, remoto; piden pipelines + ML + **dashboards/reportes**) y pidió UI/UX de demo para el portafolio. Decisión con el usuario: FastAPI + HTML autocontenido (no Streamlit), historias "plan del día" + "pipeline de datos".
- **`GET /demo` (ADR-011):** dashboard HTML/SVG/JS vanilla autocontenido servido por la app REST — KPIs y tabla de 24 h server-side (legible sin JS), 3 gráficos apilados (CMg con anotaciones, PV + carga/descarga divergente, SoC) con crosshair/tooltip sincronizado (hover + teclado) que muestra el **motivo del `ExplicadorDespacho`** por hora; modo claro/oscuro (paleta validada del skill dataviz); sección pipeline (XLSX Coordinador → alinear → backtest) con la tabla del backtest anual. **`interfaces/demo_dia.py`** extrae el día sembrado que compartían… nadie: ahora MCP y dashboard cuentan el mismo día desde una sola fuente. Captura en `docs/img/dashboard_demo.png` (README). Verificado renderizado real (uvicorn + Edge headless, ambos temas).
- **Sweep AUD-005 (ventana):** 7 folds anuales, solo variando `--ventana-entrenamiento`. CMg RMSE: 168→32.7k · 336→20.4k · **720→20.3k (mínimo)** · 1440→21.7k · 2160→21.5k · 4320→36.3k (naive 26.2k; expansiva 38.9k). **Curva en U con meseta 336–2160**: la 720 se confirma y la elección no es frágil. Enmienda **ADR-002.2** + caso en CASES + AUD-005 → "parcialmente pagada" (vivo: hiperparámetros y regla por régimen). SAD → **v1.2.0**.
- **Fix colateral:** el header del SAD decía "reemplaza a Acopia, colisión con Acopia.ai" (daño de un replace masivo antiguo) → restaurado "Ergia/Ergia.ai"; estado del header al día (fases 0–4 cerradas).
- ruff: excepción por archivo (`E501`, `RUF001`) solo para el template del dashboard en `pyproject.toml`.
- Verde: ruff OK · mypy OK · import-linter 2 KEPT · pytest **204 passed** (+6 del dashboard).

### 2026-07-09 — CIERRE de Fase 4: modo DRL (ADR-005) + el hallazgo del repair
- **`OptimizadorDRL`** (PPO, extra `acopia[drl]`: stable-baselines3 2.9 + gymnasium 1.3, instalaron limpio; disco ya no es problema: 14 GB libres tras limpieza del usuario) tras el mismo `PuertoOptimizador`: entrena por llamada (patrón LSTM, AUD-009), rollout determinista, acciones validadas contra `ModeloBateria`, ingreso por `FuncionObjetivo` — comparable 1:1 con el LP. Rechaza SSCC (AUD-023).
- **`EntornoDespacho`** (gymnasium): acción [-1,1] recortada a lo factible (el agente no puede violar la física); vertido = recurso analítico óptimo por signo del CMg (misma regla que el LP); recompensa escalada; muestreo de escenarios por `probabilidad_bp`. gamma=1.0 (horizonte finito).
- **`comparar_modos`**: aplicación (re-optimiza el rastro as-seen con ambos modos, `replace(politica, modo=...)` operacional sin re-versionar), herramienta MCP (4ª del servidor; error claro sin el extra) y CLI `acopia-datos comparar-modos` (forecast perfecto: mide al optimizador, no al forecaster).
- **Experimento (enero real, 3 días, 30k timesteps/día, semilla 0): primera corrida DRL 104.6% del LP — imposible contra un óptimo → auditoría del baseline.** Diagnóstico: la deriva de floors de la eficiencia entera deja la descarga de la **hora 23 (la más cara)** infactible por ~1 Wh; el repair a RETENER la anulaba entera (días 1-2: −51/−35 mills, ~15%). Fix: **`OptimizadorLP._accion_recortada`** — recorta al máximo factible (SoC/potencia/throughput/nodo, retiro en el peor escenario), paga **AUD-003**; regresión en `test_cuantizacion_lp.py`; caso en CASES. **Resultado final: LP 946 mills (antes 869, +8.9%), DRL 909 → captura 96.1% (97.7/95.1/94.9 por día). El LP gana siempre: ADR-005 medido y confirmado.**
- Moraleja (a CASES/AUDIT): **si el experimento supera al óptimo, audita al óptimo.** El valor del DRL fue estresar al baseline.
- Deuda nueva: AUD-023 (DRL sin SSCC, aceptada), AUD-024 (valorización duplicada LP/DRL), AUD-025 (obs del DRL sin throughput/banda). AUD-009 extendida al PPO.
- Verde: ruff OK · mypy(91) OK · import-linter 2 KEPT (+gymnasium prohibido en domain) · pytest **198 passed** (+15) · pip-audit limpio.
- **Sign-off Fase 4:** ✅ en `docs/AUDIT.md`. **Portafolio (fases 1–4) completo**; Fase 5 solo con tracción.

### 2026-07-09 — Alineación con el Método EJECUTADA (plan de 5 pasos completo)
- **1. `docs/TROUBLESHOOTING.md`** dejó de estar vacío: 4 incidentes reales (disco 0 GB corrompe cachés; API v4 del Coordinador inviable para bulk; stdout corrompía el JSON-RPC del MCP stdio; SARIMAX anual impráctico → `--ventana-entrenamiento`).
- **2. `docs/CASES.md`** ganó la sección "Casos de datos reales (Fases 2–4)": coma decimal, formato ancho del Coordinador, CMg=0 sostenido, CMg negativo en forecast, series std=0, TMY sin calendario común, 8754 vs 8760 h, **régimen-dependencia del CMg** y los 2 emergentes SSCC. "Desvío intradía" pasó de ⏳ a ✅.
- **3. SAD → v1.1.0** (con tabla de historial de revisiones, antes no existía): **ADR-010** (SSCC = un producto: banda simétrica por disponibilidad, precio en la política; settlement de activación fuera del MVP), **enmienda ADR-002.1** (entrenamiento régimen-local, evidencia anual 20.3k vs 26.2k), **enmienda ADR-007.1** (`RastroForecast` + huella SHA-256). Header actualizado (versión/estado; ya no dice "0.1 draft propuesto").
- **4. `docs/AUDIT.md`** ganó el **registro `AUD-NNN`**: AUD-001…015 deuda viva (con plan/estado) + AUD-016…022 deuda pagada (con dónde se pagó). El log por fase se mantiene intacto. Numeración cruzada desde el SAD (AUD-005 = sweep ventana, AUD-010 = persistir RastroForecast).
- **5. README** al día (fases 0–3 cerradas + F4 con el MCP de titular, comandos MCP/backtest, extras opcionales) + **DoD de 7 pasos** del MANIFIESTO escrito en `CLAUDE.md` (incluida la pregunta 1a "¿hay una idea mejor?") + **pip-audit** en `[dev]` de pyproject. pip-audit encontró y se pagó al tiro: setuptools 70.2.0 vulnerable (PYSEC-2025-49) → actualizado a `>=78.1.1,<82` (torch exige <82). Nota: pip-audit no puede auditar `torch 2.12.1+cpu` (rueda del índice de PyTorch, no PyPI) — limitación conocida, aceptable.
- Verde completo: ruff OK · mypy(85) OK · import-linter 2 KEPT · pytest **183 passed** · pip-audit sin vulnerabilidades.
- **Sigue pendiente del usuario (seguridad, reiterado):** rotar la key SIP del Coordinador expuesta en junio.

### 2026-07-09 — Revisión contra el Método (MANIFIESTO v1.1.0) — PLAN APROBADO, ejecutar en sesión nueva
- Se auditó Acopia contra `MANIFIESTO.md` (doctrina personal del usuario, en `\\wsl.localhost\Ubuntu-24.04\home\faborubio\Workspace\metodo\`). **Cumple en espíritu** (SAD que manda, fases + sign-off, deuda visible, honestidad, CLAUDE.md reentrable, proporcionalidad) pero hay gaps concretos. **El usuario aprobó aplicar TODO el paquete.**
- **Plan de 5 pasos (en orden):**
  1. **`docs/TROUBLESHOOTING.md` (hoy vacío) ← migrar incidentes reales:** disco C: a 0 GB corrompió cachés mypy/import-linter (F1, fix: pip cache purge); API v4 Coordinador inviable para bulk (429 + ignora filtro de barra → descarga manual XLS); stdout corrompía JSON-RPC del MCP stdio (fix: log a stderr, commit 7477a1b); SARIMAX anual impráctico en ventana expansiva (fix: `--ventana-entrenamiento`).
  2. **`docs/CASES.md` (congelado en F1) ← casos de datos reales F2–F4:** coma decimal chilena; formato ancho Coordinador (Fecha combinada + columna titulada por barra + matching tolerante); CMg=0 en 240 h de enero (sobreoferta solar); TMY año típico sin calendario común (alinear --por-posicion --recortar); 8754 vs 8760 h (DST); **régimen-dependencia del CMg** (LSTM pierde con historial completo, gana con ventana 720 — el hallazgo estrella); series degeneradas std=0 (+EPS en LSTM); CMg negativo admisible en forecast; emergentes SSCC: "comprar energía para vender disponibilidad" y "sin retiro, absorber exige estar inyectando (R≤d)". Además: marcar "Desvío intradía" como ✅ cubierto (era ⏳).
  3. **SAD ← decisiones sin ADR (regla 1 del método):** **ADR-010** producto SSCC único (banda simétrica, disponibilidad, precio constante en política; settlement de activación fuera del MVP); **enmienda a ADR-002** ventana régimen-local (evidencia: anual 7 folds, LSTM 20.3k vs naive 26.2k CMg RMSE); **nota/enmienda a ADR-007** (RastroForecast + huella SHA-256). + **Tabla de historial de revisiones** al SAD (hoy no tiene).
  4. **`docs/AUDIT.md` ← registro `AUD-NNN`** (regla 2): numerar la deuda viva con estado (pendiente/pagada + dónde se pagó), manteniendo el log por fase. Deuda viva conocida: re-clamp retiro en cuantización, converger a banda SoC, sweep ventana/hiperparámetros, backtest política con LSTM, escenarios del LSTM en estocástico, gatillo desvío multi-señal, persistencia de pesos, RastroForecast→persistencia, política completa junto al rastro, telemetría real.
  5. **README al día** (dice "Fase 1 cerrada"; van 4 fases y el MCP es el titular) + **DoD de 7 pasos del manifiesto escrito en `CLAUDE.md`** (en especial 1a "¿hay una idea mejor?") + **`pip-audit` al toolchain dev** (pata de seguridad del verde; bandit se descartó por proporcionalidad).
- **Pendiente del usuario (seguridad, reiterado):** rotar la key SIP del Coordinador expuesta en junio.

### 2026-07-02 — Fase 4 rebanada 2 (capa MCP read-only + explicabilidad, §5)
- **`ExplicadorDespacho`** (dominio, puro): explica cada intervalo desde el plan + rastro as-seen — acción, CMg y su **percentil dentro del horizonte** (bp), trayectoria de SoC reconstruida con `ModeloBateria`, vertido, banda SSCC y un `motivo` determinista ("Carga: el CMg es de los más baratos…"; CMg ≤ 0 → "inyectar pagaría por generar"; RETENER con banda → "mantiene headroom para la banda SSCC").
- **`simular_escenario`** (aplicación): parte del escenario as-seen del rastro (ADR-007), aplica `cmg_por_intervalo` y/o `factor_generacion_bp` y re-optimiza **sin persistir**; devuelve comparación de ingresos (delta).
- **Servidor MCP** (`interfaces/mcp/servidor.py`, FastMCP 3): herramientas del SAD §5 — `consultar_despacho`, `explicar_despacho(plan_id, intervalo?)`, `simular(cmg_por_intervalo, factor_generacion_pct)`. **Read-only + simulación** (decisión de seguridad del SAD). `comparar_modos` queda para la rebanada DRL. `crear_servidor(...)` por inyección; `python -m acopia.interfaces.mcp.servidor` = demo stdio con día chileno típico sembrado (duck curve, CMg 0 a mediodía).
- Tests end-to-end con el **cliente in-memory de FastMCP** (asyncio.run, sin plugins): lista de herramientas, consulta, "por qué cargó" y simulación de CMg 0 en la punta (delta < 0, sin tocar el plan original). `fastmcp>=3` como extra `[mcp]`.
- Verde: ruff/mypy(85)/import-linter OK · pytest **183 passed** (+13).

### 2026-07-02 — Fase 4 rebanada 1 (co-optimización arbitraje + SSCC, §3.0)
- **`ReservaFrecuencia`** (dominio, `producto_sscc.py`): banda simétrica ±R remunerada por **disponibilidad** (precio constante en la política; el settlement de activación queda fuera del MVP). `PoliticaDespacho.reserva: ReservaFrecuencia | None` (None = arbitraje puro). `PlanDespacho.reserva_w: tuple[int,...] = ()` (retrocompatible). `FuncionObjetivo.ingreso_reserva`.
- **LP co-optimizado (una sola función objetivo):** restricciones de banda = headroom de potencia (±R sobre el setpoint), de **energía** (sostener la activación el intervalo completo: `energia − R/ef_d ≥ e_min`, `energia + ef_c·R ≤ e_max`) y de **inyección/retiro en todos los escenarios** (`inyectado ± R` dentro del nodo). Cuantización con clamp conservador (`_reserva_factible`: nunca agranda la banda del LP).
- **El LP me ganó dos veces (comportamientos emergentes correctos, ahora fijados por test):** (1) **compra energía de la red para vender disponibilidad** cuando la banda paga más que el spot (arbitraje entre productos); (2) con `retiro=0`, absorber la activación a bajar **exige estar inyectando ≥ R** → reparte óptimamente entre vender y respaldar banda (d=R=5k en el test). Moraleja de testing: fijar invariantes, no expectativas ingenuas.
- Tests (+7): sin SSCC no hay banda; banda máxima con valor terminal neutralizando liquidación; los dos emergentes; la banda compite con el arbitraje (ingreso total sube, `R + setpoint ≤ potencia`); ingreso = bruto + disponibilidad; determinismo con SSCC.
- Verde: ruff/mypy(78)/import-linter OK · pytest **170 passed**.

### 2026-07-02 — CIERRE de Fase 3 (ventana régimen-local + deuda saldada + sign-off)
- **`ventana_entrenamiento`** en `backtest_rodante` + flag CLI `--ventana-entrenamiento`: entrena con las últimas N obs (régimen-local) en vez de todo el histórico. Una sola pieza saldó ambas deudas de Fase 2.
- **Anual 7 folds, ventana 720 (30 días):** naive gen 36.2 / CMg 26.2k · SARIMAX 41.3 / 28.2k (ahora corre en segundos; no bate al naive) · **LSTM 46.5 / CMg 20.3k → −23% vs naive**. Con historial completo el LSTM daba 38.9k: el problema era el régimen, no el modelo. OJO: en CMg MAPE empatan (~39-40%); la ganancia es en RMSE (magnitud, lo que pesa para arbitraje). En generación el naive sigue ganando.
- La ventana 720 NO fue barrida (replica la config ganadora de enero); el sweep sistemático es deuda de Fase 4.
- Verde: ruff/mypy(76)/import-linter OK · pytest **163 passed** (+3).
- **Sign-off Fase 3:** ✅ en `docs/AUDIT.md`. Deuda → Fase 4: sweep ventana/hiperparámetros, backtest de política con LSTM, escenarios del LSTM en el estocástico, gatillo multi-señal, persistencia de pesos, RastroForecast a persistencia.

### 2026-07-02 — Fase 3 rebanada 3 (ReoptimizarIntradia + detección de desvío, §6.2)
- **`deteccion_desvio`** (dominio, puro): `desvio_generacion_bp(previsto, observado)` compara la generación acumulada asumida por el plan vs la telemetría, en puntos base; `hay_desvio(..., umbral_bp)` es el gatillo. Borde: generación inesperada de noche (previsto 0) = desvío total (10000 bp); noche tranquila = 0.
- **`reoptimizar_intradia`** (aplicación): recalcula los intervalos restantes **desde el estado real de la batería** con el forecast actualizado. La política NO se re-versiona (ADR-008): `dataclasses.replace` recorta `horizonte_intervalos` operacionalmente; el plan restante conserva id/versión. Valida `0 < intervalo_actual < horizonte` y el largo de los escenarios.
- **Test demo de la fase:** día planificado soleado se nubla a la hora 1 (la carga se repara a RETENER → la batería queda con la mitad de lo previsto). Seguir el plan obsoleto por la tarde → la descarga planificada es infactible y se pierde ingreso; **reoptimizar desde el estado real recupera ingreso** (assert estricto) con 0 reparaciones. Telemetría = desvíos sintéticos (límite honesto de §6.2: la telemetría plant-level no es pública).
- Verde: ruff/mypy(76)/import-linter OK · pytest **160 passed** (+12).

### 2026-07-02 — Fase 3 rebanada 2 (BacktestPolitica + SimuladorEjecucion, §6.3)
- **`SimuladorEjecucion`** (dominio, puro): confronta un plan con el día **real**. Reglas conservadoras auditables: acción infactible para la batería → RETENER; carga que exigiría retirar de la red más allá del límite (el PV real no alcanza) → RETENER; vertido realizado = max(planificado, excedente obligatorio) acotado al PV real. Reporta `acciones_reparadas` (intervalos donde el plan era inejecutable).
- **`backtest_politica`** (aplicación): por fold (día): forecast as-seen → `optimizar_escenarios` → ejecutar contra lo real → `ingreso_esperado` vs `ingreso_realizado` vs `ingreso_foresight` (optimizar el día real = techo) + `captura_vs_foresight_bp`. **El estado de la batería se arrastra entre folds.** Test clave: forecast perfecto ⇒ realizado == esperado == foresight (captura 100%); forecast engañoso ⇒ reparaciones y captura < 100%.
- **CLI `acopia-datos backtest-politica`** (planta modelo parametrizable; default retiro=0 → solo PV+BESS). **Resultado real** (`planta_2025.csv`, 5 folds, naive): 1 escenario → captura **93.3%**, 12 reparadas · 3 escenarios → 87.8%, 12 · **5 escenarios → 100.4%, 6 reparadas**. La historia de ADR-004 en datos reales: más escenarios ⇒ planes que fallan menos en ejecución. OJO: captura >100% es legítima (el foresight es por-día sin valor terminal; la política ejecutada arrastra energía entre días). Números direccionales (planta 1 kW TMY, 5 días, naive).
- Verde: ruff/mypy(72)/import-linter OK · pytest **148 passed** (+9).

### 2026-07-02 — Fase 3 rebanada 1 (optimizador estocástico de dos etapas, ADR-004)
- `PuertoOptimizador` gana **`optimizar_escenarios(planta, estado, escenarios, politica)`**; `OptimizadorLP.optimizar` ahora delega con un solo escenario (equivalencia verificada por test).
- **Formulación de dos etapas:** primera etapa = programa de la batería (carga/descarga/energía, común a todos los escenarios, here-and-now); segunda etapa = **vertido de recurso por escenario**. Restricciones de inyección/retiro del nodo exigidas en *todos* los escenarios → la robustez emerge de la factibilidad conjunta. Objetivo: ingreso esperado ponderado por `probabilidad_bp` (pesos normalizados) − ciclado + valor terminal.
- **Ingreso esperado del plan:** cada escenario se valoriza con *su* vertido de recurso cuantizado (mismas acciones); promedio ponderado en aritmética entera (`suma_ponderada // suma_pesos`). El plan reporta el vertido del **escenario 0** (referencia puntual).
- **Test clave (la foto de ADR-004):** planta sin retiro de red (`retiro_max=0`), PV barato en hora 0 en el caso medio pero **0 en el escenario pesimista** → el plan del caso medio CARGA (inejecutable si sale nublado); el estocástico RETIENE. Robustez ante el colapso/incertidumbre del PV demostrada.
- Verde: ruff/mypy(68)/import-linter OK · pytest **139 passed** (+7).

### 2026-07-02 — CIERRE de Fase 2 (backtest anual + sign-off)
- **Backtest anual** (7 folds × 24 h sobre `planta_2025.csv`, 8754 h): naive gen RMSE **36.2** / CMg RMSE **26.2k** / CMg MAPE **39.1%** · LSTM (config CLI fija) gen 62.4 / CMg 38.9k / MAPE 46.1%. Corrió ~35 min el LSTM (1.2 s/época sobre ~8700 obs).
- **Hallazgo clave (documentado sin maquillaje en AUDIT):** el LSTM que ganaba en enero (−36% CMg vs naive) **pierde contra el naive en el anual** con los mismos hiperparámetros (ventana 48, hidden 32, 250 épocas). Confirmación empírica del riesgo de ADR-002 (CMg régimen-dependiente): el tuning debe escalar con el volumen de historia. Va como deuda prioritaria a Fase 3.
- SARIMAX anual no corrió (impráctico, ver bitácora anterior); queda como deuda (submuestra o fit incremental).
- **Sign-off Fase 2:** ✅ en `docs/AUDIT.md` — entregable del SAD §13 completo (LSTM + escenarios + baseline SARIMAX + snapshot ADR-007), validado sobre datos reales.

### 2026-07-01 — Endurecimiento con casos borde (pre-cierre Fase 2)
- **+20 tests de borde** (132 passed total). Forecasters (los 3, parametrizados): generación siempre 0 / serie constante (std=0, la estandarización del LSTM usa `+EPS` → sin NaN ni negativos), **CMg negativo admisible** (curtailment), horizonte 1, LSTM en largo mínimo exacto (ventana+horizonte). Ingesta: `parsear_decimal` negativos, ambigüedad de columna (`_indice_columna` con dos barras que empiezan igual → error claro), `alinear_por_posicion([],[])`. Snapshot: huella de 1 observación (64 hex). Backtest: `folds=1`.
- **Footgun real corregido:** `leer_serie_xlsx` en formato ancho, si veía **horas pero ninguna fecha** (columna de fecha mal configurada), devolvía **0 filas en silencio**. Ahora **falla con mensaje claro** ("La columna de fecha '…' no tiene valores; ¿es la correcta para --col-ts-cmg?").
- Verde: ruff/mypy(67)/import-linter OK · pytest **132 passed**.
- **Backtest anual descartado por costo:** SARIMAX estacionalidad-24 sobre ~8000 puntos en ventana expansiva es impráctico (minutos por fit × folds × 2 series). Para la cifra anual: usar naive+LSTM, o SARIMAX solo con submuestra. El backtest de enero (5 días) sigue siendo la referencia.

### 2026-07-01 — Snapshot as-seen del forecast (ADR-007) + año 2025 completo
- **ADR-007 (forecast):** `RastroForecast` (dominio) captura la **procedencia reconstruible** de un pronóstico: forecaster (id/versión), horizonte, n_escenarios, semilla, n_observaciones, **huella SHA-256 de la historia as-seen** (`domain/services/huella.py`, stdlib) y los escenarios producidos. `application/pronosticar.py`: `pronosticar_con_rastro` (forecast + rastro atómicos) y `reproduce_el_rastro` (un auditor regenera bit a bit con la misma historia+semilla → verifica determinismo). Complementa al `RastroDespacho` de Fase 1 (que ya guardaba política/estado/escenarios del plan).
- **Año completo:** `--cmg` ahora acepta **varios archivos** (los concatena y ordena por timestamp). S.GREGORIO 2025 = enero (`21593abb`) + febrero (`99728291`, multi-barra, se toma S.GREGORIO por matching tolerante) + mar-dic (`d5da8a4a`) → **`datos/planta_2025.csv`, 8754 h (364 días)** vs generación TMY. Nota: 8754 vs 8760 (6 h faltan, prob. DST) → `--por-posicion --recortar` puede introducir un desfase ≤6 h en la cola del año (aceptable, 0.07%).
- Verde: ruff/mypy(66)/import-linter OK · pytest **112 passed** (+8: huella +3, snapshot +4, multi-cmg +1).
- **Pendiente de esta sesión:** backtest sobre el año completo (corriendo en bg, LSTM lento) para actualizar las cifras del backtest de 5 días de enero.

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
- ~~Renombrar la carpeta local `ergia` → `acopia`~~ **RESUELTA (2026-07-11):** el usuario ejecutó `renombrar_a_acopia.ps1` con éxito. Verificación post-rename en sesión: `.mcp.json` apunta a la ruta nueva, `.venv` reconstruido funcional, ruff OK · mypy 65 files 0 issues · import-linter 2 KEPT · pytest **198 passed** · módulo MCP importa. Script borrado.
- ~~Rotar la key SIP del Coordinador (expuesta en un chat en junio)~~ **RESUELTA: key regenerada por el usuario el 2026-07-09.** (Ya se había verificado que la key vieja no estaba en repo/git/historiales de shell; la nueva no se pega en ningún chat ni archivo — el CLI la recibe por `--url`.)
- Confirmar dominios **acopia.ai / acopia.cl** con WHOIS en vivo (búsqueda web no mostró registro, pero no es prueba). `acopia.com` probablemente tomado (hipotecaria usa myacopia.com). **DIFERIDA a propósito (2026-07-11): el usuario decidió que aún falta mucho para eso; retomar cuando el proyecto tenga tracción/salida pública.**
- **INAPI:** registrar marca en clase software/energía (Niza 9/42/39-40). Homónimos en otros sectores no bloquean: Acopia Networks (IT, muerta tras compra de F5 en 2007), Acopia LLC (hipotecaria US), Acopia Ventures (VC), ACOPIA (ONG). Cero colisión en energía/energytech/Chile. **DIFERIDA a propósito (2026-07-11): sin registro por ahora; retomar junto con los dominios cuando surja la necesidad.**
- ~~¿Modelar SSCC con un solo producto (reserva de frecuencia) en fase 4 o varios desde el inicio?~~ **Resuelta: un solo producto (ADR-010, 2026-07-09).**
- Fuente concreta de datos: API del Coordinador Eléctrico Nacional para CMg + Explorador Solar para irradiancia.
