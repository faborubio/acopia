# CASES.md — Casos borde del dominio · Acopia

> Casos límite que el motor debe manejar correctamente. Cada caso describe el escenario, el comportamiento esperado y dónde se cubre (test). Se actualiza al descubrir/cubrir un caso.

## Plantilla

```text
### <nombre del caso>
- **Escenario:** ...
- **Comportamiento esperado:** ...
- **Cubierto por:** <test / pendiente>
```

---

### Día sin sol (generación PV ≈ 0)
- **Escenario:** nublado total o falla; el forecast de generación es cercano a cero.
- **Comportamiento esperado:** el plan no asume carga inexistente; la batería solo arbitra con su energía almacenada; sin violar SoC mínimo.
- **Cubierto por:** ✅ `tests/application/test_planificar_despacho.py` (el escenario de arbitraje usa generación = 0 y arbitra solo con la batería).

### CMg cero o negativo al mediodía
- **Escenario:** sobreoferta solar y congestión llevan el CMg a 0 o negativo en horas centrales.
- **Comportamiento esperado:** cargar agresivamente (energía "gratis" o pagada por absorber), respetando throughput; descargar en la punta de la tarde.
- **Cubierto por:** ✅ `tests/application/test_planificar_despacho.py::test_cmg_negativo_al_mediodia_carga_y_gana` (carga con CMg −50.000, descarga a 300.000; ingreso doble: remuneración por absorber + arbitraje).

### Batería al límite (SoC en mínimo o máximo)
- **Escenario:** la batería llega a SoC_min o SoC_max antes de fin de horizonte.
- **Comportamiento esperado:** restricciones duras respetadas; el optimizador no genera acciones infactibles; el plan reporta el binding constraint.
- **Cubierto por:** ✅ `tests/domain/test_modelo_bateria.py` (ejemplos de carga sobre el máximo / descarga bajo el mínimo infactibles + property-test de factibilidad). El arbitraje de Fase 1 carga hasta SoC_max sin violarlo.

### Throughput de garantía agotándose
- **Escenario:** el ciclado acumulado se acerca al límite de energía total en vida útil.
- **Comportamiento esperado:** el motor penaliza/limita ciclos extra; no "gana" arbitraje destruyendo la garantía.
- **Cubierto por:** ✅ `tests/domain/test_modelo_bateria.py::test_throughput_garantia_agotado_es_infactible`. El optimizador LP también incluye la restricción de throughput. **Pendiente: test del optimizador con garantía casi agotada.**

### Precio plano → efecto fin de horizonte (descubierto en Fase 1, resuelto)
- **Escenario:** CMg constante en todo el horizonte; sin diferencial que arbitrar.
- **Comportamiento esperado:** nunca conviene cargar; y si se valoriza la energía final, **no se liquida** la batería solo porque el horizonte termina.
- **Cubierto por:** ✅ `test_precios_planos_nunca_cargan` (invariante "no cargar") + ✅ `test_valor_energia_final_evita_liquidacion` (con `precio_energia_final` la batería retiene en vez de liquidar). El valor terminal es opcional en `PoliticaDespacho`.

### Resolución sub-horaria (15 min)
- **Escenario:** horizonte con intervalos de 15 min (no divisores limpios de la hora).
- **Comportamiento esperado:** la cuantización de energía (Wh enteros) se mantiene determinista y el plan sigue siendo factible.
- **Cubierto por:** ✅ `tests/application/test_planificar_despacho.py::test_resolucion_sub_horaria_factible_y_determinista`.

### Throughput de garantía agotado (cero)
- **Escenario:** la garantía de ciclado ya está consumida (presupuesto 0).
- **Comportamiento esperado:** la batería no cicla nada; el plan es todo RETENER.
- **Cubierto por:** ✅ `tests/application/test_planificar_despacho.py::test_throughput_cero_no_cicla`.

### Eficiencia bajo el break-even
- **Escenario:** round-trip bajo (p. ej. 49 %) y spread de CMg insuficiente para cubrir la pérdida.
- **Comportamiento esperado:** no conviene arbitrar; el motor no carga (no destruye valor por ciclar).
- **Cubierto por:** ✅ `tests/application/test_planificar_despacho.py::test_eficiencia_bajo_break_even_no_arbitra`.

### SoC sin banda operativa (soc_min == soc_max)
- **Escenario:** batería configurada sin banda útil (mín = máx).
- **Comportamiento esperado:** no hay margen para mover energía; el plan es todo RETENER, sin acciones infactibles.
- **Cubierto por:** ✅ `tests/application/test_planificar_despacho.py::test_soc_sin_banda_operativa_solo_retiene`.

