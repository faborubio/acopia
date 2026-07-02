"""Servidor MCP de Acopia (FastMCP): consulta, explicación y simulación del despacho.

Herramientas (§5 del SAD): ``consultar_despacho``, ``explicar_despacho`` y
``simular_escenario``. **Decisión de seguridad:** la capa MCP es read-only +
simulación — no envía órdenes al SCADA ni activa un plan real; simular no persiste.
``comparar_modos`` (determinista vs DRL) llega con el modo DRL (ADR-005).

El servidor se arma por inyección (`crear_servidor`); ``python -m
acopia.interfaces.mcp.servidor`` levanta una demo stdio con un plan sembrado para
interrogarlo desde Claude ("¿por qué cargaste a mediodía?").
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastmcp import FastMCP

from acopia.application.simular_escenario import simular_escenario
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import PoliticaDespacho
from acopia.domain.ports.puerto_optimizador import PuertoOptimizador
from acopia.domain.ports.repositorio_planes import RepositorioPlanes
from acopia.domain.services.explicador_despacho import ExplicadorDespacho


def _resumen_plan(plan_id: str, plan: PlanDespacho) -> dict[str, Any]:
    acciones = [
        {"intervalo": k, "accion": a.tipo.value, "potencia_w": a.potencia.w}
        for k, a in enumerate(plan.acciones)
    ]
    return {
        "plan_id": plan_id,
        "politica": {"id": plan.politica_id, "version": plan.politica_version},
        "semilla": plan.semilla,
        "ingreso_esperado_mills": plan.ingreso_esperado_mills,
        "energia_vertida_total_wh": sum(plan.energia_vertida_wh),
        "reserva_sscc_w": list(plan.reserva_w),
        "acciones": acciones,
    }


def crear_servidor(
    repositorio: RepositorioPlanes,
    optimizador: PuertoOptimizador,
    planta: Planta,
    politica: PoliticaDespacho,
) -> FastMCP:
    """Arma el servidor MCP sobre los puertos del dominio (read-only + simulación)."""
    servidor: FastMCP = FastMCP(
        name="acopia",
        instructions=(
            "Motor de despacho PV-BESS (mercado chileno). Consulta, explica y simula "
            "planes de despacho. Solo lectura y simulación: nada se ejecuta ni persiste."
        ),
    )
    explicador = ExplicadorDespacho()

    @servidor.tool
    def consultar_despacho(plan_id: str) -> dict[str, Any]:
        """Resumen de un plan: acciones por intervalo, ingreso esperado, vertido y banda SSCC."""
        plan, _ = repositorio.obtener(plan_id)
        return _resumen_plan(plan_id, plan)

    @servidor.tool
    def explicar_despacho(plan_id: str, intervalo: int | None = None) -> list[dict[str, Any]]:
        """Por qué el plan cargó/descargó/retuvo: CMg relativo, SoC, vertido y banda.

        Con ``intervalo`` explica solo ese paso; sin él, todo el horizonte.
        """
        plan, rastro = repositorio.obtener(plan_id)
        explicaciones = explicador.explicar(
            planta.bateria, plan, rastro, politica.resolucion
        )
        if intervalo is not None:
            if not 0 <= intervalo < len(explicaciones):
                raise ValueError(
                    f"Intervalo {intervalo} fuera del horizonte [0, {len(explicaciones) - 1}]"
                )
            return [asdict(explicaciones[intervalo])]
        return [asdict(e) for e in explicaciones]

    @servidor.tool
    def simular(
        plan_id: str,
        cmg_por_intervalo: dict[str, int] | None = None,
        factor_generacion_pct: int = 100,
    ) -> dict[str, Any]:
        """Reevalúa el despacho bajo un escenario modificado (sin efectos ni persistencia).

        ``cmg_por_intervalo``: CMg (mills/MWh) a forzar por intervalo, p. ej.
        ``{"12": 0}`` = CMg cero al mediodía. ``factor_generacion_pct``: escala la
        generación PV (100 = sin cambio, 0 = nublado total).
        """
        plan, rastro = repositorio.obtener(plan_id)
        overrides = {int(k): v for k, v in (cmg_por_intervalo or {}).items()}
        resultado = simular_escenario(
            optimizador,
            planta,
            plan,
            rastro,
            politica,
            cmg_por_intervalo=overrides,
            factor_generacion_bp=factor_generacion_pct * 100,
        )
        return {
            "plan_id_original": plan_id,
            "ingreso_original_mills": resultado.ingreso_original_mills,
            "ingreso_simulado_mills": resultado.ingreso_simulado_mills,
            "delta_ingreso_mills": resultado.delta_ingreso_mills,
            "plan_simulado": _resumen_plan("(simulado, no persistido)", resultado.plan_simulado),
        }

    return servidor


def _demo() -> FastMCP:
    """Demo stdio: planta modelo + un plan de arbitraje sembrado, listo para interrogar."""
    from acopia.application.planificar_despacho import PlanificarDespacho
    from acopia.domain.entities.bateria import Bateria
    from acopia.domain.entities.escenario import Escenario, PuntoPronostico
    from acopia.domain.entities.estado_bateria import EstadoBateria
    from acopia.domain.entities.politica_despacho import Modo, Objetivo
    from acopia.domain.value_objects.eficiencia import Eficiencia
    from acopia.domain.value_objects.energia import Energia
    from acopia.domain.value_objects.intervalo import Intervalo
    from acopia.domain.value_objects.potencia import Potencia
    from acopia.domain.value_objects.precio import Precio
    from acopia.domain.value_objects.soc import Soc
    from acopia.infrastructure.optimizacion.optimizador_lp import OptimizadorLP
    from acopia.infrastructure.persistencia.repositorio_planes_memoria import (
        RepositorioPlanesEnMemoria,
    )

    bateria = Bateria(
        capacidad=Energia(100_000),
        potencia_max_carga=Potencia(50_000),
        potencia_max_descarga=Potencia(50_000),
        eficiencia_carga=Eficiencia.de_porcentaje(95),
        eficiencia_descarga=Eficiencia.de_porcentaje(95),
        soc_min=Soc.de_porcentaje(0),
        soc_max=Soc.de_porcentaje(100),
        throughput_garantia=Energia(1_000_000_000),
    )
    planta = Planta("planta-demo", bateria, Potencia(80_000), Potencia(0))
    politica = PoliticaDespacho(
        id="arbitraje-demo",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=24,
        resolucion=Intervalo.de_minutos(60),
        semilla=42,
        modo=Modo.PREDICT_THEN_OPTIMIZE,
    )
    # Día chileno típico: PV de campana con CMg colapsado a mediodía y punta vespertina.
    generacion = [0, 0, 0, 0, 0, 0, 5, 20, 45, 65, 80, 90, 95, 90, 80, 65, 45, 20, 5, 0, 0, 0, 0, 0]
    cmg = [
        75, 74, 73, 72, 73, 75, 70, 40, 5, 0, 0, 0, 0, 0, 3, 10, 25, 60, 95, 110, 105, 95, 85, 80,
    ]
    escenario = Escenario(
        tuple(
            PuntoPronostico(Potencia(g * 1_000), Precio(c * 1_000))
            for g, c in zip(generacion, cmg, strict=True)
        )
    )
    repositorio = RepositorioPlanesEnMemoria()
    optimizador = OptimizadorLP()
    resultado = PlanificarDespacho(optimizador, repositorio).ejecutar(
        planta, EstadoBateria(Energia(20_000)), escenario, politica
    )
    servidor = crear_servidor(repositorio, optimizador, planta, politica)
    print(f"Plan demo sembrado: plan_id={resultado.plan_id}")
    return servidor


if __name__ == "__main__":
    _demo().run()
