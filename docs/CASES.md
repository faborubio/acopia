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

### Precio plano → efecto fin de horizonte (descubierto en Fase 1)
- **Escenario:** CMg constante en todo el horizonte; sin diferencial que arbitrar.
- **Comportamiento esperado:** nunca conviene cargar (comprar para revender al mismo precio menos eficiencia). *Limitación actual:* sin valor de SoC terminal, el modelo puede **liquidar** la batería al final del horizonte (deuda en `AUDIT.md`).
- **Cubierto por:** ✅ `tests/application/test_planificar_despacho.py::test_precios_planos_nunca_cargan` (afirma el invariante "no cargar"; la liquidación queda como deuda).

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
- **Escenario:** generación real << forecast a media jornada.
- **Comportamiento esperado:** `ReoptimizarIntradia` recalcula el resto del día con el estado real; el plan original queda en el rastro.
- **Cubierto por:** ⏳ pendiente — `ReoptimizarIntradia` es Fase 3 (con planta modelo sintética).

---

## Casos identificados, aún no abordados (visión de halcón)

> Anotados para no perderlos; se convierten en test/feature en su fase.

### Curtailment por límite de transmisión
- **Escenario:** el nodo no puede absorber toda la inyección (congestión); hay un techo de potencia de inyección.
- **Comportamiento esperado:** preferir cargar la batería antes que verter; respetar el límite de inyección; verter solo el excedente que no cabe ni en la red ni en la batería.
- **Cubierto por:** ✅ entidad `Planta` (punto de conexión) + el optimizador modela `vertido` con la restricción de inyección. Tests `test_limite_de_inyeccion_carga_para_evitar_vertimiento` (vierte 20 kWh tras cargar 30 e inyectar 30) y `test_punto_de_conexion_holgado_no_vierte`. *(Pendiente: límite de retiro re-clamp en cuantización; curtailment voluntario a CMg negativo.)*

### Estado inicial fuera de la banda operativa
- **Escenario:** el SoC inicial llega por encima de soc_max o por debajo de soc_min (telemetría real, recalibración).
- **Comportamiento esperado:** degradar con elegancia (no romper el LP); permitir converger a la banda.
- **Estado:** ⏳ pendiente — hoy el LP sería infactible; falta manejo explícito.

### Horizonte de un solo intervalo
- **Escenario:** `horizonte_intervalos == 1`.
- **Comportamiento esperado:** plan de una acción coherente, sin errores de borde.
- **Estado:** ⏳ pendiente de test explícito (el dominio lo permite).
