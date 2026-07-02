"""Tests del ExplicadorDespacho: la explicabilidad que consume la capa MCP."""

from __future__ import annotations

import pytest

from acopia.domain.entities.accion_despacho import AccionDespacho
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.rastro import RastroDespacho
from acopia.domain.services.explicador_despacho import ExplicadorDespacho
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


def _armar(acciones: list[AccionDespacho], cmgs: list[int]) -> tuple[PlanDespacho, RastroDespacho]:
    plan = PlanDespacho(
        politica_id="p",
        politica_version=1,
        semilla=0,
        acciones=tuple(acciones),
        energia_vertida_wh=(0,) * len(acciones),
        ingreso_esperado_mills=0,
    )
    escenario = Escenario(
        tuple(PuntoPronostico(Potencia(0), Precio(c)) for c in cmgs)
    )
    rastro = RastroDespacho(
        politica_id="p",
        politica_version=1,
        semilla=0,
        estado_inicial=EstadoBateria(Energia(0)),
        escenarios=(escenario,),
    )
    return plan, rastro


def test_explica_el_arbitraje_completo() -> None:
    plan, rastro = _armar(
        [
            AccionDespacho.cargar(Potencia(10_000)),
            AccionDespacho.retener(),
            AccionDespacho.descargar(Potencia(10_000)),
        ],
        [10_000, 50_000, 500_000],
    )
    explicaciones = ExplicadorDespacho().explicar(_bateria(), plan, rastro, UNA_HORA)

    assert len(explicaciones) == 3
    carga, retiene, descarga = explicaciones
    assert carga.accion == "CARGAR" and "más baratos" in carga.motivo
    assert carga.percentil_cmg_bp == 0  # el CMg más barato del horizonte
    assert descarga.accion == "DESCARGAR" and "más caros" in descarga.motivo
    assert descarga.percentil_cmg_bp == 10_000  # el más caro
    assert retiene.accion == "RETENER"
    # Trayectoria de SoC reconstruida: 0 -> 10k -> 10k -> 0
    assert carga.energia_despues_wh == 10_000
    assert descarga.energia_antes_wh == 10_000
    assert descarga.energia_despues_wh == 0


def test_menciona_la_banda_sscc_al_retener() -> None:
    plan, rastro = _armar([AccionDespacho.retener()], [50_000])
    plan = PlanDespacho(
        politica_id="p",
        politica_version=1,
        semilla=0,
        acciones=plan.acciones,
        energia_vertida_wh=plan.energia_vertida_wh,
        ingreso_esperado_mills=0,
        reserva_w=(30_000,),
    )
    (explicacion,) = ExplicadorDespacho().explicar(_bateria(), plan, rastro, UNA_HORA)
    assert explicacion.reserva_w == 30_000
    assert "banda SSCC" in explicacion.motivo


def test_cmg_negativo_explica_absorber() -> None:
    plan, rastro = _armar([AccionDespacho.cargar(Potencia(10_000))], [-5_000])
    (explicacion,) = ExplicadorDespacho().explicar(_bateria(), plan, rastro, UNA_HORA)
    assert "pagaría por generar" in explicacion.motivo


def test_rastro_inconsistente_es_error() -> None:
    plan, rastro = _armar([AccionDespacho.retener()], [50_000, 60_000])
    with pytest.raises(ValueError, match="rastro"):
        ExplicadorDespacho().explicar(_bateria(), plan, rastro, UNA_HORA)
