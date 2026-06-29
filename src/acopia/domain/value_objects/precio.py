"""Precio nodal (costo marginal, CMg) en mills enteros por MWh.

1 mill = 1/1000 de la unidad monetaria. El CMg **puede ser negativo** (sobreoferta
solar + congestión): no se restringe el signo.
"""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.value_objects.energia import Energia

_WH_POR_MWH = 1_000_000


@dataclass(frozen=True, slots=True, order=True)
class Precio:
    """CMg en mills por MWh (entero). Puede ser negativo."""

    mills_por_mwh: int

    def ingreso_por(self, energia: Energia) -> int:
        """Ingreso en mills por inyectar ``energia`` (Wh, no negativa) a este precio."""
        return (self.mills_por_mwh * energia.wh) // _WH_POR_MWH

    def ingreso_por_wh(self, wh: int) -> int:
        """Ingreso en mills por un flujo de energía con signo (Wh; negativo = retiro)."""
        return (self.mills_por_mwh * wh) // _WH_POR_MWH

    def __str__(self) -> str:
        return f"{self.mills_por_mwh} mills/MWh"
