"""Tests de SimularEscenario: reevaluar el despacho sin efectos (capa MCP)."""

from __future__ import annotations

import pytest

from acopia.application.planificar_despacho import PlanificarDespacho
from acopia.application.simular_escenario import simular_escenario
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
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

UNA_HORA = Intervalo.de_minutos(60)


def _planta() -> Planta:
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
    return Planta("planta-test", bateria, Potencia(10_000_000), Potencia(10_000_000))


def _politica() -> PoliticaDespacho:
    return PoliticaDespacho(
        id="arbitraje",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=4,
        resolucion=UNA_HORA,
        semilla=42,
        modo=Modo.PREDICT_THEN_OPTIMIZE,
    )


def _escenario() -> Escenario:
    return Escenario(
        (
            PuntoPronostico(Potencia(30_000), Precio(10_000)),
            PuntoPronostico(Potencia(30_000), Precio(20_000)),
            PuntoPronostico(Potencia(0), Precio(400_000)),
            PuntoPronostico(Potencia(0), Precio(500_000)),
        )
    )


def _plan_persistido() -> tuple[str, RepositorioPlanesEnMemoria]:
    repositorio = RepositorioPlanesEnMemoria()
    resultado = PlanificarDespacho(OptimizadorLP(), repositorio).ejecutar(
        _planta(), EstadoBateria(Energia(0)), _escenario(), _politica()
    )
    return resultado.plan_id, repositorio


def test_simular_no_persiste_nada() -> None:
    plan_id, repositorio = _plan_persistido()
    plan, rastro = repositorio.obtener(plan_id)
    simular_escenario(
        OptimizadorLP(), _planta(), plan, rastro, _politica(), cmg_por_intervalo={3: 0}
    )
    # el repositorio sigue con un único plan, intacto
    assert repositorio.obtener(plan_id)[0] == plan


def test_cmg_colapsado_reduce_el_ingreso() -> None:
    # "Simulá un día con CMg cero en la punta": el arbitraje pierde su venta cara.
    plan_id, repositorio = _plan_persistido()
    plan, rastro = repositorio.obtener(plan_id)
    resultado = simular_escenario(
        OptimizadorLP(), _planta(), plan, rastro, _politica(),
        cmg_por_intervalo={2: 0, 3: 0},
    )
    assert resultado.ingreso_simulado_mills < resultado.ingreso_original_mills
    assert resultado.delta_ingreso_mills < 0


def test_dia_nublado_reduce_el_ingreso() -> None:
    plan_id, repositorio = _plan_persistido()
    plan, rastro = repositorio.obtener(plan_id)
    resultado = simular_escenario(
        OptimizadorLP(), _planta(), plan, rastro, _politica(), factor_generacion_bp=0
    )
    assert all(p.generacion.w == 0 for p in resultado.escenario_simulado.puntos)
    assert resultado.ingreso_simulado_mills < resultado.ingreso_original_mills


def test_intervalo_fuera_de_rango_es_error() -> None:
    plan_id, repositorio = _plan_persistido()
    plan, rastro = repositorio.obtener(plan_id)
    with pytest.raises(ValueError, match="fuera del horizonte"):
        simular_escenario(
            OptimizadorLP(), _planta(), plan, rastro, _politica(),
            cmg_por_intervalo={7: 0},
        )


def test_factor_negativo_es_error() -> None:
    plan_id, repositorio = _plan_persistido()
    plan, rastro = repositorio.obtener(plan_id)
    with pytest.raises(ValueError, match="factor"):
        simular_escenario(
            OptimizadorLP(), _planta(), plan, rastro, _politica(),
            factor_generacion_bp=-1,
        )
