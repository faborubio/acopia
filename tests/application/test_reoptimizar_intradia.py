"""Tests de ReoptimizarIntradia (§6.2): recuperar ingreso ante desvíos del forecast.

La demo de la fase: un día planificado soleado se nubla a media mañana; el plan
obsoleto queda inejecutable en parte y pierde ingreso; reoptimizar desde el estado
real de la batería recupera lo que sí se puede capturar.
"""

from __future__ import annotations

import pytest

from acopia.application.reoptimizar_intradia import reoptimizar_intradia
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.observacion import Observacion
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
from acopia.domain.services.deteccion_desvio import hay_desvio
from acopia.domain.services.simulador_ejecucion import SimuladorEjecucion
from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.domain.value_objects.soc import Soc
from acopia.infrastructure.optimizacion.optimizador_lp import OptimizadorLP

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


def _planta() -> Planta:
    # Solo PV+BESS: no puede retirar de la red (retiro = 0).
    return Planta("planta-test", _bateria(), Potencia(10_000_000), Potencia(0))


def _politica(horizonte: int = 4) -> PoliticaDespacho:
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


def _escenario(puntos: list[tuple[int, int]]) -> Escenario:
    return Escenario(tuple(PuntoPronostico(Potencia(g), Precio(c)) for g, c in puntos))


# Forecast soleado con que se hizo el plan: PV barato en la mañana, tarde cara.
_FORECAST_SOLEADO = [(40_000, 10_000), (40_000, 10_000), (0, 500_000), (0, 500_000)]
# Realidad: a la hora 1 se nubla (PV 0). La tarde es como se esperaba.
_DIA_REAL = [(40_000, 10_000), (0, 10_000), (0, 500_000), (0, 500_000)]


def _plan_del_dia() -> PlanDespacho:
    return OptimizadorLP().optimizar(
        _planta(), EstadoBateria(Energia(0)), _escenario(_FORECAST_SOLEADO), _politica()
    )


def _tramo(plan: PlanDespacho, desde: int, hasta: int) -> PlanDespacho:
    return PlanDespacho(
        politica_id=plan.politica_id,
        politica_version=plan.politica_version,
        semilla=plan.semilla,
        acciones=plan.acciones[desde:hasta],
        energia_vertida_wh=plan.energia_vertida_wh[desde:hasta],
        ingreso_esperado_mills=0,
    )


def test_el_desvio_de_la_manana_gatilla_la_reoptimizacion() -> None:
    previsto = _escenario(_FORECAST_SOLEADO).puntos[:2]
    observado = tuple(
        Observacion(Potencia(g), Precio(c)) for g, c in _DIA_REAL[:2]
    )
    assert hay_desvio(previsto, observado, umbral_bp=2_000)  # 50 % de PV faltante


def test_reoptimizar_recupera_ingreso_frente_al_plan_obsoleto() -> None:
    plan = _plan_del_dia()
    simulador = SimuladorEjecucion()
    politica = _politica()

    # Se ejecuta la mañana real (la nube repara la carga de la hora 1).
    manana = simulador.ejecutar(
        _planta(), EstadoBateria(Energia(0)), _tramo(plan, 0, 2),
        _escenario(_DIA_REAL[:2]), politica,
    )
    estado_real = manana.estado_final
    assert estado_real.energia_almacenada.wh < 80_000  # hay menos energía que la planeada

    # Camino A: seguir con el plan obsoleto por la tarde.
    tarde_obsoleta = simulador.ejecutar(
        _planta(), estado_real, _tramo(plan, 2, 4), _escenario(_DIA_REAL[2:]), politica
    )
    # Camino B: reoptimizar el resto del día desde el estado real.
    resultado = reoptimizar_intradia(
        OptimizadorLP(), _planta(), estado_real,
        (_escenario(_DIA_REAL[2:]),), politica, intervalo_actual=2,
    )
    tarde_reoptimizada = simulador.ejecutar(
        _planta(), estado_real, resultado.plan_restante, _escenario(_DIA_REAL[2:]), politica
    )

    assert tarde_reoptimizada.ingreso_realizado_mills > tarde_obsoleta.ingreso_realizado_mills
    assert tarde_reoptimizada.acciones_reparadas == 0  # el plan nuevo es ejecutable


def test_conserva_id_y_version_de_la_politica() -> None:
    plan = _plan_del_dia()
    manana = SimuladorEjecucion().ejecutar(
        _planta(), EstadoBateria(Energia(0)), _tramo(plan, 0, 2),
        _escenario(_DIA_REAL[:2]), _politica(),
    )
    resultado = reoptimizar_intradia(
        OptimizadorLP(), _planta(), manana.estado_final,
        (_escenario(_DIA_REAL[2:]),), _politica(), intervalo_actual=2,
    )
    assert resultado.plan_restante.politica_id == "arbitraje"
    assert resultado.plan_restante.politica_version == 1
    assert resultado.intervalos_restantes == 2


def test_intervalo_fuera_de_rango_es_error() -> None:
    with pytest.raises(ValueError, match="intervalo_actual"):
        reoptimizar_intradia(
            OptimizadorLP(), _planta(), EstadoBateria(Energia(0)),
            (_escenario(_DIA_REAL),), _politica(), intervalo_actual=0,
        )
    with pytest.raises(ValueError, match="intervalo_actual"):
        reoptimizar_intradia(
            OptimizadorLP(), _planta(), EstadoBateria(Energia(0)),
            (_escenario(_DIA_REAL),), _politica(), intervalo_actual=4,
        )


def test_escenario_de_largo_incorrecto_es_error() -> None:
    with pytest.raises(ValueError, match="quedan 2 intervalos"):
        reoptimizar_intradia(
            OptimizadorLP(), _planta(), EstadoBateria(Energia(0)),
            (_escenario(_DIA_REAL),), _politica(), intervalo_actual=2,
        )
