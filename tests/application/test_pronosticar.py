"""Tests del caso de uso PronosticarConRastro (forecast + snapshot as-seen, ADR-007)."""

from __future__ import annotations

import pytest

from acopia.application.pronosticar import pronosticar_con_rastro, reproduce_el_rastro
from acopia.domain.entities.observacion import Observacion
from acopia.domain.services.huella import huella_historia
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.infrastructure.forecasting.forecaster_estacional import ForecasterEstacionalNaive

_PATRON = [(0, 90_000), (50, 70_000), (100, 5_000), (50, 250_000)]


def _historia(n: int = 16) -> tuple[Observacion, ...]:
    return tuple(Observacion(Potencia(g), Precio(c)) for g, c in (_PATRON[i % 4] for i in range(n)))


def _forecaster() -> ForecasterEstacionalNaive:
    return ForecasterEstacionalNaive(estacionalidad=4)


def test_captura_la_procedencia_as_seen() -> None:
    historia = _historia()
    resultado = pronosticar_con_rastro(
        _forecaster(), "naive@estacionalidad4", historia, horizonte=4, n_escenarios=3, semilla=7
    )
    rastro = resultado.rastro
    assert rastro.forecaster == "naive@estacionalidad4"
    assert rastro.horizonte == 4
    assert rastro.n_escenarios == 3
    assert rastro.semilla == 7
    assert rastro.n_observaciones == len(historia)
    assert rastro.huella_historia == huella_historia(historia)
    assert rastro.escenarios == resultado.escenarios


def test_el_rastro_se_reproduce() -> None:
    historia = _historia()
    resultado = pronosticar_con_rastro(
        _forecaster(), "naive", historia, horizonte=4, n_escenarios=5, semilla=3
    )
    # Un auditor regenera el forecast con la misma historia y semilla.
    assert reproduce_el_rastro(_forecaster(), historia, resultado.rastro) is True


def test_no_reproduce_con_otra_historia() -> None:
    historia = _historia()
    resultado = pronosticar_con_rastro(
        _forecaster(), "naive", historia, horizonte=4, n_escenarios=2, semilla=3
    )
    otra = (*_historia()[:-1], Observacion(Potencia(999), Precio(1)))
    assert reproduce_el_rastro(_forecaster(), otra, resultado.rastro) is False


def test_historia_vacia_es_error() -> None:
    with pytest.raises(ValueError, match="vacía"):
        pronosticar_con_rastro(_forecaster(), "naive", (), horizonte=4, n_escenarios=1, semilla=0)
