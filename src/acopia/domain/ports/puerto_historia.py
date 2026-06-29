"""Puerto de historia: el dominio lo define, la infraestructura lo implementa.

Abstrae el origen de las series históricas observadas (generación PV + CMg) que
alimentan al forecaster. Un adaptador puede leerlas de un CSV, de la API del
Coordinador/Explorador Solar, o de la base de datos.
"""

from __future__ import annotations

from typing import Protocol

from acopia.domain.entities.observacion import Observacion


class PuertoHistoria(Protocol):
    """Fuente de observaciones históricas, ordenadas cronológicamente."""

    def cargar(self) -> tuple[Observacion, ...]:
        """Devuelve la serie histórica observada (generación PV + CMg) en orden temporal."""
        ...
