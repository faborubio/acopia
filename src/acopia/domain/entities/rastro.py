"""RastroDespacho: snapshot as-seen que hace reconstruible y auditable un plan (ADR-007)."""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.entities.escenario import Escenario
from acopia.domain.entities.estado_bateria import EstadoBateria


@dataclass(frozen=True, slots=True)
class RastroDespacho:
    """Forecast, estado inicial y semilla con que se generó un plan.

    Sin este snapshot, el backtest y la simulación no son fieles: guarda el forecast
    y el estado *tal como se vieron* al planificar.
    """

    politica_id: str
    politica_version: int
    semilla: int
    estado_inicial: EstadoBateria
    escenarios: tuple[Escenario, ...]

    def __post_init__(self) -> None:
        if not self.escenarios:
            raise ValueError("El rastro debe guardar al menos un escenario")
