"""Tests de comparar_modos: la comparación es fiel al rastro y no persiste nada.

Se testea el caso de uso con dobles baratos (el LP y un stub que retiene): la
conducta del optimizador DRL real vive en ``tests/infrastructure/test_optimizador_drl.py``.
"""

from __future__ import annotations

from acopia.application.comparar_modos import comparar_modos
from acopia.domain.entities.accion_despacho import AccionDespacho
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
from acopia.domain.entities.rastro import RastroDespacho
from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.domain.value_objects.soc import Soc
from acopia.infrastructure.optimizacion.optimizador_lp import OptimizadorLP

UNA_HORA = Intervalo.de_minutos(60)


class _OptimizadorQueRetiene:
    """Doble de PuertoOptimizador: siempre retiene (ingreso = solo el PV). Registra el modo."""

    def __init__(self) -> None:
        self.modo_recibido: Modo | None = None

    def optimizar(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        escenario: Escenario,
        politica: PoliticaDespacho,
    ) -> PlanDespacho:
        return self.optimizar_escenarios(planta, estado_inicial, (escenario,), politica)

    def optimizar_escenarios(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        escenarios: tuple[Escenario, ...],
        politica: PoliticaDespacho,
    ) -> PlanDespacho:
        self.modo_recibido = politica.modo
        n = politica.horizonte_intervalos
        return PlanDespacho(
            politica_id=politica.id,
            politica_version=politica.version,
            semilla=politica.semilla,
            acciones=tuple(AccionDespacho.retener() for _ in range(n)),
            energia_vertida_wh=(0,) * n,
            ingreso_esperado_mills=0,
        )


def _contexto() -> tuple[Planta, RastroDespacho, PoliticaDespacho]:
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
    planta = Planta("planta-test", bateria, Potencia(1_000_000), Potencia(1_000_000))
    politica = PoliticaDespacho(
        id="comparacion",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=4,
        resolucion=UNA_HORA,
        semilla=7,
        modo=Modo.PREDICT_THEN_OPTIMIZE,
    )
    escenario = Escenario(
        (
            PuntoPronostico(Potencia(0), Precio(10_000)),
            PuntoPronostico(Potencia(0), Precio(10_000)),
            PuntoPronostico(Potencia(0), Precio(300_000)),
            PuntoPronostico(Potencia(0), Precio(300_000)),
        )
    )
    rastro = RastroDespacho(
        politica_id=politica.id,
        politica_version=politica.version,
        semilla=politica.semilla,
        estado_inicial=EstadoBateria(Energia(0)),
        escenarios=(escenario,),
    )
    return planta, rastro, politica


def test_compara_ambos_modos_sobre_el_mismo_rastro() -> None:
    planta, rastro, politica = _contexto()
    stub = _OptimizadorQueRetiene()
    resultado = comparar_modos(OptimizadorLP(), stub, planta, rastro, politica)

    # El LP arbitra (carga barato, vende caro): ingreso positivo. El stub retiene: 0.
    assert resultado.ingreso_deterministico_mills > 0
    assert resultado.ingreso_drl_mills == 0
    assert resultado.delta_mills == -resultado.ingreso_deterministico_mills
    assert resultado.brecha_bp == -10_000  # el "DRL" deja el 100% sobre la mesa


def test_cada_optimizador_recibe_su_modo() -> None:
    planta, rastro, politica = _contexto()
    stub = _OptimizadorQueRetiene()
    comparar_modos(OptimizadorLP(), stub, planta, rastro, politica)
    assert stub.modo_recibido is Modo.DRL


def test_no_muta_la_politica_original() -> None:
    planta, rastro, politica = _contexto()
    comparar_modos(OptimizadorLP(), _OptimizadorQueRetiene(), planta, rastro, politica)
    assert politica.modo is Modo.PREDICT_THEN_OPTIMIZE


def test_brecha_cero_si_el_baseline_es_cero() -> None:
    planta, rastro, politica = _contexto()
    stub = _OptimizadorQueRetiene()
    resultado = comparar_modos(stub, _OptimizadorQueRetiene(), planta, rastro, politica)
    assert resultado.brecha_bp == 0