### Desvío fuerte del forecast intradía
- **Escenario:** generación real << forecast a media jornada (el día planificado soleado se nubla).
- **Comportamiento esperado:** `ReoptimizarIntradia` recalcula el resto del día desde el estado real de la batería; el plan original queda en el rastro; la política no se re-versiona (ADR-008).
- **Cubierto por:** ✅ `tests/application/test_reoptimizar_intradia.py` (`test_el_desvio_de_la_manana_gatilla_la_reoptimizacion`, `test_reoptimizar_recupera_ingreso_frente_al_plan_obsoleto`, `test_conserva_id_y_version_de_la_politica`) + gatillo en `tests/domain/test_deteccion_desvio.py`. Telemetría sintética (límite honesto del SAD §6.2).

---

## Casos de datos reales (Fases 2–4)

> Descubiertos al ingerir datos chilenos reales (CMg S.GREGORIO 2025 del Coordinador + generación TMY del Explorador Solar) y al co-optimizar SSCC. Regla del método: el caso se documenta **antes** de calibrar heurística/config.

### Coma decimal chilena en TODO dato numérico
- **Escenario:** el Coordinador y el Explorador Solar entregan `"57,79415"` (coma decimal) e incluso miles con punto (`"1.234,56"`).
- **Comportamiento esperado:** `parsear_decimal` tolera ambos formatos (también negativos); lo usan el gateway CSV, los lectores de serie y la extracción de CMg.
- **Cubierto por:** ✅ `test_parsear_decimal_tolera_coma_chilena`, `test_parsear_decimal_negativos` (`tests/infrastructure/test_preparacion.py`), `test_lee_coma_decimal_chilena` (`tests/infrastructure/test_gateway_csv.py`).

### Formato ANCHO del XLSX de CMg del Coordinador
- **Escenario:** columnas `Fecha | Día | Hora | Barra | <NOMBRE_BARRA>`: timestamp partido en `Fecha` (celda **combinada** por día → openpyxl devuelve `None` fuera de la fila ancla) + `Hora` (0..23); la columna de CMg se titula con el mnemónico de la barra (`S.GREGORIO____013`) y `Barra` va vacía.
- **Comportamiento esperado:** forward-fill de la fecha combinada + `--col-hora-cmg`; **matching tolerante** de columna (`--col-cmg "S.GREGORIO"` calza con `S.GREGORIO____013`, y dos barras con el mismo prefijo dan error claro, no una elección silenciosa). Si la columna de fecha no tiene valores, **falla con mensaje claro** (antes devolvía 0 filas en silencio — footgun real).
- **Cubierto por:** ✅ `test_leer_cmg_formato_ancho_coordinador`, `test_cli_alinear_cmg_ancho_del_coordinador`, `test_indice_columna_ambiguo_falla`, `test_leer_serie_xlsx_ancho_sin_fecha_falla` (`tests/infrastructure/test_preparacion.py`).

### CMg = 0 sostenido a mediodía (sobreoferta solar real)
- **Escenario:** en enero 2025, S.GREGORIO registró **240 h con CMg = 0** — no es un dato corrupto, es la duck curve chilena (el diferencial que Acopia arbitra).
- **Comportamiento esperado:** el pipeline y los forecasters admiten CMg 0 sin tratarlo como faltante; las métricas no dividen por cero (MAPE omite reales nulos); el despacho carga en esas horas.
- **Cubierto por:** ✅ `test_mape_omite_reales_nulos` (`tests/domain/test_metricas_forecast.py`) + backtests reales sobre `datos/planta.csv` (la demo MCP siembra exactamente ese perfil).

### CMg negativo también en el forecast
- **Escenario:** el CMg puede ser negativo (curtailment extremo); el forecaster no debe recortarlo a 0 como hace con la generación PV.
- **Comportamiento esperado:** los tres forecasters emiten CMg negativo si la historia lo sugiere; solo la generación se recorta a ≥ 0.
- **Cubierto por:** ✅ `test_cmg_negativo_es_admisible` (parametrizado sobre los 3 forecasters, `tests/infrastructure/test_forecasters_borde.py`).

### Series degeneradas (std = 0) en el LSTM
- **Escenario:** generación siempre 0 (falla larga, invierno extremo) o serie constante — la estandarización dividiría por σ = 0 → NaN.
- **Comportamiento esperado:** estandarización con `+EPS`; el forecaster no produce NaN ni generación negativa.
- **Cubierto por:** ✅ `test_generacion_siempre_cero_no_rompe`, `test_serie_constante_no_rompe` (`tests/infrastructure/test_forecasters_borde.py`).

