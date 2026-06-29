"""PlanDespacho: salida inmutable del motor — una acción por intervalo + ingreso esperado."""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.entities.accion_despacho import AccionDespacho


@dataclass(frozen=True, slots=True)
class PlanDespacho:
    """Plan resultante, trazable a (política, semilla).

    ``ingreso_esperado_mills`` se calcula con la ``FuncionObjetivo`` del dominio sobre
    el plan factible: es el número auditable, no el reportado por el solver.
    """

    politica_id: str
    politica_version: int
    semilla: int
    acciones: tuple[AccionDespacho, ...]
    ingreso_esperado_mills: int

    def __post_init__(self) -> None:
        if not self.acciones:
            raise ValueError("Un plan debe tener al menos una acción")

    def __len__(self) -> int:
        return len(self.acciones)
