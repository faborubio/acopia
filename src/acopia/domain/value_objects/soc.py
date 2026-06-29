"""Estado de carga (SoC) en puntos base enteros (0..10000 = 0 %..100 %)."""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.value_objects.energia import Energia

_BASE = 10_000


@dataclass(frozen=True, slots=True, order=True)
class Soc:
    """Estado de carga en puntos base (0..10000). Discretizado para determinismo."""

    puntos_base: int

    def __post_init__(self) -> None:
        if not 0 <= self.puntos_base <= _BASE:
            raise ValueError(f"SoC fuera de rango [0..{_BASE}]: {self.puntos_base}")

    @classmethod
    def de_porcentaje(cls, porcentaje: int) -> Soc:
        return cls(porcentaje * 100)

    @classmethod
    def desde_energia(cls, almacenada: Energia, capacidad: Energia) -> Soc:
        if capacidad.wh <= 0:
            raise ValueError("La capacidad debe ser positiva para calcular el SoC")
        return cls((almacenada.wh * _BASE) // capacidad.wh)

    def energia_en(self, capacidad: Energia) -> Energia:
        """Energía almacenada que corresponde a este SoC para una capacidad dada."""
        return Energia((capacidad.wh * self.puntos_base) // _BASE)

    @property
    def fraccion(self) -> float:
        """Fracción [0..1] — solo para presentación, no para cálculo de dominio."""
        return self.puntos_base / _BASE

    def __str__(self) -> str:
        return f"{self.puntos_base / 100:.2f} %"
