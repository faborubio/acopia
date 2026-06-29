"""Estado dinámico de la batería en un instante: energía almacenada y throughput acumulado."""

from __future__ import annotations

from dataclasses import dataclass, field

from acopia.domain.entities.bateria import Bateria
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.soc import Soc


@dataclass(frozen=True, slots=True)
class EstadoBateria:
    """Estado en un instante. Inmutable: aplicar una acción produce un estado nuevo.

    ``throughput_acumulado`` es la energía total que ya pasó por las celdas
    (suma de cargas y descargas a nivel de celda); se compara contra
    ``Bateria.throughput_garantia``.
    """

    energia_almacenada: Energia
    throughput_acumulado: Energia = field(default_factory=Energia.cero)

    def soc(self, bateria: Bateria) -> Soc:
        return Soc.desde_energia(self.energia_almacenada, bateria.capacidad)
