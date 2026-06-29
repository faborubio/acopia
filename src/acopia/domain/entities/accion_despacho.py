"""Acción de despacho en un intervalo: cargar, descargar o retener."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from acopia.domain.value_objects.potencia import Potencia


class TipoAccion(Enum):
    CARGAR = "CARGAR"
    DESCARGAR = "DESCARGAR"
    RETENER = "RETENER"


@dataclass(frozen=True, slots=True)
class AccionDespacho:
    """Decisión para un intervalo: un tipo y la potencia de intercambio con la red.

    Invariante: RETENER exige potencia cero; CARGAR/DESCARGAR exigen potencia > 0.
    """

    tipo: TipoAccion
    potencia: Potencia

    def __post_init__(self) -> None:
        if self.tipo is TipoAccion.RETENER and self.potencia.w != 0:
            raise ValueError("RETENER exige potencia cero")
        if self.tipo is not TipoAccion.RETENER and self.potencia.w == 0:
            raise ValueError(f"{self.tipo.value} exige potencia mayor que cero")

    @classmethod
    def retener(cls) -> AccionDespacho:
        return cls(TipoAccion.RETENER, Potencia.cero())

    @classmethod
    def cargar(cls, potencia: Potencia) -> AccionDespacho:
        return cls(TipoAccion.CARGAR, potencia)

    @classmethod
    def descargar(cls, potencia: Potencia) -> AccionDespacho:
        return cls(TipoAccion.DESCARGAR, potencia)
