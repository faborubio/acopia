"""Backtest rodante de un forecaster: mide su error out-of-sample sobre la historia.

Orquesta el `PuertoForecaster` (dominio) y `MetricasForecast` (dominio) en una
ventana expansiva: para cada fold entrena con lo previo y pronostica el siguiente
tramo, comparando contra lo real. Sirve para la comparación honesta de ADR-002
(baseline vs SARIMAX vs LSTM) sobre los mismos datos, sin acoplar a ninguna infra.
"""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.entities.observacion import Observacion
from acopia.domain.ports.puerto_forecaster import PuertoForecaster
from acopia.domain.services.metricas_forecast import MetricasForecast


@dataclass(frozen=True, slots=True)
class MetricasSerie:
    """RMSE y MAPE promedio de una serie sobre los folds del backtest."""

    rmse: float
    mape: float


@dataclass(frozen=True, slots=True)
class ResultadoBacktest:
    """Resultado agregado del backtest para un forecaster."""

    folds: int
    horizonte: int
    generacion: MetricasSerie
    cmg: MetricasSerie


def backtest_rodante(
    forecaster: PuertoForecaster,
    historia: tuple[Observacion, ...],
    horizonte: int,
    folds: int,
    semilla: int = 0,
    ventana_entrenamiento: int | None = None,
) -> ResultadoBacktest:
    """Evalúa ``forecaster`` en ``folds`` tramos consecutivos de ``horizonte`` pasos.

    Ventana expansiva por defecto: el fold ``k`` entrena con todo lo anterior al tramo
    y pronostica los ``horizonte`` pasos siguientes. Con ``ventana_entrenamiento`` se
    entrena solo con las últimas N observaciones previas al tramo (**régimen-local**):
    acota el costo de modelos que re-entrenan por llamada (SARIMAX/LSTM) y evita que
    un histórico largo con cambio de régimen (CMg) diluya el patrón reciente.
    Devuelve el RMSE/MAPE promedio por serie.
    """
    if horizonte < 1:
        raise ValueError("El horizonte debe ser >= 1")
    if folds < 1:
        raise ValueError("folds debe ser >= 1")
    if ventana_entrenamiento is not None and ventana_entrenamiento < 1:
        raise ValueError("ventana_entrenamiento debe ser >= 1")
    if len(historia) <= folds * horizonte:
        raise ValueError(
            f"Historia insuficiente ({len(historia)}) para {folds} folds de {horizonte} "
            f"pasos: se requieren más de {folds * horizonte} observaciones"
        )

    metricas = MetricasForecast()
    rmse_gen, mape_gen, rmse_cmg, mape_cmg = [], [], [], []
    for k in range(folds):
        fin = len(historia) - (folds - 1 - k) * horizonte
        entrenamiento = historia[: fin - horizonte]
        if ventana_entrenamiento is not None:
            entrenamiento = entrenamiento[-ventana_entrenamiento:]
        real = historia[fin - horizonte : fin]
        escenario = forecaster.pronosticar(entrenamiento, horizonte, 1, semilla)[0]

        pron_gen = [float(p.generacion.w) for p in escenario.puntos]
        pron_cmg = [float(p.cmg.mills_por_mwh) for p in escenario.puntos]
        real_gen = [float(o.generacion.w) for o in real]
        real_cmg = [float(o.cmg.mills_por_mwh) for o in real]

        rmse_gen.append(metricas.rmse(pron_gen, real_gen))
        mape_gen.append(metricas.mape(pron_gen, real_gen))
        rmse_cmg.append(metricas.rmse(pron_cmg, real_cmg))
        mape_cmg.append(metricas.mape(pron_cmg, real_cmg))

    def promedio(valores: list[float]) -> float:
        return sum(valores) / len(valores)

    return ResultadoBacktest(
        folds=folds,
        horizonte=horizonte,
        generacion=MetricasSerie(promedio(rmse_gen), promedio(mape_gen)),
        cmg=MetricasSerie(promedio(rmse_cmg), promedio(mape_cmg)),
    )
