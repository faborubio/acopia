"""Tests de la detección de desvío forecast-vs-real (gatillo de §6.2)."""

from __future__ import annotations

import pytest

from acopia.domain.entities.escenario import PuntoPronostico
from acopia.domain.entities.observacion import Observacion
from acopia.domain.services.deteccion_desvio import desvio_generacion_bp, hay_desvio
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio


def _previsto(*gens: int) -> list[PuntoPronostico]:
    return [PuntoPronostico(Potencia(g), Precio(50_000)) for g in gens]


def _observado(*gens: int) -> list[Observacion]:
    return [Observacion(Potencia(g), Precio(50_000)) for g in gens]


def test_sin_desvio_cuando_coincide() -> None:
    assert desvio_generacion_bp(_previsto(1000, 2000), _observado(1000, 2000)) == 0


def test_desvio_relativo_en_puntos_base() -> None:
    # previsto 8000 acumulado, real 4000: desvío 50 % = 5000 bp
    assert desvio_generacion_bp(_previsto(4000, 4000), _observado(4000, 0)) == 5_000


def test_noche_sin_generacion_no_es_desvio() -> None:
    assert desvio_generacion_bp(_previsto(0, 0), _observado(0, 0)) == 0


def test_generacion_inesperada_de_noche_es_desvio_total() -> None:
    assert desvio_generacion_bp(_previsto(0, 0), _observado(0, 500)) == 10_000


def test_hay_desvio_respeta_el_umbral() -> None:
    previsto, observado = _previsto(4000, 4000), _observado(4000, 0)  # 5000 bp
    assert hay_desvio(previsto, observado, umbral_bp=2_000) is True
    assert hay_desvio(previsto, observado, umbral_bp=5_000) is False  # estricto


def test_largos_distintos_es_error() -> None:
    with pytest.raises(ValueError, match="mismo largo"):
        desvio_generacion_bp(_previsto(1000), _observado(1000, 2000))


def test_umbral_negativo_es_error() -> None:
    with pytest.raises(ValueError, match="umbral"):
        hay_desvio(_previsto(1000), _observado(1000), umbral_bp=-1)
