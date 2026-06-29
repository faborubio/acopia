# MEMORY.md — Bitácora · Acopia

> Decisiones, hallazgos no obvios y estado actual. Se actualiza al final de cada sesión y ante cada decisión relevante. Lo más reciente arriba.

## Estado actual

- **Fase:** 0 — Scaffolding **cerrada** (sign-off en `docs/AUDIT.md`).
- **Próxima acción (Fase 1):** definir los Protocols de `ports/` (`PuertoForecaster`, `PuertoOptimizador`, `PuertoDatos`, repositorios) y el primer caso de uso `PlanificarDespacho` con un optimizador determinista que reciba un forecast dado y produzca un plan factible.

## Bitácora

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
- Confirmar dominios **acopia.ai / acopia.cl** con WHOIS en vivo (búsqueda web no mostró registro, pero no es prueba). `acopia.com` probablemente tomado (hipotecaria usa myacopia.com).
- **INAPI:** registrar marca en clase software/energía (Niza 9/42/39-40). Homónimos en otros sectores no bloquean: Acopia Networks (IT, muerta tras compra de F5 en 2007), Acopia LLC (hipotecaria US), Acopia Ventures (VC), ACOPIA (ONG). Cero colisión en energía/energytech/Chile.
- ¿Modelar SSCC con un solo producto (reserva de frecuencia) en fase 4 o varios desde el inicio?
- Fuente concreta de datos: API del Coordinador Eléctrico Nacional para CMg + Explorador Solar para irradiancia.
