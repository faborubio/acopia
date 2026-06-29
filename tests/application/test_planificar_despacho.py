"""Tests de integración de la Fase 1: optimizador LP real + caso de uso PlanificarDespacho.

Demuestra el entregable de la fase: "dado un forecast, genero un plan factible y
rentable". Cubre sentido económico (arbitraje), factibilidad, determinismo,
ingreso auditable y persistencia con rastro.
"""

from __future__ import annotations

import pytest

from acopia.application.planificar_despacho import PlanificarDespacho
from acopia.domain.entities.accion_despacho import TipoAccion
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
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


def _bateria(
    eficiencia_pct: int = 100,
    throughput_garantia_wh: int = 10_000_000,
    soc_min_pct: int = 0,
    soc_max_pct: int = 100,
) -> Bateria:
    """100 kWh, 50 kW; por defecto 100 % (cuentas limpias) y SoC 0-100 %."""
    return Bateria(
        capacidad=Energia(100_000),
        potencia_max_carga=Potencia(50_000),
        potencia_max_descarga=Potencia(50_000),
        eficiencia_carga=Eficiencia.de_porcentaje(eficiencia_pct),
        eficiencia_descarga=Eficiencia.de_porcentaje(eficiencia_pct),
        soc_min=Soc.de_porcentaje(soc_min_pct),
        soc_max=Soc.de_porcentaje(soc_max_pct),
        throughput_garantia=Energia(throughput_garantia_wh),
    )


def _planta(bateria: Bateria, iny_w: int = 10_000_000, retiro_w: int = 10_000_000) -> Planta:
    """Planta con punto de conexión holgado por defecto (no fuerza vertimiento)."""
    return Planta("planta-test", bateria, Potencia(iny_w), Potencia(retiro_w))


