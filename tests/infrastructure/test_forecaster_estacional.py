"""Tests del ForecasterEstacionalNaive y la integración forecast -> despacho."""

from __future__ import annotations

from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.observacion import Observacion
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import Objetivo, PoliticaDespacho
from acopia.domain.services.modelo_bateria import ModeloBateria
from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.domain.value_objects.soc import Soc
from acopia.infrastructure.forecasting.forecaster_estacional import ForecasterEstacionalNaive
from acopia.infrastructure.optimizacion.optimizador_lp import OptimizadorLP

# Patrón diario de 4 pasos (mediodía soleado y barato), 3 ciclos exactos.
_GEN = [0, 50, 100, 50]
_CMG = [100_000, 80_000, 60_000, 80_000]


def _historia_periodica() -> tuple[Observacion, ...]:
    return tuple(
        Observacion(Potencia(_GEN[i % 4]), Precio(_CMG[i % 4])) for i in range(12)
    )


def _historia_con_ruido() -> tuple[Observacion, ...]:
    gen = [0, 50, 100, 50, 0, 55, 90, 45, 0, 60, 110, 40]
    cmg = [100_000, 80_000, 60_000, 80_000, 98_000, 82_000, 55_000, 79_000,
           101_000, 78_000, 63_000, 77_000]
    return tuple(Observacion(Potencia(g), Precio(c)) for g, c in zip(gen, cmg, strict=True))


def _bateria() -> Bateria:
    return Bateria(
        capacidad=Energia(100_000),
        potencia_max_carga=Potencia(50_000),
        potencia_max_descarga=Potencia(50_000),
        eficiencia_carga=Eficiencia.de_porcentaje(95),
        eficiencia_descarga=Eficiencia.de_porcentaje(95),
        soc_min=Soc.de_porcentaje(0),
        soc_max=Soc.de_porcentaje(100),
        throughput_garantia=Energia(10_000_000),
    )


def test_pronostico_puntual_repite_la_estacion() -> None:
    forecaster = ForecasterEstacionalNaive(estacionalidad=4)
    escenarios = forecaster.pronosticar(
        _historia_periodica(), horizonte=4, n_escenarios=1, semilla=0
    )
    assert len(escenarios) == 1
    puntos = escenarios[0].puntos
    assert [p.generacion.w for p in puntos] == _GEN
    assert [p.cmg.mills_por_mwh for p in puntos] == _CMG


def test_es_determinista_con_la_misma_semilla() -> None:
    forecaster = ForecasterEstacionalNaive(estacionalidad=4)
    historia = _historia_con_ruido()
    a = forecaster.pronosticar(historia, horizonte=4, n_escenarios=5, semilla=7)
    b = forecaster.pronosticar(historia, horizonte=4, n_escenarios=5, semilla=7)
    assert a == b


def test_genera_incertidumbre_entre_escenarios() -> None:
    forecaster = ForecasterEstacionalNaive(estacionalidad=4)
    escenarios = forecaster.pronosticar(
        _historia_con_ruido(), horizonte=4, n_escenarios=10, semilla=3
    )
    assert len(escenarios) == 10
    # el escenario 0 es el puntual; al menos uno de los demás difiere
    assert any(e.puntos != escenarios[0].puntos for e in escenarios[1:])


def test_generacion_nunca_negativa() -> None:
    forecaster = ForecasterEstacionalNaive(estacionalidad=4)
    escenarios = forecaster.pronosticar(
        _historia_con_ruido(), horizonte=4, n_escenarios=20, semilla=1
    )
    assert all(p.generacion.w >= 0 for e in escenarios for p in e.puntos)


def test_integracion_forecast_alimenta_el_despacho() -> None:
    # Fase 2 -> Fase 1: el escenario pronosticado produce un plan factible.
    forecaster = ForecasterEstacionalNaive(estacionalidad=4)
    escenarios = forecaster.pronosticar(
        _historia_periodica(), horizonte=4, n_escenarios=1, semilla=0
    )

    bateria = _bateria()
    planta = Planta("p", bateria, Potencia(10_000_000), Potencia(10_000_000))
    estado = EstadoBateria(Energia(0))
    politica = PoliticaDespacho(
        id="con-forecast",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=4,
        resolucion=Intervalo.de_minutos(60),
        semilla=0,
    )
    plan = OptimizadorLP().optimizar(planta, estado, escenarios[0], politica)

    modelo = ModeloBateria()
    actual = estado
    for accion in plan.acciones:
        assert modelo.es_factible(bateria, actual, accion, politica.resolucion)
        actual = modelo.aplicar(bateria, actual, accion, politica.resolucion)
