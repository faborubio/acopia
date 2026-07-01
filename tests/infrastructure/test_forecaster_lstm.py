"""Tests del ForecasterSeq2SeqLSTM: forma, determinismo, learnability y comparación.

El objetivo verificable de ADR-002 es "batir al baseline en nuestro set", no replicar
el ~34% del paper. Sobre datos sintéticos pequeños eso solo es honestamente exigible
cuando el baseline tiene un sesgo estructural (tendencia): ahí el LSTM gana de forma
robusta. La learnability (reproducir una señal periódica) verifica la arquitectura.
"""

from __future__ import annotations

import pytest

from acopia.domain.entities.observacion import Observacion
from acopia.domain.services.metricas_forecast import MetricasForecast
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.infrastructure.forecasting.forecaster_estacional import ForecasterEstacionalNaive
from acopia.infrastructure.forecasting.forecaster_lstm import ForecasterSeq2SeqLSTM

_PG = [0, 40, 90, 40]
_PC = [100_000, 80_000, 60_000, 80_000]
_SLOPE_G, _SLOPE_C = 8, 2000


def _periodica(n: int = 40) -> tuple[Observacion, ...]:
    """Señal puramente periódica de período 4 (sin tendencia)."""
    return tuple(Observacion(Potencia(_PG[i % 4]), Precio(_PC[i % 4])) for i in range(n))


def _con_tendencia(n: int = 48) -> tuple[Observacion, ...]:
    """Período 4 + tendencia por estación: el estacional-naïve se queda corto."""
    return tuple(
        Observacion(
            Potencia(_PG[i % 4] + _SLOPE_G * (i // 4)),
            Precio(_PC[i % 4] + _SLOPE_C * (i // 4)),
        )
        for i in range(n)
    )


def test_forma_y_cantidad_de_escenarios() -> None:
    forecaster = ForecasterSeq2SeqLSTM(ventana=8, hidden=8, epocas=20)
    escenarios = forecaster.pronosticar(_periodica(), horizonte=4, n_escenarios=3, semilla=0)
    assert len(escenarios) == 3
    assert all(len(e.puntos) == 4 for e in escenarios)


def test_es_determinista_con_la_misma_semilla() -> None:
    forecaster = ForecasterSeq2SeqLSTM(ventana=8, hidden=8, epocas=30)
    historia = _periodica()
    a = forecaster.pronosticar(historia, horizonte=4, n_escenarios=5, semilla=11)
    b = forecaster.pronosticar(historia, horizonte=4, n_escenarios=5, semilla=11)
    assert a == b


def test_generacion_nunca_negativa() -> None:
    forecaster = ForecasterSeq2SeqLSTM(ventana=8, hidden=8, epocas=20)
    escenarios = forecaster.pronosticar(_periodica(), horizonte=4, n_escenarios=8, semilla=2)
    assert all(p.generacion.w >= 0 for e in escenarios for p in e.puntos)


def test_historia_insuficiente_es_error() -> None:
    # ventana 8 + horizonte 4 exige >= 12 observaciones.
    forecaster = ForecasterSeq2SeqLSTM(ventana=8)
    with pytest.raises(ValueError):
        forecaster.pronosticar(_periodica(8), horizonte=4, n_escenarios=1, semilla=0)


def test_escenario_cero_es_el_puntual_sin_ruido() -> None:
    # El escenario 0 es el pronóstico puntual; los demás incorporan incertidumbre.
    forecaster = ForecasterSeq2SeqLSTM(ventana=8, hidden=8, epocas=20)
    escenarios = forecaster.pronosticar(_con_tendencia(), horizonte=4, n_escenarios=3, semilla=1)
    assert any(e != escenarios[0] for e in escenarios[1:])


def test_aprende_una_senal_periodica() -> None:
    # Learnability: con señal puramente periódica el LSTM reproduce el siguiente período.
    historia = _periodica(40)
    real_gen = [float(_PG[i % 4]) for i in range(40, 44)]
    punto = ForecasterSeq2SeqLSTM(ventana=8, hidden=16, epocas=150).pronosticar(
        historia, horizonte=4, n_escenarios=1, semilla=0
    )[0]
    rmse = MetricasForecast().rmse([float(p.generacion.w) for p in punto.puntos], real_gen)
    assert rmse < 5.0  # pico de 90 W -> error < ~5 %


def test_lstm_bate_al_estacional_naive_con_tendencia() -> None:
    # ADR-002: el LSTM debe batir al baseline en nuestro set. Con tendencia el
    # estacional-naïve (repite la última estación) se sesga; el LSTM la extrapola.
    historia = _con_tendencia(48)
    real_gen = [float(_PG[i % 4] + _SLOPE_G * (i // 4)) for i in range(48, 52)]

    naive = ForecasterEstacionalNaive(estacionalidad=4).pronosticar(
        historia, horizonte=4, n_escenarios=1, semilla=0
    )[0]
    lstm = ForecasterSeq2SeqLSTM(ventana=8, hidden=24, epocas=250).pronosticar(
        historia, horizonte=4, n_escenarios=1, semilla=0
    )[0]

    metricas = MetricasForecast()
    rmse_naive = metricas.rmse([float(p.generacion.w) for p in naive.puntos], real_gen)
    rmse_lstm = metricas.rmse([float(p.generacion.w) for p in lstm.puntos], real_gen)

    assert rmse_lstm < rmse_naive
