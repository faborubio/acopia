"""Casos borde de los forecasters, compartidos por las 3 implementaciones (ADR-002).

Bordes que importan en datos chilenos reales: series degeneradas (planta nocturna,
CMg plano), CMg negativo (curtailment), horizonte 1 e historia en el largo mínimo.
"""

from __future__ import annotations

import numpy as np
import pytest

from acopia.domain.entities.observacion import Observacion
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.infrastructure.forecasting.forecaster_estacional import ForecasterEstacionalNaive
from acopia.infrastructure.forecasting.forecaster_lstm import ForecasterSeq2SeqLSTM
from acopia.infrastructure.forecasting.forecaster_sarimax import ForecasterSARIMAX


def _historia(pares: list[tuple[int, int]], repeticiones: int) -> tuple[Observacion, ...]:
    return tuple(
        Observacion(Potencia(g), Precio(c)) for _ in range(repeticiones) for g, c in pares
    )


def _todos() -> list[object]:
    return [
        ForecasterEstacionalNaive(estacionalidad=4),
        ForecasterSARIMAX(estacionalidad=4),
        ForecasterSeq2SeqLSTM(ventana=4, hidden=8, epocas=20),
    ]


@pytest.mark.parametrize("forecaster", _todos())
def test_generacion_siempre_cero_no_rompe(forecaster: object) -> None:
    # Planta nocturna / sensor apagado: gen=0 en toda la historia (std=0).
    historia = _historia([(0, 50_000), (0, 70_000), (0, 60_000), (0, 55_000)], 4)
    escenarios = forecaster.pronosticar(historia, horizonte=4, n_escenarios=2, semilla=0)  # type: ignore[attr-defined]
    valores = [p.generacion.w for e in escenarios for p in e.puntos]
    assert all(v >= 0 for v in valores)
    assert not any(np.isnan(v) for v in valores)


@pytest.mark.parametrize("forecaster", _todos())
def test_serie_constante_no_rompe(forecaster: object) -> None:
    # gen y CMg planos (std=0 en ambas features): no debe dar NaN ni negativos.
    historia = _historia([(50, 60_000)], 16)
    escenarios = forecaster.pronosticar(historia, horizonte=4, n_escenarios=3, semilla=1)  # type: ignore[attr-defined]
    for e in escenarios:
        for p in e.puntos:
            assert p.generacion.w >= 0


@pytest.mark.parametrize("forecaster", _todos())
def test_cmg_negativo_es_admisible(forecaster: object) -> None:
    # Precios negativos son reales (curtailment): el pronóstico puede ser negativo.
    historia = _historia([(10, -5_000), (20, 50_000), (30, -3_000), (15, 40_000)], 4)
    escenarios = forecaster.pronosticar(historia, horizonte=4, n_escenarios=1, semilla=0)  # type: ignore[attr-defined]
    assert all(p.generacion.w >= 0 for e in escenarios for p in e.puntos)  # gen nunca negativa


def test_lstm_historia_en_largo_minimo() -> None:
    # ventana + horizonte = 4 + 4 = 8 observaciones: una única ventana de entrenamiento.
    historia = _historia([(10, 50_000), (20, 40_000)], 4)  # 8 obs
    escenario = ForecasterSeq2SeqLSTM(ventana=4, hidden=8, epocas=10).pronosticar(
        historia, horizonte=4, n_escenarios=1, semilla=0
    )[0]
    assert len(escenario.puntos) == 4


@pytest.mark.parametrize("forecaster", _todos())
def test_horizonte_de_un_intervalo(forecaster: object) -> None:
    historia = _historia([(10, 50_000), (20, 40_000), (30, 60_000), (15, 45_000)], 4)
    escenario = forecaster.pronosticar(historia, horizonte=1, n_escenarios=1, semilla=0)[0]  # type: ignore[attr-defined]
    assert len(escenario.puntos) == 1
