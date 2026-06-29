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
- **Cubierto por:** pendiente.

### CMg cero o negativo al mediodía
- **Escenario:** sobreoferta solar y congestión llevan el CMg a 0 o negativo en horas centrales.
- **Comportamiento esperado:** cargar agresivamente (energía "gratis" o pagada por absorber), respetando C-rate y throughput; descargar en la punta de la tarde.
- **Cubierto por:** pendiente.

### Batería al límite (SoC en mínimo o máximo)
- **Escenario:** la batería llega a SoC_min o SoC_max antes de fin de horizonte.
- **Comportamiento esperado:** restricciones duras respetadas; el optimizador no genera acciones infactibles; el plan reporta el binding constraint.
- **Cubierto por:** pendiente (property-test de factibilidad).

### Throughput de garantía agotándose
- **Escenario:** el ciclado acumulado se acerca al límite de energía total en vida útil.
- **Comportamiento esperado:** el motor penaliza/limita ciclos extra; no "gana" arbitraje destruyendo la garantía.
- **Cubierto por:** pendiente.

### Desvío fuerte del forecast intradía
- **Escenario:** generación real << forecast a media jornada.
- **Comportamiento esperado:** `ReoptimizarIntradia` recalcula el resto del día con el estado real; el plan original queda en el rastro.
- **Cubierto por:** pendiente (planta modelo sintética).
