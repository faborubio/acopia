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
