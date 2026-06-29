"""Puerto del optimizador de despacho: el dominio lo define, la infraestructura lo implementa.

Detrás de este puerto vive el solver MILP/convexo (predict-then-optimize determinista)
y, más adelante, el agente DRL — siempre intercambiables y medidos contra el baseline.
"""

from __future__ import annotations

from typing import Protocol

from acopia.domain.entities.escenario import Escenario
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import PoliticaDespacho


class PuertoOptimizador(Protocol):
    """Genera un plan de despacho factible para un escenario y una política dados."""

    def optimizar(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        escenario: Escenario,
        politica: PoliticaDespacho,
    ) -> PlanDespacho:
        """Devuelve un plan factible (respeta batería y el límite de inyección del nodo)."""
        ...
