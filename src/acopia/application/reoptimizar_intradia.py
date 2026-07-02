"""ReoptimizarIntradia: recalcula el plan del resto del día ante desvíos (§6.2).

Cuando la telemetría muestra que la generación real se desvió del forecast que el
plan asumió, se reoptimiza **desde el estado real de la batería** para los
intervalos restantes, con el forecast actualizado. La política (id/versión,
objetivo, restricciones) no cambia: solo se aplica a la ventana que queda —
`horizonte_intervalos` se recorta operacionalmente, sin re-versionar (ADR-008).

Límite honesto (SAD §6.2): la telemetría plant-level real no es pública; en
portafolio los desvíos se demuestran con una planta modelo sintética. El puerto y
el caso de uso quedan listos para telemetría real.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from acopia.domain.entities.escenario import Escenario
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import PoliticaDespacho
from acopia.domain.ports.puerto_optimizador import PuertoOptimizador


@dataclass(frozen=True, slots=True)
class ResultadoReoptimizacion:
    """Plan para el resto del día, desde el intervalo actual y el estado real."""

    plan_restante: PlanDespacho
    intervalo_desde: int
    intervalos_restantes: int


def reoptimizar_intradia(
    optimizador: PuertoOptimizador,
    planta: Planta,
    estado_real: EstadoBateria,
    escenarios_actualizados: tuple[Escenario, ...],
    politica: PoliticaDespacho,
    intervalo_actual: int,
) -> ResultadoReoptimizacion:
    """Reoptimiza los intervalos restantes del día desde el estado real.

    ``intervalo_actual`` es 0-based: cuántos intervalos del plan original ya
    transcurrieron. Los ``escenarios_actualizados`` cubren exactamente el resto.
    """
    horizonte = politica.horizonte_intervalos
    if not 0 < intervalo_actual < horizonte:
        raise ValueError(
            f"intervalo_actual ({intervalo_actual}) debe estar en (0, {horizonte}): "
            "reoptimizar exige que haya transcurrido al menos un intervalo y quede al menos uno"
        )
    restantes = horizonte - intervalo_actual
    for indice, escenario in enumerate(escenarios_actualizados):
        if len(escenario) != restantes:
            raise ValueError(
                f"El escenario {indice} tiene {len(escenario)} puntos; "
                f"quedan {restantes} intervalos"
            )

    politica_restante = replace(politica, horizonte_intervalos=restantes)
    plan = optimizador.optimizar_escenarios(
        planta, estado_real, escenarios_actualizados, politica_restante
    )
    return ResultadoReoptimizacion(
        plan_restante=plan,
        intervalo_desde=intervalo_actual,
        intervalos_restantes=restantes,
    )
