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
    energia_vertida_wh: tuple[int, ...]
    ingreso_esperado_mills: int
    reserva_w: tuple[int, ...] = ()  # banda SSCC comprometida por intervalo (W); () = sin SSCC

    def __post_init__(self) -> None:
        if not self.acciones:
            raise ValueError("Un plan debe tener al menos una acción")
        if len(self.energia_vertida_wh) != len(self.acciones):
            raise ValueError("energia_vertida_wh debe tener una entrada por acción")
        if any(v < 0 for v in self.energia_vertida_wh):
            raise ValueError("La energía vertida no puede ser negativa")
        if self.reserva_w and len(self.reserva_w) != len(self.acciones):
            raise ValueError("reserva_w debe tener una entrada por acción (o ser vacía)")
        if any(r < 0 for r in self.reserva_w):
            raise ValueError("La reserva no puede ser negativa")

    def __len__(self) -> int:
        return len(self.acciones)
