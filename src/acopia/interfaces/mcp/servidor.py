"""Servidor MCP de Acopia (FastMCP): consulta, explicación, simulación y comparación.

Herramientas (§5 del SAD): ``consultar_despacho``, ``explicar_despacho``,
``simular`` y ``comparar_modos`` (determinista vs DRL, ADR-005). **Decisión de
seguridad:** la capa MCP es read-only + simulación — no envía órdenes al SCADA ni
activa un plan real; nada persiste.

El servidor se arma por inyección (`crear_servidor`); ``python -m
acopia.interfaces.mcp.servidor`` levanta una demo stdio con un plan sembrado para
interrogarlo desde Claude ("¿por qué cargaste a mediodía?").
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from typing import Any

from fastmcp import FastMCP

from acopia.application.comparar_modos import comparar_modos as comparar_modos_app
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
    optimizador_drl: PuertoOptimizador | None = None,
) -> FastMCP:
    """Arma el servidor MCP sobre los puertos del dominio (read-only + simulación).

    ``optimizador_drl`` habilita ``comparar_modos`` (ADR-005); si es ``None`` la
    herramienta existe pero responde con un error claro (extra ``acopia[drl]``).
    """
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

    @servidor.tool
    def comparar_modos(plan_id: str) -> dict[str, Any]:
        """Determinista vs DRL sobre el mismo escenario as-seen del plan (ADR-005).

        Entrena el agente DRL al vuelo (puede tardar). El baseline auditable sigue
        siendo el determinista: esta herramienta mide, no reemplaza. Sin efectos.
        """
        if optimizador_drl is None:
            raise ValueError(
                "El modo DRL no está disponible en este servidor: "
                "instala el extra acopia[drl] (stable-baselines3 + gymnasium)"
            )
        _, rastro = repositorio.obtener(plan_id)
        resultado = comparar_modos_app(optimizador, optimizador_drl, planta, rastro, politica)
        return {
            "plan_id": plan_id,
            "ingreso_deterministico_mills": resultado.ingreso_deterministico_mills,
            "ingreso_drl_mills": resultado.ingreso_drl_mills,
            "delta_mills": resultado.delta_mills,
            "brecha_bp": resultado.brecha_bp,
            "plan_deterministico": _resumen_plan(
                "(deterministico, no persistido)", resultado.plan_deterministico
            ),
            "plan_drl": _resumen_plan("(drl, no persistido)", resultado.plan_drl),
        }

    return servidor


def _demo() -> FastMCP:
    """Demo stdio: planta modelo + un plan de arbitraje sembrado, listo para interrogar."""
    from acopia.interfaces.demo_dia import sembrar_dia_demo

    demo = sembrar_dia_demo()
    optimizador_drl = None
    try:
        from acopia.infrastructure.drl.optimizador_drl import OptimizadorDRL

        optimizador_drl = OptimizadorDRL(total_timesteps=24_576)
    except ImportError:
        print("(comparar_modos sin DRL: instala acopia[drl])", file=sys.stderr)
    servidor = crear_servidor(
        demo.repositorio,
        demo.optimizador,
        demo.planta,
        demo.politica,
        optimizador_drl=optimizador_drl,
    )
    # A stderr: en transporte stdio, stdout es el canal JSON-RPC del MCP.
    print(f"Plan demo sembrado: plan_id={demo.plan_id}", file=sys.stderr)
    return servidor


if __name__ == "__main__":
    _demo().run()