### Año típico (TMY) y CMg real no comparten calendario
- **Escenario:** el Explorador Solar entrega un año meteorológico **típico** (2004–2016); el CMg es de 2025. Un join por timestamp da vacío.
- **Comportamiento esperado:** alineación **por posición** (hora a hora) con el timestamp del CMg, opt-in (`--por-posicion`); largos distintos exigen `--recortar` explícito (no se recorta en silencio).
- **Cubierto por:** ✅ `test_alinear_por_posicion_usa_ts_del_cmg`, `test_alinear_por_posicion_exige_mismo_largo`, `test_cli_alinear_recortar_al_largo_menor`, `test_cli_alinear_por_posicion` (`tests/infrastructure/test_preparacion.py`).

### El año real trae 8754 h, no 8760 (probable DST)
- **Escenario:** el CMg 2025 concatenado suma 8754 h (faltan ~6); con `--por-posicion --recortar` la cola del año puede quedar desfasada ≤ 6 h contra el TMY.
- **Comportamiento esperado:** aceptado y documentado (0.07% del año); no se interpola ni se rellena en silencio.
- **Cubierto por:** ✅ documentado aquí y en `MEMORY.md` (2026-07-01); decisión consciente, sin heurística oculta.

### Régimen-dependencia del CMg (el hallazgo estrella de F2–F3)
- **Escenario:** el LSTM que ganaba con 1 mes de historia (−36% CMg RMSE vs naive en enero) **pierde contra el naive en el backtest anual** con los mismos hiperparámetros (38.9k vs 26.2k). El CMg cambia de régimen (hidrología, gas, congestión) y una config fija no lo sigue.
- **Comportamiento esperado:** entrenamiento **régimen-local** — `--ventana-entrenamiento 720` (30 días) entrena con las últimas N obs; el LSTM recupera la ventaja anual (CMg RMSE **20.3k vs 26.2k naive, −23%**). Es la evidencia empírica del riesgo que ADR-002 anticipó (enmienda 2026-07-09 en el SAD).
- **Cubierto por:** ✅ `test_ventana_de_entrenamiento_recorta_la_historia`, `test_ventana_expansiva_por_defecto` (`tests/application/test_backtest.py`) + cifras en `docs/AUDIT.md` (cierres de F2 y F3). La ventana fue barrida el 2026-07-12 (ver caso siguiente).

### La curva de sensibilidad de la ventana régimen-local (sweep de AUD-005)
- **Escenario:** la ventana 720 replicaba la config ganadora de enero sin barrido — ¿es un mínimo real o un accidente? Sweep con el protocolo del anual (7 folds × 24 h, `planta_2025.csv`, LSTM 48/32/250, semilla 0), variando solo `--ventana-entrenamiento`.
- **Comportamiento observado (CMg RMSE):** 168→**32.7k** (pierde vs naive: muy poca historia para aprender) · 336→**20.4k** · 720→**20.3k** (mínimo) · 1440→**21.7k** · 2160→**21.5k** · 4320→**36.3k** (pierde: el cambio de régimen diluye el patrón reciente) · referencias: naive 26.2k, historial completo 38.9k. La curva tiene forma de U: **meseta amplia 336–2160** donde cualquier ventana bate al naive (−17% a −23%) y colapso en ambos extremos.
- **Lectura:** la elección de 720 **no es frágil** (meseta ancha), y la régimen-dependencia del CMg queda descrita por una curva completa, no por dos puntos. En gen RMSE el naive sigue ganando en todas las ventanas (consistente con F2–F3).
- **Cubierto por:** ✅ evidencia en enmienda ADR-002.2 (SAD) y AUD-005 (registro); reproducible con `acopia-datos backtest --planta datos/planta_2025.csv --folds 7 --modelos lstm --ventana-entrenamiento N`.

### SSCC emergente: comprar energía de la red para vender disponibilidad
- **Escenario:** la banda de reserva paga más que el spot; el LP decide **retirar de la red** para tener energía que respalde la banda (arbitraje entre productos, no entre horas).
- **Comportamiento esperado:** es correcto y deseado — la co-optimización de ADR-010 lo permite mientras respete nodo, SoC y throughput. Se fija como invariante, no se "corrige".
- **Cubierto por:** ✅ `test_comprar_energia_para_vender_disponibilidad` (`tests/infrastructure/test_cooptimizacion_sscc.py`).

### Deriva de floors de eficiencia: la cuantización anulaba la hora más cara
- **Escenario:** la eficiencia entera (floor) acumula una deriva de Wh a lo largo del día: tras N cargas, la batería entera tiene menos energía que la trayectoria continua del LP. La descarga planificada de la **última hora (la más cara)** queda infactible por unos pocos Wh.
- **Comportamiento esperado:** recortar la acción al máximo factible (SoC, potencia, throughput, nodo), no anularla. El repair antiguo (RETENER) perdía el intervalo completo: ~15% del ingreso en días reales de enero. Descubierto porque el **experimento DRL de ADR-005 "superaba" al LP** — le ganaba al repair, no al óptimo.
- **Cubierto por:** ✅ `test_la_deriva_de_floors_recorta_la_descarga_en_vez_de_anularla` (`tests/infrastructure/test_cuantizacion_lp.py`) + `OptimizadorLP._accion_recortada` (paga AUD-003).