def _politica(
    horizonte: int,
    costo_ciclado: int = 0,
    resolucion: Intervalo = UNA_HORA,
) -> PoliticaDespacho:
    return PoliticaDespacho(
        id="arbitraje",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=horizonte,
        resolucion=resolucion,
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


def _plan_es_factible(
    bateria: Bateria,
    estado: EstadoBateria,
    plan: PlanDespacho,
    resolucion: Intervalo = UNA_HORA,
) -> bool:
    modelo = ModeloBateria()
    actual = estado
    for accion in plan.acciones:
        if not modelo.es_factible(bateria, actual, accion, resolucion):
            return False
        actual = modelo.aplicar(bateria, actual, accion, resolucion)
    return True


def test_arbitraje_carga_barato_y_descarga_caro() -> None:
    optimizador = OptimizadorLP()
    bateria = _bateria()
    estado = EstadoBateria(Energia(0))
    plan = optimizador.optimizar(_planta(bateria), estado, _escenario_arbitraje(), _politica(4))

    tipos = [a.tipo for a in plan.acciones]
    assert tipos[:2] == [TipoAccion.CARGAR, TipoAccion.CARGAR]
    assert tipos[2:] == [TipoAccion.DESCARGAR, TipoAccion.DESCARGAR]
    # Ingreso: -(50k*10k + 50k*10k)/1e6 + (50k*500k + 50k*500k)/1e6 = -1000 + 50000
    assert plan.ingreso_esperado_mills == 49_000


def test_plan_generado_es_factible() -> None:
    optimizador = OptimizadorLP()
    bateria = _bateria()
    estado = EstadoBateria(Energia(0))
    plan = optimizador.optimizar(_planta(bateria), estado, _escenario_arbitraje(), _politica(4))
    assert _plan_es_factible(bateria, estado, plan)


def test_determinismo_mismo_plan() -> None:
    optimizador = OptimizadorLP()
    bateria = _bateria()
    estado = EstadoBateria(Energia(0))
    escenario = _escenario_arbitraje()
    plan_a = optimizador.optimizar(_planta(bateria), estado, escenario, _politica(4))
    plan_b = optimizador.optimizar(_planta(bateria), estado, escenario, _politica(4))
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
    plan = optimizador.optimizar(_planta(bateria), estado, escenario, _politica(4))
    assert all(a.tipo is not TipoAccion.CARGAR for a in plan.acciones)
    assert plan.ingreso_esperado_mills >= 0


def test_caso_de_uso_persiste_plan_con_rastro() -> None:
    repositorio = RepositorioPlanesEnMemoria()
    caso = PlanificarDespacho(OptimizadorLP(), repositorio)
    bateria = _bateria()
    estado = EstadoBateria(Energia(0))
    escenario = _escenario_arbitraje()

    resultado = caso.ejecutar(_planta(bateria), estado, escenario, _politica(4))

    plan_guardado, rastro = repositorio.obtener(resultado.plan_id)
    assert plan_guardado == resultado.plan
    assert rastro.estado_inicial == estado
    assert rastro.escenarios == (escenario,)
    assert rastro.semilla == 42


# --------------------------------------------------------------------------- #
# Casos borde (ver docs/CASES.md)
# --------------------------------------------------------------------------- #


def test_cmg_negativo_al_mediodia_carga_y_gana() -> None:
    # El caso más chileno: sobreoferta solar lleva el CMg a negativo al mediodía.
    # Cargar entonces se paga doble: te remuneran por absorber y guardas para la tarde.
    optimizador = OptimizadorLP()
    bateria = _bateria()
    estado = EstadoBateria(Energia(0))
    escenario = Escenario(
        (
            PuntoPronostico(Potencia(0), Precio(-50_000)),
            PuntoPronostico(Potencia(0), Precio(-50_000)),
            PuntoPronostico(Potencia(0), Precio(300_000)),
            PuntoPronostico(Potencia(0), Precio(300_000)),
        )
    )
    plan = optimizador.optimizar(_planta(bateria), estado, escenario, _politica(4))
    tipos = [a.tipo for a in plan.acciones]
    assert tipos == [
        TipoAccion.CARGAR,
        TipoAccion.CARGAR,
        TipoAccion.DESCARGAR,
        TipoAccion.DESCARGAR,
    ]
    # carga: 2 * (-50k * -50k)/1e6 = +5000 ; descarga: 2 * (50k * 300k)/1e6 = +30000
    assert plan.ingreso_esperado_mills == 35_000
    assert _plan_es_factible(bateria, estado, plan)


def test_resolucion_sub_horaria_factible_y_determinista() -> None:
    optimizador = OptimizadorLP()
    bateria = _bateria()
    estado = EstadoBateria(Energia(0))
    escenario = _escenario_arbitraje()
    politica = _politica(4, resolucion=Intervalo.de_minutos(15))
    plan_a = optimizador.optimizar(_planta(bateria), estado, escenario, politica)
    plan_b = optimizador.optimizar(_planta(bateria), estado, escenario, politica)
    assert plan_a == plan_b
    assert _plan_es_factible(bateria, estado, plan_a, Intervalo.de_minutos(15))


def test_throughput_cero_no_cicla() -> None:
    # Garantía de throughput agotada: la batería no puede ciclar nada.
    optimizador = OptimizadorLP()
    bateria = _bateria(throughput_garantia_wh=0)
    estado = EstadoBateria(Energia(50_000))
    plan = optimizador.optimizar(_planta(bateria), estado, _escenario_arbitraje(), _politica(4))
    assert all(a.tipo is TipoAccion.RETENER for a in plan.acciones)


def test_eficiencia_bajo_break_even_no_arbitra() -> None:
    # Round-trip 49 % (70 %·70 %): el spread 1.5x no cubre la pérdida, así que no carga.
    optimizador = OptimizadorLP()
    bateria = _bateria(eficiencia_pct=70)
    estado = EstadoBateria(Energia(0))
    escenario = Escenario(
        (
            PuntoPronostico(Potencia(0), Precio(100_000)),
            PuntoPronostico(Potencia(0), Precio(100_000)),
            PuntoPronostico(Potencia(0), Precio(150_000)),
            PuntoPronostico(Potencia(0), Precio(150_000)),
        )
    )
    plan = optimizador.optimizar(_planta(bateria), estado, escenario, _politica(4))
    assert all(a.tipo is TipoAccion.RETENER for a in plan.acciones)


def test_soc_sin_banda_operativa_solo_retiene() -> None:
    # SoC_min == SoC_max: no hay banda para mover energía; no puede cargar ni descargar.
    optimizador = OptimizadorLP()
    bateria = _bateria(soc_min_pct=50, soc_max_pct=50)
    estado = EstadoBateria(Energia(50_000))
    plan = optimizador.optimizar(_planta(bateria), estado, _escenario_arbitraje(), _politica(4))
    assert all(a.tipo is TipoAccion.RETENER for a in plan.acciones)


# --- Límite de transmisión / curtailment (el problema estructural chileno) ----


def _escenario_curtailment() -> Escenario:
    """Mediodía con mucho sol y CMg bajo; tarde sin sol y CMg alto."""
    return Escenario(
        (
            PuntoPronostico(Potencia(80_000), Precio(10_000)),   # PV 80 kWh > techo de red
            PuntoPronostico(Potencia(0), Precio(500_000)),       # tarde cara
            PuntoPronostico(Potencia(0), Precio(500_000)),
        )
    )


def test_limite_de_inyeccion_carga_para_evitar_vertimiento() -> None:
    # Batería de 30 kWh: absorbe parte del exceso de PV y reduce el vertimiento;
    # luego inyecta en la tarde cara. El excedente que no cabe ni en la red ni en
    # la batería se vierte (curtailment), exactamente el problema de los 6 TWh.
    optimizador = OptimizadorLP()
    bateria = _bateria(soc_max_pct=30)  # 30 kWh útiles
    estado = EstadoBateria(Energia(0))
    planta = _planta(bateria, iny_w=30_000)  # techo de inyección 30 kW
    plan = optimizador.optimizar(planta, estado, _escenario_curtailment(), _politica(3))

    tipos = [a.tipo for a in plan.acciones]
    assert tipos[0] is TipoAccion.CARGAR          # carga el exceso de PV
    assert tipos[1] is TipoAccion.DESCARGAR       # vende en la tarde cara
    # Mediodía: PV 80 - inyecta 30 - carga 30 => se vierten 20 kWh
    assert plan.energia_vertida_wh[0] == 20_000
    assert plan.energia_vertida_wh[1] == 0
    assert _plan_es_factible(bateria, estado, plan)


def test_punto_de_conexion_holgado_no_vierte() -> None:
    # Con un techo de inyección amplio no hay vertimiento aunque haya mucho sol.
    optimizador = OptimizadorLP()
    bateria = _bateria(soc_max_pct=30)
    estado = EstadoBateria(Energia(0))
    planta = _planta(bateria, iny_w=10_000_000)
    plan = optimizador.optimizar(planta, estado, _escenario_curtailment(), _politica(3))
    assert sum(plan.energia_vertida_wh) == 0


# --- Deuda resuelta: SoC terminal, estado fuera de banda, CMg negativo, horizonte 1 ---


def test_valor_energia_final_evita_liquidacion() -> None:
    # Con precio plano y batería llena, valorizar la energía final por encima del spot
    # hace que NO se liquide la batería (corrige el efecto fin de horizonte).
    optimizador = OptimizadorLP()
    bateria = _bateria(eficiencia_pct=95)  # round-trip < 100 % penaliza el churn
    estado = EstadoBateria(Energia(100_000))  # llena
    escenario = Escenario(tuple(PuntoPronostico(Potencia(0), Precio(100_000)) for _ in range(2)))
    politica = PoliticaDespacho(
        id="con-valor-final",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=2,
        resolucion=UNA_HORA,
        semilla=42,
        precio_energia_final_mills_por_mwh=200_000,  # vale más guardar que vender a 100k
    )
    plan = optimizador.optimizar(_planta(bateria), estado, escenario, politica)
    assert all(a.tipo is TipoAccion.RETENER for a in plan.acciones)


def test_estado_inicial_fuera_de_banda_es_error() -> None:
    optimizador = OptimizadorLP()
    bateria = _bateria(soc_min_pct=10, soc_max_pct=90)  # banda [10k, 90k]
    estado = EstadoBateria(Energia(95_000))  # por encima del máximo operativo
    with pytest.raises(ValueError, match="fuera de la banda"):
        optimizador.optimizar(_planta(bateria), estado, _escenario_arbitraje(), _politica(4))


def test_curtailment_voluntario_a_cmg_negativo() -> None:
    # CMg negativo con batería llena (no puede absorber): vierte el PV en vez de
    # inyectarlo a pérdida. Sin esto, el plan pagaría por inyectar.
    optimizador = OptimizadorLP()
    bateria = _bateria()
    estado = EstadoBateria(Energia(100_000))  # llena: no puede cargar
    escenario = Escenario((PuntoPronostico(Potencia(50_000), Precio(-100_000)),))
    politica = PoliticaDespacho(
        id="cmg-negativo",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=1,
        resolucion=UNA_HORA,
        semilla=42,
        precio_energia_final_mills_por_mwh=0,  # neutraliza el valor terminal
    )
    plan = optimizador.optimizar(_planta(bateria), estado, escenario, politica)
    assert plan.energia_vertida_wh[0] == 50_000  # vierte todo el PV
    assert plan.ingreso_esperado_mills == 0      # no inyecta a precio negativo


def test_horizonte_de_un_intervalo() -> None:
    optimizador = OptimizadorLP()
    bateria = _bateria()
    estado = EstadoBateria(Energia(0))
    escenario = Escenario((PuntoPronostico(Potencia(0), Precio(100_000)),))
    plan = optimizador.optimizar(_planta(bateria), estado, escenario, _politica(1))
    assert len(plan.acciones) == 1
    assert _plan_es_factible(bateria, estado, plan)
