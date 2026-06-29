"""Paso temporal del horizonte de despacho, en segundos enteros."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class Intervalo:
    """Duración de un paso del horizonte, en segundos enteros (> 0)."""

    segundos: int

    def __post_init__(self) -> None:
        if self.segundos <= 0:
            raise ValueError(f"El intervalo debe ser positivo: {self.segundos} s")

    @classmethod
    def de_minutos(cls, minutos: int) -> Intervalo:
        if minutos <= 0:
            raise ValueError(f"Los minutos deben ser positivos: {minutos}")
        return cls(minutos * 60)

    def __str__(self) -> str:
        return f"{self.segundos} s"
