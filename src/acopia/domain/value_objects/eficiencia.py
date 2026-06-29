"""Eficiencia como puntos base enteros (0..10000 = 0 %..100 %)."""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.value_objects.energia import Energia

_BASE = 10_000


@dataclass(frozen=True, slots=True, order=True)
class Eficiencia:
    """Eficiencia en puntos base (0..10000). 9500 = 95,00 %.

    Entera para preservar el determinismo: aplicar y revertir usan división
    entera (floor), reproducible.
    """

    puntos_base: int

    def __post_init__(self) -> None:
        if not 0 <= self.puntos_base <= _BASE:
            raise ValueError(f"Eficiencia fuera de rango [0..{_BASE}]: {self.puntos_base}")

    @classmethod
    def de_porcentaje(cls, porcentaje: int) -> Eficiencia:
        """Construye desde un porcentaje entero (95 -> 95,00 %)."""
        return cls(porcentaje * 100)

    def aplicar(self, energia: Energia) -> Energia:
        """Energía resultante tras la pérdida (carga: red -> celdas)."""
        return Energia((energia.wh * self.puntos_base) // _BASE)

    def revertir(self, energia: Energia) -> Energia:
        """Energía bruta necesaria para entregar ``energia`` (descarga: red <- celdas).

        Requiere eficiencia > 0; revertir con eficiencia nula no tiene sentido físico.
        """
        if self.puntos_base == 0:
            raise ValueError("No se puede revertir con eficiencia nula")
        return Energia((energia.wh * _BASE) // self.puntos_base)

    def __str__(self) -> str:
        return f"{self.puntos_base / 100:.2f} %"
