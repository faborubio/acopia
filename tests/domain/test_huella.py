"""Tests de la huella determinista de la historia (snapshot as-seen, ADR-007)."""

from __future__ import annotations

from acopia.domain.entities.observacion import Observacion
from acopia.domain.services.huella import huella_historia
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio


def _historia(*pares: tuple[int, int]) -> tuple[Observacion, ...]:
    return tuple(Observacion(Potencia(g), Precio(c)) for g, c in pares)


def test_huella_es_determinista() -> None:
    historia = _historia((0, 90_000), (50, 5_000))
    assert huella_historia(historia) == huella_historia(historia)


def test_huella_cambia_con_los_datos() -> None:
    a = _historia((0, 90_000), (50, 5_000))
    b = _historia((0, 90_000), (51, 5_000))  # una unidad distinta
    assert huella_historia(a) != huella_historia(b)


def test_huella_es_sensible_al_orden() -> None:
    a = _historia((0, 90_000), (50, 5_000))
    b = _historia((50, 5_000), (0, 90_000))
    assert huella_historia(a) != huella_historia(b)


def test_huella_de_una_sola_observacion() -> None:
    unica = _historia((100, -5_000))  # incluye CMg negativo
    assert isinstance(huella_historia(unica), str)
    assert len(huella_historia(unica)) == 64  # SHA-256 en hex
