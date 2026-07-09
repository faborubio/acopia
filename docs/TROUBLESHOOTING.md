# TROUBLESHOOTING.md — Problemas conocidos · Acopia

> Problemas reproducibles y su resolución. Se actualiza al resolver un problema concreto, para que la próxima sesión no lo redescubra.

## Plantilla

```text
### <síntoma>
- **Causa:** ...
- **Resolución:** ...
- **Fecha:** ...
```

---

### mypy / import-linter fallan con errores crípticos de caché

- **Síntoma:** durante la verificación de Fase 1, `mypy --strict` y `lint-imports` empezaron a fallar con errores internos que no correspondían al código.
- **Causa:** el disco C: llegó a **0 GB libres** y las escrituras de caché (`.mypy_cache/`, caché de import-linter) quedaron corruptas/truncadas.
- **Resolución:** liberar espacio (`pip cache purge` recuperó ~132 MB) y borrar los cachés corruptos; las herramientas los regeneran. **Prevención:** vigilar el disco antes de instalar dependencias pesadas (torch, stable-baselines3); al escribir esto quedan ~3.6 GB libres.
- **Fecha:** 2026-06-28 (Fase 1).

### La API SIP v4 del Coordinador es inviable para descargas bulk de CMg

- **Síntoma:** intentar bajar un año de CMg de UNA barra vía `https://sipub.api.coordinador.cl/costo-marginal-real/v4/findByDate` termina en **HTTP 429** (rate limit) y respuestas gigantes.
- **Causa:** el endpoint **ignora el filtro de barra en el servidor** — devuelve TODAS las barras (~150.000 registros/día) y hay que filtrar en cliente, lo que multiplica páginas y dispara el rate limit. Además, el endpoint v2 documentado en el portal (`…/sipub/api/v2/recursos/…`) está obsoleto; el `acopia-datos cmg` escrito contra v2 quedó obsoleto con él.
- **Resolución:** **descarga manual del XLS** de [Costo Marginal Real](https://www.coordinador.cl/mercados/documentos/transferencias-economicas/costo-marginal-real/) (una barra, rango de fechas) + `acopia-datos alinear --por-posicion` (el lector maneja el formato ancho del Coordinador; ver `docs/CASES.md`). La API queda solo para consultas puntuales de pocos días.
- **Fecha:** 2026-06-29 (Fase 2).

### El servidor MCP stdio se cae / el cliente reporta JSON inválido

- **Síntoma:** al conectar un cliente MCP al servidor stdio (`python -m acopia.interfaces.mcp.servidor`), el handshake fallaba o el cliente reportaba mensajes JSON-RPC corruptos.
- **Causa:** la demo sembrada imprimía su log por **stdout**, que en transporte stdio es el **canal JSON-RPC**: cualquier `print` intercalado corrompe el framing del protocolo.
- **Resolución:** todo log/diagnóstico del servidor MCP va a **stderr** (commit `7477a1b`). Regla general: en un proceso stdio-MCP, stdout es sagrado.
- **Fecha:** 2026-07-02 (Fase 4).

### El backtest anual con SARIMAX no termina (minutos por fit × folds)

- **Síntoma:** `acopia-datos backtest` sobre `planta_2025.csv` (~8700 obs) con SARIMAX quedaba impráctico: estacionalidad 24 sobre ~8000 puntos en **ventana expansiva** toma minutos por fit, × folds × 2 series.
- **Causa:** el costo del fit de SARIMAX crece con el largo de la historia; la ventana expansiva re-ajusta con TODO el histórico en cada fold.
- **Resolución:** `--ventana-entrenamiento N` (p. ej. 720 = 30 días): entrena régimen-local con las últimas N observaciones. SARIMAX anual pasó de impráctico a segundos — y de paso el LSTM recuperó su ventaja en CMg (ver `docs/CASES.md`, régimen-dependencia).
- **Fecha:** 2026-07-02 (Fase 3).
