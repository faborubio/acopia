"""Tests del OptimizadorDRL (PPO): factibilidad, determinismo y honestidad vs el LP.

La postura de ADR-005 se fija por test: el LP es el óptimo del problema
determinista, así que el DRL puede a lo sumo empatarlo — nunca superarlo. Con un
presupuesto de entrenamiento mínimo (los tests deben ser rápidos) NO se exige que
el DRL arbitre bien; se exige que su plan sea **factible, determinista y valorizado
con la misma vara** que el baseline.
"""

from __future__ import annotations

import pytest

pytest.importorskip("stable_baselines3")
pytest.importorskip("gymnasium")

from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
from acopia.domain.entities.producto_sscc import ReservaFrecuencia
from acopia.domain.services.funcion_objetivo import FuncionObjetivo
from acopia.domain.services.modelo_bateria import ModeloBateria
from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.domain.value_objects.soc import Soc
from acopia.infrastructure.drl.entorno_despacho import vertido_recurso
from acopia.infrastructure.drl.optimizador_drl import OptimizadorDRL
from acopia.infrastructure.optimizacion.optimizador_lp import OptimizadorLP

UNA_HORA = Intervalo.de_minutos(60)


def _planta() -> Planta:
    bateria = Bateria(
        capacidad=Energia(10_000),
        potencia_max_carga=Potencia(5_000),
        potencia_max_descarga=Potencia(5_000),
        eficiencia_carga=Eficiencia.de_porcentaje(100),
        eficiencia_descarga=Eficiencia.de_porcentaje(100),
        soc_min=Soc.de_porcentaje(0),
        soc_max=Soc.de_porcentaje(100),
        throughput_garantia=Energia(1_000_000),
    )
    return Planta("planta-drl", bateria, Potencia(20_000), Potencia(20_000))


def _politica(semilla: int = 7) -> PoliticaDespacho:
    return PoliticaDespacho(
        id="drl-test",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=4,
        resolucion=UNA_HORA,
        semilla=semilla,
        modo=Modo.DRL,
    )


def _escenario_arbitraje() -> Escenario:
    """Dos horas baratas con PV, dos caras sin PV: el arbitraje evidente."""
    return Escenario(
        (
            PuntoPronostico(Potencia(3_000), Precio(10_000)),
            PuntoPronostico(Potencia(3_000), Precio(10_000)),
            PuntoPronostico(Potencia(0), Precio(300_000)),
            PuntoPronostico(Potencia(0), Precio(300_000)),
        )
    )


def _optimizador_rapido() -> OptimizadorDRL:
    return OptimizadorDRL(total_timesteps=512, n_steps=64, batch_size=64)


def test_plan_factible_para_la_bateria() -> None:
    plan = _optimizador_rapido().optimizar(
        _planta(), EstadoBateria(Energia(0)), _escenario_arbitraje(), _politica()
    )
    modelo = ModeloBateria()
    estado = EstadoBateria(Energia(0))
    for accion in plan.acciones:  # replay: ninguna acción viola la física
        estado = modelo.aplicar(_planta().bateria, estado, accion, UNA_HORA)
    assert len(plan) == 4
    assert all(v >= 0 for v in plan.energia_vertida_wh)
    assert plan.reserva_w == ()


def test_es_determinista_con_la_misma_semilla() -> None:
    a = _optimizador_rapido().optimizar(
        _planta(), EstadoBateria(Energia(0)), _escenario_arbitraje(), _politica(semilla=3)
    )
    b = _optimizador_rapido().optimizar(
        _planta(), EstadoBateria(Energia(0)), _escenario_arbitraje(), _politica(semilla=3)
    )
    assert a.acciones == b.acciones
    assert a.ingreso_esperado_mills == b.ingreso_esperado_mills


def test_no_supera_al_optimo_deterministico() -> None:
    """La foto de ADR-005: el LP es el óptimo; el DRL a lo sumo lo empata."""
    planta, escenario = _planta(), _escenario_arbitraje()
    politica = _politica()
    plan_drl = _optimizador_rapido().optimizar(
        planta, EstadoBateria(Energia(0)), escenario, politica
    )
    plan_lp = OptimizadorLP().optimizar(planta, EstadoBateria(Energia(0)), escenario, politica)
    assert plan_drl.ingreso_esperado_mills <= plan_lp.ingreso_esperado_mills


def test_ingreso_reportado_es_el_de_la_funcion_objetivo() -> None:
    """El ingreso del plan DRL es auditable: lo reproduce la FuncionObjetivo del dominio."""
    planta, escenario, politica = _planta(), _escenario_arbitraje(), _politica()
    plan = _optimizador_rapido().optimizar(planta, EstadoBateria(Energia(0)), escenario, politica)
    objetivo = FuncionObjetivo()
    esperado = objetivo.ingreso_bruto(plan, escenario, UNA_HORA) - objetivo.costo_ciclado(
        plan, politica, planta.bateria.eficiencia_carga, planta.bateria.eficiencia_descarga
    )
    assert plan.ingreso_esperado_mills == esperado


def test_reserva_sscc_no_soportada() -> None:
    politica = PoliticaDespacho(
        id="drl-sscc",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=4,
        resolucion=UNA_HORA,
        semilla=1,
        modo=Modo.DRL,
        reserva=ReservaFrecuencia(banda_max_w=1_000, precio_disponibilidad_mills_por_mwh=50_000),
    )
    with pytest.raises(ValueError, match="SSCC"):
        _optimizador_rapido().optimizar(
            _planta(), EstadoBateria(Energia(0)), _escenario_arbitraje(), politica
        )


def test_estado_inicial_fuera_de_banda_es_error() -> None:
    with pytest.raises(ValueError, match="fuera de la banda"):
        _optimizador_rapido().optimizar(
            _planta(), EstadoBateria(Energia(50_000)), _escenario_arbitraje(), _politica()
        )


def test_vertido_recurso_cmg_positivo_es_el_obligatorio() -> None:
    # gen 100, sin batería, techo 60: se vierten 40 obligatorios
    assert vertido_recurso(100, 0, 0, 60, 0, 50_000) == 40
    # cabe todo: no se vierte
    assert vertido_recurso(100, 0, 0, 200, 0, 50_000) == 0


def test_vertido_recurso_cmg_negativo_vierte_lo_maximo() -> None:
    # CMg negativo: inyectar paga; se vierte todo el PV que las reglas permitan
    assert vertido_recurso(100, 0, 0, 200, 0, -1_000) == 100
    # cargando 30, verter 100 dejaría inyectado = -30 < -retiro(0): se vierte 70
    assert vertido_recurso(100, 30, 0, 200, 0, -1_000) == 70
