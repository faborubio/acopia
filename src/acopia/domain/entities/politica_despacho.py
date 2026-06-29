"""PolíticaDeDespacho: unidad atómica versionada que lleva la semántica del despacho.

Reproducir un plan = fijar (política, forecast as-seen, semilla). El motor es
estable; la política versionada define restricciones, objetivo y horizonte.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from acopia.domain.value_objects.intervalo import Intervalo


class Objetivo(Enum):
    MAX_INGRESO = "MAX_INGRESO"
    MIN_CURTAILMENT = "MIN_CURTAILMENT"
    HIBRIDO = "HIBRIDO"


class Modo(Enum):
    PREDICT_THEN_OPTIMIZE = "PREDICT_THEN_OPTIMIZE"
    DRL = "DRL"


@dataclass(frozen=True, slots=True)
class PoliticaDespacho:
    """Restricciones + objetivo + horizonte, versionado e inmutable.

    ``costo_ciclado_mills_por_mwh`` es la penalización por degradación aplicada a la
    energía que pasa por las celdas; evita que un plan "gane" destruyendo la batería.
    La co-optimización con SSCC (``productos_sscc``) llega en la Fase 4.
    """

    id: str
    version: int
    objetivo: Objetivo
    horizonte_intervalos: int
    resolucion: Intervalo
    semilla: int
    modo: Modo = Modo.PREDICT_THEN_OPTIMIZE
    costo_ciclado_mills_por_mwh: int = 0

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError(f"La versión debe ser >= 1: {self.version}")
        if self.horizonte_intervalos < 1:
            raise ValueError(f"El horizonte debe tener >= 1 intervalo: {self.horizonte_intervalos}")
        if self.costo_ciclado_mills_por_mwh < 0:
            raise ValueError("El costo de ciclado no puede ser negativo")
