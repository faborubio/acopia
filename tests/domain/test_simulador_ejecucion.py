"""Tests del SimuladorEjecucion: confrontar un plan con el día real (§6.3)."""

from __future__ import annotations

import pytest

from acopia.domain.entities.accion_despacho import AccionDespacho, TipoAccion
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
from acopia.domain.services.simulador_ejecucion import SimuladorEjecucion
from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.domain.value_objects.soc import Soc

UNA_HORA = Intervalo.de_minutos(60)


def _bateria() -> Bateria:
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


def _planta(iny_w: int = 10_000_000, retiro_w: int = 10_000_000) -> Planta:
    return Planta("planta-test", _bateria(), Potencia(iny_w), Potencia(retiro_w))


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


def _plan(acciones: list[AccionDespacho], vertidos: list[int] | None = None) -> PlanDespacho:
    return PlanDespacho(
        politica_id="arbitraje",
        politica_version=1,
        semilla=42,
        acciones=tuple(acciones),
        energia_vertida_wh=tuple(vertidos or [0] * len(acciones)),
        ingreso_esperado_mills=0,
    )


def _real(puntos: list[tuple[int, int]]) -> Escenario:
    return Escenario(tuple(PuntoPronostico(Potencia(g), Precio(c)) for g, c in puntos))


def test_plan_ejecutable_se_ejecuta_tal_cual() -> None:
    # Cargar 10 kWh del PV real (20 kWh disponibles) y venderlos caro después.
    plan = _plan(
        [AccionDespacho.cargar(Potencia(10_000)), AccionDespacho.descargar(Potencia(10_000))]
    )
    real = _real([(20_000, 10_000), (0, 500_000)])

    resultado = SimuladorEjecucion().ejecutar(
        _planta(), EstadoBateria(Energia(0)), plan, real, _politica(2)
    )
    assert resultado.acciones_realizadas == plan.acciones
    assert resultado.acciones_reparadas == 0
    # hora 0: inyecta 20k-10k=10k Wh a 10k mills/MWh = 100; hora 1: 10k Wh a 500k = 5000
    assert resultado.ingreso_realizado_mills == 100 + 5_000


def test_carga_sin_pv_real_se_repara_a_retener() -> None:
    # El plan (hecho con un forecast optimista) carga 10 kWh, pero el día real no
    # tiene PV y la planta no puede retirar de la red: inejecutable -> RETENER.
    plan = _plan([AccionDespacho.cargar(Potencia(10_000))])
    real = _real([(0, 10_000)])

    resultado = SimuladorEjecucion().ejecutar(
        _planta(retiro_w=0), EstadoBateria(Energia(0)), plan, real, _politica(1)
    )
    assert resultado.acciones_realizadas[0].tipo is TipoAccion.RETENER
    assert resultado.acciones_reparadas == 1
    assert resultado.estado_final.energia_almacenada.wh == 0


def test_vertido_obligatorio_cuando_el_pv_real_excede_el_techo() -> None:
    # PV real de 30 kWh con techo de inyección de 20 kWh y batería quieta:
    # 10 kWh se vierten aunque el plan no lo contemplara.
    plan = _plan([AccionDespacho.retener()])
    real = _real([(30_000, 100_000)])

    resultado = SimuladorEjecucion().ejecutar(
        _planta(iny_w=20_000), EstadoBateria(Energia(0)), plan, real, _politica(1)
    )
    assert resultado.energia_vertida_wh == (10_000,)
    # se inyectan 20 kWh a 100k mills/MWh = 2000 mills
    assert resultado.ingreso_realizado_mills == 2_000


def test_descarga_infactible_para_la_bateria_se_repara() -> None:
    # Descargar con la batería vacía es infactible: repair a RETENER.
    plan = _plan([AccionDespacho.descargar(Potencia(10_000))])
    real = _real([(0, 500_000)])

    resultado = SimuladorEjecucion().ejecutar(
        _planta(), EstadoBateria(Energia(0)), plan, real, _politica(1)
    )
    assert resultado.acciones_realizadas[0].tipo is TipoAccion.RETENER
    assert resultado.acciones_reparadas == 1


def test_largos_distintos_es_error() -> None:
    plan = _plan([AccionDespacho.retener()])
    real = _real([(0, 1), (0, 1)])
    with pytest.raises(ValueError, match="escenario real"):
        SimuladorEjecucion().ejecutar(
            _planta(), EstadoBateria(Energia(0)), plan, real, _politica(1)
        )
