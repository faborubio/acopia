"""Energía en Wh enteros (no negativa)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class Energia:
    """Cantidad de energía, en Wh enteros.

    No negativa: representa energía almacenada, capacidades y deltas absolutos.
    La aritmética que produzca un valor negativo es un error de dominio (p. ej.
    descargar más de lo disponible) y se señala con ``ValueError``.
    """

    wh: int

    def __post_init__(self) -> None:
        if self.wh < 0:
            raise ValueError(f"La energía no puede ser negativa: {self.wh} Wh")

    @classmethod
    def cero(cls) -> Energia:
        return cls(0)

    def __add__(self, otra: Energia) -> Energia:
        return Energia(self.wh + otra.wh)

    def __sub__(self, otra: Energia) -> Energia:
        return Energia(self.wh - otra.wh)

    def __str__(self) -> str:
        return f"{self.wh} Wh"
