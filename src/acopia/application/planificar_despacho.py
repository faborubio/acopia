"""Caso de uso PlanificarDespacho: fija la política, optimiza y persiste plan + rastro.

Dos pasos críticos para la auditabilidad (estilo Movinta/Veredicto): se fija la
**versión de política** y se persiste el **snapshot** (forecast + estado as-seen).
Sin eso, el backtest y la simulación no son fieles (ADR-007, ADR-008).
"""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.entities.escenario import Escenario
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import PoliticaDespacho
from acopia.domain.entities.rastro import RastroDespacho
from acopia.domain.ports.puerto_optimizador import PuertoOptimizador
from acopia.domain.ports.repositorio_planes import RepositorioPlanes


@dataclass(frozen=True, slots=True)
class ResultadoPlanificacion:
    """Salida del caso de uso: el plan y su identificador persistido."""

    plan_id: str
    plan: PlanDespacho


class PlanificarDespacho:
    """Orquesta el dominio a través de puertos; no conoce solver ni base de datos."""

    def __init__(self, optimizador: PuertoOptimizador, repositorio: RepositorioPlanes) -> None:
        self._optimizador = optimizador
        self._repositorio = repositorio

    def ejecutar(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        escenario: Escenario,
        politica: PoliticaDespacho,
    ) -> ResultadoPlanificacion:
        plan = self._optimizador.optimizar(planta, estado_inicial, escenario, politica)
        rastro = RastroDespacho(
            politica_id=politica.id,
            politica_version=politica.version,
            semilla=politica.semilla,
            estado_inicial=estado_inicial,
            escenarios=(escenario,),
        )
        plan_id = self._repositorio.guardar(plan, rastro)
        return ResultadoPlanificacion(plan_id=plan_id, plan=plan)
