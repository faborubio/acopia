"""CompararModos: el modo DRL medido contra el baseline determinista (ADR-005, §5).

Re-optimiza el **mismo** rastro as-seen (ADR-007) con ambos modos y devuelve la
comparación de ingresos. Sin efectos: no persiste nada. El cambio de ``modo`` en la
política es operacional (como el recorte de horizonte de ``reoptimizar_intradia``):
no se re-versiona, porque la semántica del despacho no cambia — solo el motor que
se está midiendo.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import Modo, PoliticaDespacho
from acopia.domain.entities.rastro import RastroDespacho
from acopia.domain.ports.puerto_optimizador import PuertoOptimizador

_BASE = 10_000


@dataclass(frozen=True, slots=True)
class ResultadoComparacion:
    """Ambos planes sobre el mismo escenario as-seen, con sus ingresos esperados."""

    plan_deterministico: PlanDespacho
    plan_drl: PlanDespacho

    @property
    def ingreso_deterministico_mills(self) -> int:
        return self.plan_deterministico.ingreso_esperado_mills

    @property
    def ingreso_drl_mills(self) -> int:
        return self.plan_drl.ingreso_esperado_mills

    @property
    def delta_mills(self) -> int:
        """DRL menos determinista: positivo = el DRL captura más ingreso."""
        return self.ingreso_drl_mills - self.ingreso_deterministico_mills

    @property
    def brecha_bp(self) -> int:
        """Delta relativo al baseline en puntos base (10000 = 100%)."""
        base = abs(self.ingreso_deterministico_mills)
        return (self.delta_mills * _BASE) // base if base else 0


def comparar_modos(
    optimizador_deterministico: PuertoOptimizador,
    optimizador_drl: PuertoOptimizador,
    planta: Planta,
    rastro: RastroDespacho,
    politica: PoliticaDespacho,
) -> ResultadoComparacion:
    """Corre ambos modos sobre los escenarios as-seen del rastro. No persiste.

    La comparación es honesta por construcción: mismos escenarios, mismo estado
    inicial, misma política (salvo ``modo``) y el ingreso de ambos planes se calcula
    con la misma ``FuncionObjetivo`` del dominio.
    """
    plan_det = optimizador_deterministico.optimizar_escenarios(
        planta,
        rastro.estado_inicial,
        rastro.escenarios,
        replace(politica, modo=Modo.PREDICT_THEN_OPTIMIZE),
    )
    plan_drl = optimizador_drl.optimizar_escenarios(
        planta,
        rastro.estado_inicial,
        rastro.escenarios,
        replace(politica, modo=Modo.DRL),
    )
    return ResultadoComparacion(plan_deterministico=plan_det, plan_drl=plan_drl)
