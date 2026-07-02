"""Tests de la co-optimización arbitraje + SSCC (§3.0, Fase 4).

La reserva de frecuencia (banda simétrica, pago por disponibilidad) compite con el
arbitraje por la misma potencia y energía de la batería, en una sola función objetivo.
"""

from __future__ import annotations

from acopia.domain.entities.accion_despacho import TipoAccion
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
from acopia.domain.entities.producto_sscc import ReservaFrecuencia
from acopia.domain.services.funcion_objetivo import FuncionObjetivo
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


def _planta(retiro_w: int = 10_000_000) -> Planta:
    return Planta("planta-test", _bateria(), Potencia(10_000_000), Potencia(retiro_w))


def _politica(
    horizonte: int,
    reserva: ReservaFrecuencia | None = None,
    costo_ciclado: int = 0,
    precio_final: int | None = None,
) -> PoliticaDespacho:
    return PoliticaDespacho(
        id="cooptimizacion",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=horizonte,
        resolucion=UNA_HORA,
        semilla=42,
        modo=Modo.PREDICT_THEN_OPTIMIZE,
        costo_ciclado_mills_por_mwh=costo_ciclado,
        precio_energia_final_mills_por_mwh=precio_final,
        reserva=reserva,
    )


def _escenario_plano(horizonte: int, precio: int = 50_000) -> Escenario:
    return Escenario(
        tuple(PuntoPronostico(Potencia(0), Precio(precio)) for _ in range(horizonte))
    )


def _escenario_arbitraje() -> Escenario:
    return Escenario(
        (
            PuntoPronostico(Potencia(0), Precio(10_000)),
            PuntoPronostico(Potencia(0), Precio(10_000)),
            PuntoPronostico(Potencia(0), Precio(500_000)),
            PuntoPronostico(Potencia(0), Precio(500_000)),
        )
    )


def test_sin_sscc_el_plan_no_compromete_banda() -> None:
    plan = OptimizadorLP().optimizar(
        _planta(), EstadoBateria(Energia(0)), _escenario_arbitraje(), _politica(4)
    )
    assert plan.reserva_w == ()


def test_reserva_pura_compromete_la_banda_maxima_disponible() -> None:
    # Sin diferencial de precios (nada que arbitrar) y buena remuneración: la batería
    # a media carga ofrece toda la banda que la potencia y la energía permiten.
    # Valor terminal == spot (neutraliza liquidar) + ciclado > 0 (moverse cuesta):
    # quedarse quieto con la banda al máximo es el óptimo, sin degeneración.
    reserva = ReservaFrecuencia(
        precio_disponibilidad_mills_por_mwh=100_000, banda_max_w=40_000
    )
    plan = OptimizadorLP().optimizar(
        _planta(), EstadoBateria(Energia(50_000)), _escenario_plano(2),
        _politica(2, reserva, costo_ciclado=1_000, precio_final=50_000),
    )
    assert plan.reserva_w == (40_000, 40_000)  # limitada por banda_max, no la batería
    assert all(a.tipo is TipoAccion.RETENER for a in plan.acciones)


def test_sin_retiro_la_banda_exige_estar_inyectando() -> None:
    # Física de la banda simétrica en una planta que NO puede retirar de la red:
    # absorber la activación a bajar exige estar inyectando al menos R (R <= d), y
    # sostener la activación a subir exige energía (R <= e0 - d). Con 10 kWh el
    # óptimo es el reparto d = R = 5 kW: vende la mitad para poder respaldar la otra.
    reserva = ReservaFrecuencia(
        precio_disponibilidad_mills_por_mwh=100_000, banda_max_w=40_000
    )
    plan = OptimizadorLP().optimizar(
        _planta(retiro_w=0), EstadoBateria(Energia(10_000)), _escenario_plano(1),
        _politica(1, reserva),
    )
    assert plan.acciones[0].tipo is TipoAccion.DESCARGAR
    assert plan.acciones[0].potencia.w == 5_000
    assert plan.reserva_w == (5_000,)


def test_comprar_energia_para_vender_disponibilidad() -> None:
    # Descubierto por el propio LP: si la banda paga mucho más que el spot, conviene
    # CARGAR de la red (comprar barato) para respaldar más banda. Arbitraje entre
    # productos — la co-optimización de §3.0 funcionando.
    reserva = ReservaFrecuencia(
        precio_disponibilidad_mills_por_mwh=100_000, banda_max_w=40_000
    )
    plan = OptimizadorLP().optimizar(
        _planta(), EstadoBateria(Energia(10_000)), _escenario_plano(1),
        _politica(1, reserva),
    )
    assert plan.acciones[0].tipo is TipoAccion.CARGAR  # compra para respaldar banda
    assert plan.reserva_w[0] > 10_000  # la banda supera lo que la energía inicial daba


def test_la_banda_compite_con_el_arbitraje() -> None:
    # Con reserva cara, el optimizador sacrifica arbitraje para mantener headroom:
    # el ingreso total sube vs arbitraje puro, y la descarga ya no usa toda la potencia.
    politica_sin = _politica(4)
    reserva = ReservaFrecuencia(
        precio_disponibilidad_mills_por_mwh=400_000, banda_max_w=50_000
    )
    politica_con = _politica(4, reserva)
    estado = EstadoBateria(Energia(50_000))
    escenario = _escenario_arbitraje()

    plan_sin = OptimizadorLP().optimizar(_planta(), estado, escenario, politica_sin)
    plan_con = OptimizadorLP().optimizar(_planta(), estado, escenario, politica_con)

    assert plan_con.ingreso_esperado_mills > plan_sin.ingreso_esperado_mills
    assert sum(plan_con.reserva_w) > 0
    # Feasibilidad conjunta: banda + setpoint dentro de la potencia de la batería.
    for accion, r in zip(plan_con.acciones, plan_con.reserva_w, strict=True):
        setpoint = accion.potencia.w if accion.tipo is not TipoAccion.RETENER else 0
        assert r + setpoint <= 50_000


def test_ingreso_incluye_la_disponibilidad() -> None:
    reserva = ReservaFrecuencia(
        precio_disponibilidad_mills_por_mwh=100_000, banda_max_w=40_000
    )
    politica = _politica(2, reserva)
    plan = OptimizadorLP().optimizar(
        _planta(), EstadoBateria(Energia(50_000)), _escenario_plano(2), politica
    )
    objetivo = FuncionObjetivo()
    esperado = objetivo.ingreso_bruto(
        plan, _escenario_plano(2), UNA_HORA
    ) + objetivo.ingreso_reserva(plan, politica)
    assert plan.ingreso_esperado_mills == esperado
    # 40 kWh de banda por hora x 2 h = 80 kWh; a 100k mills/MWh = 8000 mills
    assert objetivo.ingreso_reserva(plan, politica) == 8_000


def test_es_determinista_con_sscc() -> None:
    reserva = ReservaFrecuencia(
        precio_disponibilidad_mills_por_mwh=200_000, banda_max_w=30_000
    )
    politica = _politica(4, reserva)
    estado = EstadoBateria(Energia(50_000))
    a = OptimizadorLP().optimizar(_planta(), estado, _escenario_arbitraje(), politica)
    b = OptimizadorLP().optimizar(_planta(), estado, _escenario_arbitraje(), politica)
    assert a == b
