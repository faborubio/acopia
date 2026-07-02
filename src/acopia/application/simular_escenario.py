"""SimularEscenario: reevaluar el despacho bajo un escenario modificado, sin efectos (§5).

Es la herramienta de simulación de la capa MCP ("simulá un día con CMg cero al
mediodía"): parte del escenario as-seen del rastro (ADR-007), aplica los cambios
pedidos (CMg por intervalo, factor de generación) y re-optimiza. **No persiste
nada**: devuelve la comparación contra el plan original.
"""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import PoliticaDespacho
from acopia.domain.entities.rastro import RastroDespacho
from acopia.domain.ports.puerto_optimizador import PuertoOptimizador
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio

_BASE = 10_000


@dataclass(frozen=True, slots=True)
class ResultadoSimulacion:
    """Comparación plan original vs plan bajo el escenario simulado."""

    escenario_simulado: Escenario
    plan_simulado: PlanDespacho
    ingreso_original_mills: int
    ingreso_simulado_mills: int

    @property
    def delta_ingreso_mills(self) -> int:
        return self.ingreso_simulado_mills - self.ingreso_original_mills


def simular_escenario(
    optimizador: PuertoOptimizador,
    planta: Planta,
    plan_original: PlanDespacho,
    rastro: RastroDespacho,
    politica: PoliticaDespacho,
    cmg_por_intervalo: dict[int, int] | None = None,
    factor_generacion_bp: int = _BASE,
) -> ResultadoSimulacion:
    """Re-optimiza sobre el escenario as-seen modificado. Sin efectos (no persiste).

    ``cmg_por_intervalo`` reemplaza el CMg (mills/MWh) de los intervalos indicados;
    ``factor_generacion_bp`` escala la generación PV (10000 = sin cambio, 0 = nublado
    total). El estado inicial y la política son los del plan original (as-seen).
    """
    if factor_generacion_bp < 0:
        raise ValueError(f"El factor de generación no puede ser negativo: {factor_generacion_bp}")
    base = rastro.escenarios[0]
    overrides = cmg_por_intervalo or {}
    for intervalo in overrides:
        if not 0 <= intervalo < len(base):
            raise ValueError(
                f"Intervalo {intervalo} fuera del horizonte [0, {len(base) - 1}]"
            )

    puntos = tuple(
        PuntoPronostico(
            Potencia((p.generacion.w * factor_generacion_bp) // _BASE),
            Precio(overrides.get(k, p.cmg.mills_por_mwh)),
        )
        for k, p in enumerate(base.puntos)
    )
    escenario_simulado = Escenario(puntos, base.probabilidad_bp)
    plan_simulado = optimizador.optimizar(
        planta, rastro.estado_inicial, escenario_simulado, politica
    )
    return ResultadoSimulacion(
        escenario_simulado=escenario_simulado,
        plan_simulado=plan_simulado,
        ingreso_original_mills=plan_original.ingreso_esperado_mills,
        ingreso_simulado_mills=plan_simulado.ingreso_esperado_mills,
    )
