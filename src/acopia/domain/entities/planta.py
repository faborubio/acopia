"""Planta PV-BESS: batería + punto de conexión a la red.

El **punto de conexión** impone el techo de inyección al nodo (límite de
transmisión): cuando la generación PV más la descarga superan ese techo, el
excedente debe **almacenarse o verterse** (curtailment). Es la causa estructural
del vertimiento solar en Chile (congestión norte-centro).
"""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.entities.bateria import Bateria
from acopia.domain.value_objects.potencia import Potencia


@dataclass(frozen=True, slots=True)
class Planta:
    """PV + batería + punto de conexión. Inmutable.

    ``potencia_max_inyeccion``: techo de inyección al nodo (límite de transmisión).
    ``potencia_max_retiro``: techo de retiro de la red (para cargar desde la red).
    """

    id: str
    bateria: Bateria
    potencia_max_inyeccion: Potencia
    potencia_max_retiro: Potencia

    @classmethod
    def con_conexion_simetrica(
        cls, id: str, bateria: Bateria, potencia_conexion: Potencia
    ) -> Planta:
        """Planta cuyo punto de conexión inyecta y retira con el mismo límite."""
        return cls(id, bateria, potencia_conexion, potencia_conexion)