### El XLSX "Reducciones ERV" del Coordinador (bloques por día + typos oficiales)
- **Escenario (Observatorio, ADR-012):** una hoja `Resumen-DiarioHorario-<Tecnología>` por tecnología; cada día es un **bloque** — fila con la fecha (fórmula hacia `Resumen-Mensual`, se lee el valor cacheado con `data_only`), header `Central/Hora` con las horas 1..24, una fila por central en **MWh** y una fila `Total` que cierra. El archivo real de mayo 2026 trajo además: **`"-"` (guión contable)** por "sin reducción" en la hoja eólica, y un **typo en el header** (un `|` donde iba el `2`, hoja solar, día 10).
- **Comportamiento esperado:** `leer_reducciones_erv` aplana a registros `(tecnologia, central, fecha, 24 MWh)`; celdas vacías y guiones cuentan como 0.0; filas `Total` se omiten (los totales se recalculan, nunca se confía en fórmulas del libro); el typo del header se **repara por posición** solo si las horas encontradas son ≥20 y contiguas (menos que eso = header trunco → error, no desfase silencioso); vertimiento negativo = error con hoja/fila/hora.
- **Validación real:** el archivo de mayo 2026 completo (31 días, 9238 registros) cuadra **exacto** con su propio `Resumen-Mensual`: solar 137.548 · eólica 57.830 · hidro pasada 1.708 · embalse 0 GWh.
- **Cubierto por:** ✅ `tests/infrastructure/test_reducciones_erv.py` (8 tests: aplanado, 4 tecnologías, celda vacía, guión, typo del header, header trunco, negativo, archivo ajeno).

### SSCC emergente: sin retiro de red, absorber exige estar inyectando
- **Escenario:** planta con `retiro_max = 0`: para absorber la activación a bajar (cargar +R) sin retirar de la red, el punto de conexión exige **estar inyectando ≥ R**.
- **Comportamiento esperado:** el LP reparte óptimamente entre vender e inyectar de respaldo (en el test, d = R = 5 kW). Moraleja de testing: fijar invariantes físicos, no expectativas ingenuas — el LP ganó dos veces.
- **Cubierto por:** ✅ `test_sin_retiro_la_banda_exige_estar_inyectando` (`tests/infrastructure/test_cooptimizacion_sscc.py`).

---

## Casos identificados, aún no abordados (visión de halcón)

> Anotados para no perderlos; se convierten en test/feature en su fase.

### Curtailment por límite de transmisión
- **Escenario:** el nodo no puede absorber toda la inyección (congestión); hay un techo de potencia de inyección.
- **Comportamiento esperado:** preferir cargar la batería antes que verter; respetar el límite de inyección; verter solo el excedente que no cabe ni en la red ni en la batería.
- **Cubierto por:** ✅ entidad `Planta` (punto de conexión) + el optimizador modela `vertido` con la restricción de inyección. Tests `test_limite_de_inyeccion_carga_para_evitar_vertimiento` (vierte 20 kWh tras cargar 30 e inyectar 30) y `test_punto_de_conexion_holgado_no_vierte`. *(Pendiente: límite de retiro re-clamp en cuantización; curtailment voluntario a CMg negativo.)*

### Estado inicial fuera de la banda operativa
- **Escenario:** el SoC inicial llega por encima de soc_max o por debajo de soc_min (telemetría real, recalibración).
- **Comportamiento esperado:** no romper el LP con un error críptico; señalar el problema con claridad.
- **Cubierto por:** ✅ `test_estado_inicial_fuera_de_banda_es_error` (el optimizador valida y lanza `ValueError`; el REST lo traduce a 422). *(Pendiente: permitir converger a la banda en vez de rechazar.)*

### CMg negativo con batería sin capacidad de absorber
- **Escenario:** CMg negativo y batería llena (no puede cargar más).
- **Comportamiento esperado:** verter el PV en vez de inyectarlo a precio negativo (curtailment voluntario).
- **Cubierto por:** ✅ `test_curtailment_voluntario_a_cmg_negativo` (vierte 50 kWh; ingreso 0 en vez de pagar por inyectar).

### Horizonte de un solo intervalo
- **Escenario:** `horizonte_intervalos == 1`.
- **Comportamiento esperado:** plan de una acción coherente, sin errores de borde.
- **Cubierto por:** ✅ `test_horizonte_de_un_intervalo`.
