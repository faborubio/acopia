"""Escenario: una trayectoria posible de generación PV y CMg, con su probabilidad."""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio

_BASE = 10_000


@dataclass(frozen=True, slots=True)
class PuntoPronostico:
    """Pronóstico para un intervalo: generación PV esperada y CMg nodal."""

    generacion: Potencia
    cmg: Precio


@dataclass(frozen=True, slots=True)
class Escenario:
    """Trayectoria de pronóstico sobre el horizonte, con probabilidad en puntos base.

    Para un despacho determinista (predict-then-optimize sobre el caso medio) se usa
    un único escenario con ``probabilidad_bp = 10000``. La optimización estocástica
    sobre varios escenarios llega en la Fase 3.
    """

    puntos: tuple[PuntoPronostico, ...]
    probabilidad_bp: int = _BASE

    def __post_init__(self) -> None:
        if not self.puntos:
            raise ValueError("Un escenario debe tener al menos un punto")
        if not 0 < self.probabilidad_bp <= _BASE:
            raise ValueError(f"Probabilidad fuera de rango (0..{_BASE}]: {self.probabilidad_bp}")

    def __len__(self) -> int:
        return len(self.puntos)
