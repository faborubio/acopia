"""Tests del backtest rodante (servicio de aplicación, sin infra)."""

from __future__ import annotations

import pytest

from acopia.application.backtest import backtest_rodante
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.observacion import Observacion
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio


class _ForecasterConstante:
    """Forecaster stub: siempre pronostica la misma generación y CMg."""

    def __init__(self, generacion: int, cmg: int) -> None:
        self._generacion = generacion
        self._cmg = cmg

    def pronosticar(
        self,
        historia: tuple[Observacion, ...],
        horizonte: int,
        n_escenarios: int,
        semilla: int,
    ) -> tuple[Escenario, ...]:
        puntos = tuple(
            PuntoPronostico(Potencia(self._generacion), Precio(self._cmg))
            for _ in range(horizonte)
        )
        return (Escenario(puntos),)


def _historia_constante(n: int, gen: int, cmg: int) -> tuple[Observacion, ...]:
    return tuple(Observacion(Potencia(gen), Precio(cmg)) for _ in range(n))


def test_backtest_promedia_las_metricas_por_serie() -> None:
    # historia constante gen=30, cmg=100; el stub pronostica gen=0, cmg=100.
    historia = _historia_constante(6, gen=30, cmg=100)
    resultado = backtest_rodante(
        _ForecasterConstante(generacion=0, cmg=100), historia, horizonte=2, folds=2
    )
    assert resultado.folds == 2
    assert resultado.horizonte == 2
    assert resultado.generacion.rmse == 30.0  # |30 - 0|
    assert resultado.generacion.mape == 100.0  # (30-0)/30
    assert resultado.cmg.rmse == 0.0  # pronóstico exacto
    assert resultado.cmg.mape == 0.0


def test_backtest_historia_insuficiente_es_error() -> None:
    historia = _historia_constante(4, gen=10, cmg=100)
    with pytest.raises(ValueError, match="insuficiente"):
        backtest_rodante(_ForecasterConstante(0, 0), historia, horizonte=2, folds=2)


def test_backtest_valida_folds_y_horizonte() -> None:
    historia = _historia_constante(10, gen=10, cmg=100)
    with pytest.raises(ValueError, match="horizonte"):
        backtest_rodante(_ForecasterConstante(0, 0), historia, horizonte=0, folds=1)
    with pytest.raises(ValueError, match="folds"):
        backtest_rodante(_ForecasterConstante(0, 0), historia, horizonte=2, folds=0)


class _ForecasterEspia(_ForecasterConstante):
    """Registra el largo de la historia con que se le pide pronosticar."""

    def __init__(self) -> None:
        super().__init__(generacion=0, cmg=0)
        self.largos: list[int] = []

    def pronosticar(
        self,
        historia: tuple[Observacion, ...],
        horizonte: int,
        n_escenarios: int,
        semilla: int,
    ) -> tuple[Escenario, ...]:
        self.largos.append(len(historia))
        return super().pronosticar(historia, horizonte, n_escenarios, semilla)


def test_ventana_de_entrenamiento_recorta_la_historia() -> None:
    historia = _historia_constante(10, gen=10, cmg=100)
    espia = _ForecasterEspia()
    backtest_rodante(espia, historia, horizonte=2, folds=2, ventana_entrenamiento=3)
    # fold 0 entrena con obs[:6] recortado a 3; fold 1 con obs[:8] recortado a 3
    assert espia.largos == [3, 3]


def test_ventana_expansiva_por_defecto() -> None:
    historia = _historia_constante(10, gen=10, cmg=100)
    espia = _ForecasterEspia()
    backtest_rodante(espia, historia, horizonte=2, folds=2)
    assert espia.largos == [6, 8]


def test_ventana_invalida_es_error() -> None:
    historia = _historia_constante(10, gen=10, cmg=100)
    with pytest.raises(ValueError, match="ventana_entrenamiento"):
        backtest_rodante(
            _ForecasterConstante(0, 0), historia, horizonte=2, folds=1,
            ventana_entrenamiento=0,
        )


def test_backtest_un_solo_fold() -> None:
    # folds=1 con historia justa (> horizonte): un único tramo out-of-sample.
    historia = _historia_constante(3, gen=30, cmg=0)
    resultado = backtest_rodante(_ForecasterConstante(30, 0), historia, horizonte=2, folds=1)
    assert resultado.folds == 1
    assert resultado.generacion.rmse == 0.0  # pronóstico exacto
