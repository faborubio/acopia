"""Tests del ForecasterSARIMAX y su comparación contra el baseline estacional."""

from __future__ import annotations

from acopia.domain.entities.observacion import Observacion
from acopia.domain.services.metricas_forecast import MetricasForecast
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.infrastructure.forecasting.forecaster_estacional import ForecasterEstacionalNaive
from acopia.infrastructure.forecasting.forecaster_sarimax import ForecasterSARIMAX

_PATRON_GEN = [0, 50, 100, 50]
_PATRON_CMG = [100_000, 80_000, 60_000, 80_000]


def _historia_estacional(n: int = 48) -> tuple[Observacion, ...]:
    # patrón diario de 4 pasos con una leve variación determinista (evita matriz singular)
    return tuple(
        Observacion(
            Potencia(_PATRON_GEN[i % 4] + (i % 3)),
            Precio(_PATRON_CMG[i % 4] + 50 * (i % 3)),
        )
        for i in range(n)
    )


def _historia_con_tendencia(n: int = 24) -> tuple[Observacion, ...]:
    return tuple(Observacion(Potencia(1000 + 50 * i), Precio(50_000 + 100 * i)) for i in range(n))


def test_forma_y_cantidad_de_escenarios() -> None:
    forecaster = ForecasterSARIMAX(estacionalidad=4)
    escenarios = forecaster.pronosticar(
        _historia_estacional(), horizonte=4, n_escenarios=3, semilla=0
    )
    assert len(escenarios) == 3
    assert all(len(e.puntos) == 4 for e in escenarios)


def test_es_determinista_con_la_misma_semilla() -> None:
    forecaster = ForecasterSARIMAX(estacionalidad=4)
    historia = _historia_estacional()
    a = forecaster.pronosticar(historia, horizonte=4, n_escenarios=5, semilla=11)
    b = forecaster.pronosticar(historia, horizonte=4, n_escenarios=5, semilla=11)
    assert a == b


def test_generacion_nunca_negativa() -> None:
    forecaster = ForecasterSARIMAX(estacionalidad=4)
    escenarios = forecaster.pronosticar(
        _historia_estacional(), horizonte=4, n_escenarios=8, semilla=2
    )
    assert all(p.generacion.w >= 0 for e in escenarios for p in e.puntos)


def test_sarimax_bate_al_estacional_naive_con_tendencia() -> None:
    # Con tendencia, el estacional-naïve (repite la última estación) se queda corto;
    # SARIMAX con diferenciación extrapola la tendencia y baja el RMSE.
    historia = _historia_con_tendencia(24)
    real_gen = [float(1000 + 50 * i) for i in range(24, 28)]  # continúa la tendencia

    naive = ForecasterEstacionalNaive(estacionalidad=4).pronosticar(
        historia, horizonte=4, n_escenarios=1, semilla=0
    )[0]
    sarimax = ForecasterSARIMAX(
        estacionalidad=4, orden=(1, 1, 1), orden_estacional=(0, 0, 0, 0)
    ).pronosticar(historia, horizonte=4, n_escenarios=1, semilla=0)[0]

    metricas = MetricasForecast()
    rmse_naive = metricas.rmse([float(p.generacion.w) for p in naive.puntos], real_gen)
    rmse_sarimax = metricas.rmse([float(p.generacion.w) for p in sarimax.puntos], real_gen)

    assert rmse_sarimax < rmse_naive
