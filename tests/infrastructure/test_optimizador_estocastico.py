"""Tests del optimizador estocástico de dos etapas (ADR-004, Fase 3).

La decisión here-and-now (programa de la batería) es común a todos los escenarios;
el vertido es el recurso por escenario. El plan debe ser factible en *todos* los
escenarios y maximizar el ingreso esperado ponderado por ``probabilidad_bp``.
"""

from __future__ import annotations

import pytest

from acopia.domain.entities.accion_despacho import TipoAccion
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
from acopia.domain.services.funcion_objetivo import FuncionObjetivo
from acopia.domain.services.modelo_bateria import ModeloBateria
from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.domain.value_objects.soc import Soc
from acopia.infrastructure.optimizacion.optimizador_lp import OptimizadorLP

UNA_HORA = Intervalo.de_minutos(60)


def _bateria() -> Bateria:
    """100 kWh, 50 kW, eficiencia 100 % (cuentas limpias), SoC 0-100 %."""
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


def _planta(retiro_w: int = 10_000_000) -> Planta:
    return Planta("planta-test", _bateria(), Potencia(10_000_000), Potencia(retiro_w))


def _politica(horizonte: int) -> PoliticaDespacho:
    return PoliticaDespacho(
        id="arbitraje",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=horizonte,
        resolucion=UNA_HORA,
        semilla=42,
        modo=Modo.PREDICT_THEN_OPTIMIZE,
        costo_ciclado_mills_por_mwh=0,
    )


def _escenario(puntos: list[tuple[int, int]], probabilidad_bp: int = 10_000) -> Escenario:
    return Escenario(
        tuple(PuntoPronostico(Potencia(g), Precio(c)) for g, c in puntos), probabilidad_bp
    )


def test_un_escenario_equivale_al_modo_deterministico() -> None:
    optimizador = OptimizadorLP()
    escenario = _escenario([(0, 10_000), (0, 10_000), (0, 500_000), (0, 500_000)])
    estado = EstadoBateria(Energia(0))

    plan_det = optimizador.optimizar(_planta(), estado, escenario, _politica(4))
    plan_sto = optimizador.optimizar_escenarios(_planta(), estado, (escenario,), _politica(4))
    assert plan_det == plan_sto


def test_es_determinista() -> None:
    optimizador = OptimizadorLP()
    escenarios = (
        _escenario([(0, 10_000), (0, 400_000)], 5_000),
        _escenario([(0, 30_000), (0, 600_000)], 5_000),
    )
    estado = EstadoBateria(Energia(0))
    a = optimizador.optimizar_escenarios(_planta(), estado, escenarios, _politica(2))
    b = optimizador.optimizar_escenarios(_planta(), estado, escenarios, _politica(2))
    assert a == b


def test_plan_factible_para_la_bateria() -> None:
    optimizador = OptimizadorLP()
    escenarios = (
        _escenario([(20_000, 10_000), (0, 300_000), (10_000, 80_000), (0, 500_000)], 5_000),
        _escenario([(5_000, 20_000), (0, 250_000), (2_000, 90_000), (0, 450_000)], 5_000),
    )
    estado = EstadoBateria(Energia(0))
    plan = optimizador.optimizar_escenarios(_planta(), estado, escenarios, _politica(4))

    modelo = ModeloBateria()
    actual = estado
    for accion in plan.acciones:
        assert modelo.es_factible(_bateria(), actual, accion, UNA_HORA)
        actual = modelo.aplicar(_bateria(), actual, accion, UNA_HORA)


def test_robustez_no_carga_pv_que_puede_no_existir() -> None:
    # ADR-004: planta que NO puede retirar de la red (retiro_max = 0). En el caso
    # medio hay PV barato en la hora 0 y conviene cargar; pero en el escenario
    # pesimista (nublado) la generación es 0 y esa carga sería inejecutable.
    # El plan estocástico debe respetar el peor escenario: no cargar en la hora 0.
    optimizador = OptimizadorLP()
    politica = _politica(2)
    estado = EstadoBateria(Energia(0))
    planta = _planta(retiro_w=0)

    optimista = _escenario([(40_000, 10_000), (0, 500_000)], 5_000)
    pesimista = _escenario([(0, 10_000), (0, 500_000)], 5_000)
    caso_medio = _escenario([(20_000, 10_000), (0, 500_000)])

    plan_medio = optimizador.optimizar(planta, estado, caso_medio, politica)
    assert plan_medio.acciones[0].tipo is TipoAccion.CARGAR  # el caso medio sí cargaría

    plan_robusto = optimizador.optimizar_escenarios(
        planta, estado, (optimista, pesimista), politica
    )
    assert plan_robusto.acciones[0].tipo is TipoAccion.RETENER  # respeta el pesimista


def test_ingreso_esperado_es_promedio_ponderado() -> None:
    # Sin batería útil (sin diferencial aprovechable): el ingreso es solo la venta
    # del PV de cada escenario, y el esperado debe ser el promedio ponderado exacto.
    optimizador = OptimizadorLP()
    politica = _politica(1)
    estado = EstadoBateria(Energia(0))
    alto = _escenario([(10_000, 100_000)], 7_500)  # 10 kWh a 100 mills/kWh... en bp 75%
    bajo = _escenario([(2_000, 100_000)], 2_500)

    plan = optimizador.optimizar_escenarios(_planta(), estado, (alto, bajo), politica)

    objetivo = FuncionObjetivo()
    ingreso_alto = objetivo.ingreso_bruto(plan, alto, UNA_HORA)
    ingreso_bajo = objetivo.ingreso_bruto(plan, bajo, UNA_HORA)
    # pesos 0.75 / 0.25 en aritmética entera
    esperado = (7_500 * ingreso_alto + 2_500 * ingreso_bajo) // 10_000
    assert plan.ingreso_esperado_mills == esperado


def test_sin_escenarios_es_error() -> None:
    optimizador = OptimizadorLP()
    with pytest.raises(ValueError, match="al menos un escenario"):
        optimizador.optimizar_escenarios(
            _planta(), EstadoBateria(Energia(0)), (), _politica(2)
        )


def test_largos_distintos_es_error() -> None:
    optimizador = OptimizadorLP()
    escenarios = (
        _escenario([(0, 10_000), (0, 20_000)]),
        _escenario([(0, 10_000)]),
    )
    with pytest.raises(ValueError, match="escenario 1"):
        optimizador.optimizar_escenarios(
            _planta(), EstadoBateria(Energia(0)), escenarios, _politica(2)
        )