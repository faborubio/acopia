"""Batería: configuración física e invariantes (capacidad, potencia, eficiencia, límites)."""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.soc import Soc


@dataclass(frozen=True, slots=True)
class Bateria:
    """Parámetros físicos de la batería. Inmutable.

    ``throughput_garantia`` es la energía total (a través de las celdas) que el
    fabricante garantiza durante la vida útil; es el límite que de verdad acota
    cuánto puede ciclar el activo (más que un "máximo de ciclos por día").
    El C-rate queda implícito en ``potencia_max_*`` expresado en W.
    """

    capacidad: Energia
    potencia_max_carga: Potencia
    potencia_max_descarga: Potencia
    eficiencia_carga: Eficiencia
    eficiencia_descarga: Eficiencia
    soc_min: Soc
    soc_max: Soc
    throughput_garantia: Energia

    def __post_init__(self) -> None:
        if self.capacidad.wh <= 0:
            raise ValueError("La capacidad debe ser positiva")
        if self.soc_min > self.soc_max:
            raise ValueError(f"soc_min {self.soc_min} no puede superar soc_max {self.soc_max}")
        if self.eficiencia_descarga.puntos_base == 0:
            raise ValueError("La eficiencia de descarga no puede ser nula")

    @property
    def energia_min(self) -> Energia:
        """Energía almacenada en el SoC mínimo operativo."""
        return self.soc_min.energia_en(self.capacidad)

    @property
    def energia_max(self) -> Energia:
        """Energía almacenada en el SoC máximo operativo."""
        return self.soc_max.energia_en(self.capacidad)
