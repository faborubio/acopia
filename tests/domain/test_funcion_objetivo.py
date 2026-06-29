"""Tests de la FuncionObjetivo: ingreso bruto y costo de ciclado, con aritmética entera."""

from __future__ import annotations

from acopia.domain.entities.accion_despacho import AccionDespacho
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
from acopia.domain.services.funcion_objetivo import FuncionObjetivo
from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio

UNA_HORA = Intervalo.de_minutos(60)


def _plan(*acciones: AccionDespacho, vertido: tuple[int, ...] | None = None) -> PlanDespacho:
    vertidos = vertido if vertido is not None else tuple(0 for _ in acciones)
    return PlanDespacho("p", 1, 0, acciones, vertidos, ingreso_esperado_mills=0)


def test_ingreso_bruto_descuenta_carga_y_suma_descarga() -> None:
    objetivo = FuncionObjetivo()
    escenario = Escenario(
        (
            PuntoPronostico(Potencia(0), Precio(50_000)),   # carga: retiro a 50.000
            PuntoPronostico(Potencia(0), Precio(200_000)),  # descarga: inyección a 200.000
        )
    )
    plan = _plan(
        AccionDespacho.cargar(Potencia(100_000)),    # 100 kWh a la red (retiro)
        AccionDespacho.descargar(Potencia(90_000)),  # 90 kWh inyectados
    )
    # mills = -100000*50000/1e6 + 90000*200000/1e6 = -5000 + 18000 = 13000
    assert objetivo.ingreso_bruto(plan, escenario, UNA_HORA) == 13_000


def test_generacion_se_valoriza_al_cmg() -> None:
    objetivo = FuncionObjetivo()
    escenario = Escenario((PuntoPronostico(Potencia(40_000), Precio(100_000)),))
    plan = _plan(AccionDespacho.retener())
    # 40 kWh * 100.000 / 1e6 = 4.000 mills
    assert objetivo.ingreso_bruto(plan, escenario, UNA_HORA) == 4_000


def test_vertimiento_reduce_la_inyeccion() -> None:
    objetivo = FuncionObjetivo()
    escenario = Escenario((PuntoPronostico(Potencia(100_000), Precio(100_000)),))
    plan = _plan(AccionDespacho.retener(), vertido=(40_000,))
    # inyectado = 100k - 40k = 60k ; 60k * 100.000 / 1e6 = 6.000 mills
    assert objetivo.ingreso_bruto(plan, escenario, UNA_HORA) == 6_000


def test_costo_ciclado_penaliza_throughput_de_celdas() -> None:
    objetivo = FuncionObjetivo()
    politica = PoliticaDespacho(
        id="p",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=1,
        resolucion=UNA_HORA,
        semilla=0,
        modo=Modo.PREDICT_THEN_OPTIMIZE,
        costo_ciclado_mills_por_mwh=10_000,
    )
    plan = _plan(AccionDespacho.cargar(Potencia(100_000)))  # 100 kWh AC
    ef = Eficiencia.de_porcentaje(100)
    # celdas = 100.000 Wh; costo = 10.000 * 100.000 / 1e6 = 1.000 mills
    assert objetivo.costo_ciclado(plan, politica, ef, ef) == 1_000
