"""Observación histórica: generación PV y CMg medidos en un intervalo pasado.

Es el insumo del forecaster (lo observado), frente a `PuntoPronostico` (lo predicho).
"""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio


@dataclass(frozen=True, slots=True)
class Observacion:
    """Generación PV y CMg observados en un intervalo histórico."""

    generacion: Potencia
    cmg: Precio
