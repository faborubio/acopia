"""Tests del servidor MCP: las tres herramientas del SAD, end-to-end in-memory."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

pytest.importorskip("fastmcp")
from fastmcp import Client

from acopia.application.planificar_despacho import PlanificarDespacho
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import (
    Modo,
    Objetivo,
    PoliticaDespacho,
)
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
from acopia.interfaces.mcp.servidor import crear_servidor

UNA_HORA = Intervalo.de_minutos(60)


def _armar_servidor() -> tuple[Any, str]:
    bateria = Bateria(
        capacidad=Energia(100_000),
        potencia_max_carga=Potencia(50_000),
        potencia_max_descarga=Potencia(50_000),
        eficiencia_carga=Eficiencia.de_porcentaje(100),
        eficiencia_descarga=Eficiencia.de_porcentaje(100),
        soc_min=Soc.de_porcentaje(0),
        soc_max=Soc.de_porcentaje(100),
        throughput_garantia=Energia(10_000_000),
    )
    planta = Planta("planta-test", bateria, Potencia(10_000_000), Potencia(10_000_000))
    politica = PoliticaDespacho(
        id="arbitraje",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=4,
        resolucion=UNA_HORA,
        semilla=42,
        modo=Modo.PREDICT_THEN_OPTIMIZE,
    )
    escenario = Escenario(
        (
            PuntoPronostico(Potencia(30_000), Precio(10_000)),
            PuntoPronostico(Potencia(30_000), Precio(20_000)),
            PuntoPronostico(Potencia(0), Precio(400_000)),
            PuntoPronostico(Potencia(0), Precio(500_000)),
        )
    )
    repositorio = RepositorioPlanesEnMemoria()
    optimizador = OptimizadorLP()
    resultado = PlanificarDespacho(optimizador, repositorio).ejecutar(
        planta, EstadoBateria(Energia(0)), escenario, politica
    )
    servidor = crear_servidor(repositorio, optimizador, planta, politica)
    return servidor, resultado.plan_id


def _llamar(servidor: Any, herramienta: str, argumentos: dict[str, Any]) -> Any:
    async def _ir() -> Any:
        async with Client(servidor) as cliente:
            return await cliente.call_tool(herramienta, argumentos)

    return asyncio.run(_ir())


def test_expone_las_tres_herramientas_del_sad() -> None:
    servidor, _ = _armar_servidor()

    async def _ir() -> list[str]:
        async with Client(servidor) as cliente:
            return [t.name for t in await cliente.list_tools()]

    nombres = asyncio.run(_ir())
    assert set(nombres) == {"consultar_despacho", "explicar_despacho", "simular"}


def test_consultar_despacho_resume_el_plan() -> None:
    servidor, plan_id = _armar_servidor()
    resultado = _llamar(servidor, "consultar_despacho", {"plan_id": plan_id})
    datos = resultado.data
    assert datos["plan_id"] == plan_id
    assert datos["ingreso_esperado_mills"] > 0
    assert len(datos["acciones"]) == 4


def test_explicar_despacho_responde_por_que_cargo() -> None:
    servidor, plan_id = _armar_servidor()
    resultado = _llamar(servidor, "explicar_despacho", {"plan_id": plan_id, "intervalo": 0})
    (explicacion,) = resultado.data
    assert explicacion["accion"] == "CARGAR"  # hora barata con PV
    assert "más baratos" in explicacion["motivo"]


def test_simular_cmg_cero_en_la_punta() -> None:
    servidor, plan_id = _armar_servidor()
    resultado = _llamar(
        servidor,
        "simular",
        {"plan_id": plan_id, "cmg_por_intervalo": {"2": 0, "3": 0}},
    )
    datos = resultado.data
    assert datos["delta_ingreso_mills"] < 0  # sin punta cara, el arbitraje pierde
    # y la simulación no tocó el plan original
    consulta = _llamar(servidor, "consultar_despacho", {"plan_id": plan_id})
    assert consulta.data["plan_id"] == plan_id
