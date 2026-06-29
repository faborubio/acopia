"""Tests de integración de la Fase 1: optimizador LP real + caso de uso PlanificarDespacho.

Demuestra el entregable de la fase: "dado un forecast, genero un plan factible y
rentable". Cubre sentido económico (arbitraje), factibilidad, determinismo,
ingreso auditable y persistencia con rastro.
"""

from __future__ import annotations

from acopia.application.planificar_despacho import PlanificarDespacho
from acopia.domain.entities.accion_despacho import TipoAccion
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
from acopia.domain.services.modelo_bateria import ModeloBateria
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


def _bateria() -> Bateria:
    """100 kWh, 50 kW, 100 % (cuentas limpias), SoC 0-100 %."""
    return Bateria(
        capacidad=Energia(100_000),
        potencia_max_carga=Potencia(50_000),
        potencia_max_descarga=Potencia(50_000),
        eficiencia_carga=Eficiencia.de_porcentaje(100),
        eficiencia_descarga=Eficiencia.de_porcentaje(100),
        soc_min=Soc.de_porcentaje(0),
        soc_max=Soc.de_porcentaje(100),
        throughput_garantia=Energia(10_000_000),
    )


def _politica(horizonte: int, costo_ciclado: int = 0) -> PoliticaDespacho:
    return PoliticaDespacho(
        id="arbitraje",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=horizonte,
        resolucion=UNA_HORA,
        semilla=42,
        modo=Modo.PREDICT_THEN_OPTIMIZE,
        costo_ciclado_mills_por_mwh=costo_ciclado,
    )


def _escenario_arbitraje() -> Escenario:
    """CMg bajo (mediodía) y luego alto (tarde); sin generación, arbitraje puro de red."""
    return Escenario(
        (
            PuntoPronostico(Potencia(0), Precio(10_000)),
            PuntoPronostico(Potencia(0), Precio(10_000)),
            PuntoPronostico(Potencia(0), Precio(500_000)),
            PuntoPronostico(Potencia(0), Precio(500_000)),
        )
    )


def _plan_es_factible(bateria: Bateria, estado: EstadoBateria, plan: PlanDespacho) -> bool:
    modelo = ModeloBateria()
    actual = estado
    for accion in plan.acciones:
        if not modelo.es_factible(bateria, actual, accion, UNA_HORA):
            return False
        actual = modelo.aplicar(bateria, actual, accion, UNA_HORA)
    return True


def test_arbitraje_carga_barato_y_descarga_caro() -> None:
    optimizador = OptimizadorLP()
    bateria = _bateria()
    estado = EstadoBateria(Energia(0))
    plan = optimizador.optimizar(bateria, estado, _escenario_arbitraje(), _politica(4))

    tipos = [a.tipo for a in plan.acciones]
    assert tipos[:2] == [TipoAccion.CARGAR, TipoAccion.CARGAR]
    assert tipos[2:] == [TipoAccion.DESCARGAR, TipoAccion.DESCARGAR]
    # Ingreso: -(50k*10k + 50k*10k)/1e6 + (50k*500k + 50k*500k)/1e6 = -1000 + 50000
    assert plan.ingreso_esperado_mills == 49_000


def test_plan_generado_es_factible() -> None:
    optimizador = OptimizadorLP()
    bateria = _bateria()
    estado = EstadoBateria(Energia(0))
    plan = optimizador.optimizar(bateria, estado, _escenario_arbitraje(), _politica(4))
    assert _plan_es_factible(bateria, estado, plan)


def test_determinismo_mismo_plan() -> None:
    optimizador = OptimizadorLP()
    bateria = _bateria()
    estado = EstadoBateria(Energia(0))
    escenario = _escenario_arbitraje()
    plan_a = optimizador.optimizar(bateria, estado, escenario, _politica(4))
    plan_b = optimizador.optimizar(bateria, estado, escenario, _politica(4))
    assert plan_a == plan_b


def test_precios_planos_nunca_cargan() -> None:
    # Con CMg constante no hay diferencial que arbitrar: comprar para revender al mismo
    # precio (menos eficiencia) nunca conviene, así que el plan no carga.
    # (Sí puede descargar energía existente: el modelo aún no valoriza el SoC terminal;
    # ver deuda "efecto fin de horizonte" en docs/AUDIT.md.)
    optimizador = OptimizadorLP()
    bateria = _bateria()
    estado = EstadoBateria(Energia(50_000))
    escenario = Escenario(tuple(PuntoPronostico(Potencia(0), Precio(100_000)) for _ in range(4)))
    plan = optimizador.optimizar(bateria, estado, escenario, _politica(4))
    assert all(a.tipo is not TipoAccion.CARGAR for a in plan.acciones)
    assert plan.ingreso_esperado_mills >= 0


def test_caso_de_uso_persiste_plan_con_rastro() -> None:
    repositorio = RepositorioPlanesEnMemoria()
    caso = PlanificarDespacho(OptimizadorLP(), repositorio)
    bateria = _bateria()
    estado = EstadoBateria(Energia(0))
    escenario = _escenario_arbitraje()

    resultado = caso.ejecutar(bateria, estado, escenario, _politica(4))

    plan_guardado, rastro = repositorio.obtener(resultado.plan_id)
    assert plan_guardado == resultado.plan
    assert rastro.estado_inicial == estado
    assert rastro.escenarios == (escenario,)
    assert rastro.semilla == 42
