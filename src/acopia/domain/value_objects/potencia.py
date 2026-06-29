"""Potencia en W enteros (magnitud, no negativa)."""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo


@dataclass(frozen=True, slots=True, order=True)
class Potencia:
    """Potencia de intercambio con la red, en W enteros (magnitud >= 0).

    El sentido (carga/descarga) lo lleva la acción de despacho, no el signo.
    """

    w: int

    def __post_init__(self) -> None:
        if self.w < 0:
            raise ValueError(f"La potencia no puede ser negativa: {self.w} W")

    @classmethod
    def cero(cls) -> Potencia:
        return cls(0)

    def energia_en(self, intervalo: Intervalo) -> Energia:
        """Energía (Wh) intercambiada al sostener esta potencia durante el intervalo.

        E[Wh] = P[W] * t[s] / 3600, con división entera (floor) determinista.
        """
        return Energia((self.w * intervalo.segundos) // 3600)

    def __str__(self) -> str:
        return f"{self.w} W"
