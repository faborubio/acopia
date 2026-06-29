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
