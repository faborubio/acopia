"""Repositorio de planes en memoria (Fase 1). El backend Timescale llega en fase posterior."""

from __future__ import annotations

from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.rastro import RastroDespacho


class RepositorioPlanesEnMemoria:
    """Implementa `RepositorioPlanes` con un dict. Útil para tests y la fase local."""

    def __init__(self) -> None:
        self._datos: dict[str, tuple[PlanDespacho, RastroDespacho]] = {}
        self._contador = 0

    def guardar(self, plan: PlanDespacho, rastro: RastroDespacho) -> str:
        self._contador += 1
        plan_id = f"plan-{self._contador}"
        self._datos[plan_id] = (plan, rastro)
        return plan_id

    def obtener(self, plan_id: str) -> tuple[PlanDespacho, RastroDespacho]:
        if plan_id not in self._datos:
            raise KeyError(f"No existe el plan {plan_id}")
        return self._datos[plan_id]
