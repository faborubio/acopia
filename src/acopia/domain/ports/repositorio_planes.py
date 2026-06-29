"""Puerto de persistencia de planes y su rastro (snapshot as-seen)."""

from __future__ import annotations

from typing import Protocol

from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.rastro import RastroDespacho


class RepositorioPlanes(Protocol):
    """Guarda y recupera planes junto con su rastro auditable."""

    def guardar(self, plan: PlanDespacho, rastro: RastroDespacho) -> str:
        """Persiste el plan y su rastro; devuelve el identificador asignado."""
        ...

    def obtener(self, plan_id: str) -> tuple[PlanDespacho, RastroDespacho]:
        """Recupera el plan y su rastro por identificador."""
        ...
